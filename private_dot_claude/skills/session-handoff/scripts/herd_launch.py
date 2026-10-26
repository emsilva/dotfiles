"""launch: start a worker in a new pane right of the lead, verify its banner, record it.

Codex at xhigh unless told otherwise; Claude with the lead's model at high effort when --kind claude, and only as a
builder (Claude has no sandbox to hold it read-only); opencode with its configured default model and effort when --kind
opencode, also only as a builder (no sandbox either); Grok Build at grok-4.7 xhigh when --kind grok, also only as
a builder (its sandbox off, permissions bypassed). A builder gets its own worktree and branch; a read-only worker
runs in the repo. Any failure closes the pane this command created, removes the worktree it created, and records
nothing. After starting in a reused pane, a failure reports the agent for manual cleanup because the pane is not
owned by this launch.
"""
import datetime
import json
import os
import re
import subprocess
import time
import uuid

import herdlib
import relaylib
import transcript

DEFAULTS = {'codex': ('gpt-6.1-sol', 'xhigh'), 'claude': (None, 'high'),   # Claude's model: the lead's own
            'opencode': ('gpt-6.1-sol', 'xhigh'), 'grok': ('grok-4.7', 'xhigh')}
NO_SANDBOX = ('claude', 'opencode', 'grok')
TRUST_OPTION = 'Yes, I trust this folder'
TRUST_YES = re.compile(r'❯\s*(?:\d+\.\s*)?Yes, I trust this folder')
GROK_TRUST = 'Do you trust the contents of this directory?'   # Grok Build 1.0.70; "y" answers "Yes, proceed"
GROK_READY = ('Ctrl+.:shortcuts', '─❯')   # its idle input line, as drawn in a short herd pane
STOP_ON = ('agent_name_taken', 'agent_not_ready')
SETTLE_BOUND = int(os.environ.get('HERD_SETTLE_SECONDS', '60'))   # after a startup dialog


def add_arguments(p):
    p.add_argument('role', help='what the worker does: [a-z][a-z0-9-]*, the start of its name')
    p.add_argument('--kind', choices=('codex', 'claude', 'opencode', 'grok'), default='codex')
    mode = p.add_mutually_exclusive_group()
    mode.add_argument('--builder', action='store_true', help='a worktree and branch of its own; it commits')
    mode.add_argument('--readonly', action='store_true', help='the default: runs in the repo, cannot write .git')
    p.add_argument('--base', help='builder: the commit or branch the worktree is cut from')
    p.add_argument('--type', default='feat', help='builder: the branch type, <type>/<name>-<YYYYMMDD>')
    p.add_argument('--model')
    p.add_argument('--effort')
    p.add_argument('--repo', help='default: the git top level of the current directory, else the directory')
    p.add_argument('--pane', help='start in this existing shell pane instead of splitting a new one')


def placement(layout, self_pane):
    """(pane to split, direction): down from the bottom pane of the column right of the lead, or right of the
    lead when it has no column to its right. Never a third column."""
    try:
        panes = layout['result']['layout']['panes']
        if not isinstance(panes, list) or any(
                not isinstance(p, dict) or not isinstance(p.get('pane_id'), str) or not p['pane_id']
                or not isinstance(p.get('rect'), dict)
                or any(type(p['rect'].get(k)) is not int for k in ('x', 'y', 'width', 'height'))
                or p['rect']['width'] <= 0 or p['rect']['height'] <= 0 for p in panes):
            raise ValueError
    except (KeyError, TypeError, ValueError):
        raise relaylib.HerdrError('herdr pane layout: result.layout.panes has an unexpected shape')
    me = next((p['rect'] for p in panes if p['pane_id'] == self_pane), None)
    if me is None:
        raise herdlib.Refusal('the lead pane %s is not in its own layout' % self_pane)
    right = [p for p in panes if p['rect']['x'] >= me['x'] + me['width']]
    if not right:
        return self_pane, 'right'
    column = min(p['rect']['x'] for p in right)
    bottom = max((p for p in right if p['rect']['x'] == column), key=lambda p: p['rect']['y'] + p['rect']['height'])
    return bottom['pane_id'], 'down'


def agent_args(kind, mode, model, effort, cwd, session_id):
    """The agent's own command-line arguments (after herdr's --)."""
    if kind == 'codex':
        # The inline table trusts cwd for this session only: no dialog, ~/.codex/config.toml untouched.
        args = ['-m', model, '-c', 'model_reasoning_effort="%s"' % effort,
                '-c', 'projects={%s={trust_level="trusted"}}' % json.dumps(cwd)]
        return args + (['--dangerously-bypass-approvals-and-sandbox'] if mode == 'builder'
                       else ['-s', 'workspace-write', '-a', 'never'])
    if kind == 'opencode':
        # The TUI takes no model or effort flag: they come from the opencode config (opencode_defaults checks them).
        # --session names the session up front, so the record knows it before the first prompt.
        return [cwd, '--auto', '--session', session_id]
    if kind == 'grok':
        # bypassPermissions runs tools without asking (the session records yolo_mode); its sandbox profile is off.
        return ['-m', model, '--reasoning-effort', effort, '--session-id', session_id,
                '--permission-mode', 'bypassPermissions']
    return ['--model', model, '--effort', effort, '--dangerously-skip-permissions', '--session-id', session_id]


def opencode_defaults():
    """(model, effort) a new opencode session gets from its config: the default model and that model's
    reasoningEffort setting. opencode v2's TUI takes neither on its command line."""
    r = subprocess.run(['opencode', 'debug', 'config'], capture_output=True, text=True, timeout=60)
    try:
        sources = json.loads(r.stdout)
    except ValueError:
        raise herdlib.Refusal('opencode debug config did not print JSON: %s' % ' '.join((r.stderr or r.stdout).split())[:200])
    model, effort = None, None
    for source in sources:   # lowest precedence first: later sources win
        info = source.get('info') if isinstance(source, dict) else None
        if not isinstance(info, dict):
            continue
        default = info.get('model')
        if isinstance(default, dict) and default.get('model'):
            model = default['model']
        elif isinstance(default, str) and default:
            model = default.split('/', 1)[-1].split('#', 1)[0]
        for provider in (info.get('providers') or {}).values():
            for mid, entry in ((provider or {}).get('models') or {}).items():
                value = ((entry or {}).get('settings') or {}).get('reasoningEffort')
                if value and mid == model:
                    effort = value
    return model, effort


def git(*args):
    r = subprocess.run(['git', *args], capture_output=True, text=True, timeout=60)
    if r.returncode != 0:
        raise herdlib.Refusal('git %s failed: %s' % (' '.join(args), ' '.join(r.stderr.split())))
    return r.stdout.strip()


def screen(pane):
    """What the pane shows: its viewport, then the bottom buffer (a dialog in a short pane can sit below the
    viewport's top lines, and the bottom buffer alone can miss its header)."""
    return (relaylib.herdr_text('pane', 'read', pane, '--source', 'visible') + '\n'
            + relaylib.herdr_text('pane', 'read', pane, '--source', 'detection'))


def answer_startup_dialog(kind, pane, cwd):
    """`agent start` answered agent_not_ready: a dialog holds the agent. Claude's folder-trust dialog is
    answered yes (it preselects "No, exit"): the agent runs in cwd, which this launch chose (the repo, a worktree
    it just created, or a --pane already checked to be in cwd), so the dialog can only be about cwd. Codex's
    update menu is skipped with esc. Anything else fails."""
    text = screen(pane)
    if kind == 'claude':
        if TRUST_OPTION not in text:
            raise herdr_failure('Claude is blocked at startup on something other than the trust dialog for %s'
                                % cwd, text)
        relaylib.herdr_text('agent', 'send-keys', pane, 'down')
        text = screen(pane)
        if not TRUST_YES.search(text):
            raise herdr_failure('the trust dialog did not select "Yes, I trust this folder"', text)
        relaylib.herdr_text('agent', 'send-keys', pane, 'enter')
    else:
        if 'trust' in text.lower():
            raise herdr_failure('Codex asks to trust %s despite the override' % cwd, text)
        relaylib.herdr_text('agent', 'send-keys', pane, 'esc')
    # Not `agent wait`: it returns on the first settled state, and the pane is still `blocked` until the key lands.
    deadline = time.monotonic() + SETTLE_BOUND
    while True:
        agent = (relaylib.herdr_json('agent', 'get', pane).get('result') or {}).get('agent') or {}
        if agent.get('agent_status') in ('idle', 'done'):
            return
        if time.monotonic() >= deadline:
            raise herdr_failure('the agent is still %s %d s after its startup dialog'
                                % (agent.get('agent_status'), SETTLE_BOUND), text)
        time.sleep(1)


def grok_startup(pane, cwd, blocked):
    """Bring a starting Grok Build to its input prompt. It may ask whether to trust a folder it has not seen, and
    herdr reports that question as idle, not blocked, so a successful `agent start` can return with it on screen,
    or before it is drawn. The worker runs in cwd, which this launch chose, so the question is answered "y", once:
    herdr's status is no evidence that the question has cleared, and a second "y" would land in the input line or
    a later dialog. Done when the input prompt shows and the question does not; anything else for the bound fails.
    blocked: herdr answered agent_not_ready, so a dialog is up; one that is not the trust question fails at once.
    (A worktree under a trusted repo is trusted already: no question.)"""
    deadline = time.monotonic() + SETTLE_BOUND
    answered = False
    text = screen(pane)
    if blocked and GROK_TRUST not in text:
        raise herdr_failure('Grok is blocked at startup on something other than the trust question for %s' % cwd,
                            text)
    while True:
        if GROK_TRUST in text:
            if not answered:
                relaylib.herdr_text('agent', 'send-keys', pane, 'y')
                answered = True
        elif any(mark in text for mark in GROK_READY):
            return
        if time.monotonic() >= deadline:
            raise herdr_failure('Grok still asks to trust %s %d s after "y"' % (cwd, SETTLE_BOUND) if answered else
                                'Grok shows no input prompt %d s after it started' % SETTLE_BOUND, text)
        time.sleep(1)
        text = screen(pane)


def verify_banner(pane, model_text, effort):
    """The banner must show the model and the effort. relaylib.read_banner reads it again for up to its bound
    (relay-launch.sh shares it): after a startup dialog Claude redraws, and the pane can read blank while idle."""
    problem, text = relaylib.read_banner(pane, model_text, effort)
    if problem:
        raise herdr_failure(problem, text)


def herdr_failure(message, text):
    return herdlib.Refusal('%s (pane shows: %s)' % (message, relaylib.screen_tail(text)))


def run(a, taken_names=(), attempts=3):
    self_pane = herdlib.require_herdr()
    pdir = herdlib.project_dir(a.projects, a.record_dir)
    rows = herdlib.read(pdir)
    repo = os.path.realpath(a.repo) if a.repo else (herdlib.git_toplevel(os.getcwd()) or os.path.realpath('.'))
    mode = 'builder' if a.builder else 'readonly'
    if a.kind in NO_SANDBOX and mode == 'readonly':
        raise herdlib.Refusal('a %s worker has no sandbox, so it cannot be read-only: launch it with --builder '
                              '--base <ref> (its own worktree), or give read-only work to a Codex worker'
                              % a.kind.capitalize())
    if mode == 'builder' and not a.base:
        raise herdlib.Refusal('--builder needs --base <ref>: the commit the worktree is cut from')
    if mode == 'builder' and herdlib.git_toplevel(repo) != repo:
        raise herdlib.Refusal('--builder needs a git repo top level, and %s is not one' % repo)
    model = a.model or DEFAULTS[a.kind][0]
    effort = a.effort or DEFAULTS[a.kind][1]
    if a.kind == 'opencode':
        configured = opencode_defaults()
        if configured != (model, effort):
            raise herdlib.Refusal('opencode starts new sessions on %s at effort %s (its config), not %s at %s: set '
                                  '"model" and providers.<p>.models.<m>.settings.reasoningEffort in '
                                  '~/.config/opencode/opencode.json' % (configured + (model, effort)))
    if not model:
        session = os.environ['CLAUDE_CODE_SESSION_ID']
        model = transcript.last_model(transcript.find_transcript(session, a.projects))
        if not model:
            raise herdlib.Refusal("the lead's transcript names no model: pass --model")
    taken = {agent.get('name') for agent in relaylib.herdr_list('agents', 'agent', 'list')} | set(taken_names)
    try:
        lid, name = herdlib.new_name(a.role, effort, rows, taken)
    except ValueError as e:
        raise herdlib.Refusal(str(e))
    session_id = (str(uuid.uuid4()) if a.kind in ('claude', 'grok') else
                  'ses_herd' + uuid.uuid4().hex[:20] if a.kind == 'opencode' else None)
    worktree = branch = None
    created_worktree = False
    created_pane = None
    started = False
    cwd = repo
    try:
        if mode == 'builder':
            worktree = os.path.join(repo, '.claude', 'worktrees', name)
            branch = '%s/%s-%s' % (a.type, name, datetime.date.today().strftime('%Y%m%d'))
            git('-C', repo, 'worktree', 'add', worktree, '-b', branch, a.base)
            created_worktree = True
            cwd = worktree
        if a.pane:
            pane = a.pane
            info = next((p for p in relaylib.herdr_list('panes', 'pane', 'list') if p.get('pane_id') == pane), None)
            if info is None or info.get('agent'):
                raise herdlib.Refusal('pane %s is not a shell pane (%s)' % (pane, 'gone' if info is None
                                                                          else 'it hosts ' + info['agent']))
            if os.path.realpath(info.get('cwd') or '/') != cwd:
                raise herdlib.Refusal('pane %s is in %s, not %s: cd there first' % (pane, info.get('cwd'), cwd))
        else:
            layout = relaylib.herdr_json('pane', 'layout', '--pane', self_pane)
            target, direction = placement(layout, self_pane)
            split = relaylib.herdr_json('pane', 'split', target, '--direction', direction, '--cwd', cwd, '--no-focus')
            try:
                pane = split['result']['pane']['pane_id']
                if not isinstance(pane, str) or not pane:
                    raise ValueError
            except (KeyError, TypeError, ValueError):
                raise relaylib.HerdrError('herdr pane split: result.pane.pane_id is not a nonempty string')
            created_pane = pane
        started_at = herdlib.now_iso()   # a Codex session file is stamped with its start, before this row's `at`
        ok, out = relaylib.start_agent(name, a.kind, pane, agent_args(a.kind, mode, model, effort, cwd,
                                                                   session_id), stop_on=STOP_ON)
        started = ok or relaylib.error_code(out) == 'agent_not_ready'
        if not ok and relaylib.error_code(out) == 'agent_name_taken' and attempts > 1:
            # Redraw the whole launch: its worktree, branch, pane cwd and trust override carry the name too.
            undo(created_pane, repo, worktree if created_worktree else None,
                 branch if created_worktree else None, a.base)
            created_pane, created_worktree = None, False
            return run(a, taken | {name}, attempts - 1)
        if not ok and relaylib.error_code(out) == 'agent_not_ready':
            if a.kind == 'grok':
                grok_startup(pane, cwd, blocked=True)
            else:
                answer_startup_dialog(a.kind, pane, cwd)
            agent = (relaylib.herdr_json('agent', 'get', pane).get('result') or {}).get('agent') or {}
            if agent.get('name') != name:
                relaylib.herdr_text('agent', 'rename', pane, name)
        elif not ok:
            raise herdlib.Refusal('agent start failed: %s' % out)
        elif a.kind == 'grok':
            grok_startup(pane, cwd, blocked=False)
        if a.kind not in ('opencode', 'grok'):
            # opencode's home screen draws no model line until its first prompt (and draws badly in a short pane):
            # opencode_defaults checked the config above, and dispatch checks the session's model and variant.
            # Grok draws no model or effort line either; its argv names both, and dispatch checks them against
            # the session's summary.json.
            verify_banner(pane, relaylib.banner_model(a.kind, model), effort)
        agent = (relaylib.herdr_json('agent', 'get', pane).get('result') or {}).get('agent') or {}
        session_id = (agent.get('agent_session') or {}).get('value') or session_id
        row = herdlib.append(pdir, {
            'type': 'launch', 'launch_id': lid, 'name': name, 'pane_id': pane, 'kind': a.kind, 'model': model,
            'effort': effort, 'mode': mode, 'cwd': cwd, 'worktree': worktree, 'branch': branch,
            'session_id': session_id, 'lead_session': os.environ.get('CLAUDE_CODE_SESSION_ID'), 'adopted': False,
            'started_at': started_at})
    except (herdlib.Refusal, relaylib.HerdrError, herdlib.RecordError, OSError) as e:
        if a.pane and started:
            # Herdr has no agent-stop command. Keys/prompts do not guarantee process exit, and closing a reused
            # pane would destroy a resource this launch does not own. Keep its resources for the lead's cleanup.
            raise herdlib.RecordError('launch failed after starting agent %s (%s) in reused pane %s; '
                                      'it may still be running unrecorded; close the agent manually: %s'
                                      % (name, a.kind, pane, e)) from e
        undo(created_pane, repo, worktree if created_worktree else None, branch if created_worktree else None, a.base)
        if isinstance(e, OSError):
            raise herdlib.RecordError('launch could not write its record or resources: %s' % e)
        raise
    print(json.dumps(row))
    return 0


def undo(pane, repo, worktree, branch, base):
    """Close the pane this launch created and remove the worktree and branch it created (only while the branch
    still sits on its base: a worktree with work in it is never removed)."""
    if pane:
        subprocess.run(['herdr', 'pane', 'close', pane], capture_output=True, timeout=10)
    if worktree and os.path.isdir(worktree):
        tip = subprocess.run(['git', '-C', repo, 'rev-parse', branch], capture_output=True, text=True).stdout.strip()
        start = subprocess.run(['git', '-C', repo, 'rev-parse', base], capture_output=True, text=True).stdout.strip()
        if tip and tip == start:
            subprocess.run(['git', '-C', repo, 'worktree', 'remove', worktree], capture_output=True)
            subprocess.run(['git', '-C', repo, 'branch', '-D', branch], capture_output=True)

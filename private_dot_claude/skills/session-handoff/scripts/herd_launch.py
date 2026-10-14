"""launch: start a worker in a new pane right of the lead, verify its banner, record it.

Codex at xhigh unless told otherwise; Claude with the lead's model at high effort when --kind claude, and only as a
builder (Claude has no sandbox to hold it read-only). A builder gets its own worktree and branch; a read-only worker
runs in the repo. Any failure closes the pane this command
created, removes the worktree it created, and records nothing.
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

DEFAULTS = {'codex': ('gpt-6.1-sol', 'xhigh'), 'claude': (None, 'high')}   # Claude's model: the lead's own
TRUST_OPTION = 'Yes, I trust this folder'
TRUST_YES = re.compile(r'❯\s*(?:\d+\.\s*)?Yes, I trust this folder')
STOP_ON = ('agent_name_taken', 'agent_not_ready')
SETTLE_BOUND = int(os.environ.get('HERD_SETTLE_SECONDS', '60'))   # after a startup dialog


def add_arguments(p):
    p.add_argument('role', help='what the worker does: [a-z][a-z0-9-]*, the start of its name')
    p.add_argument('--kind', choices=('codex', 'claude'), default='codex')
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
    panes = layout['result']['layout']['panes']
    me = next((p['rect'] for p in panes if p['pane_id'] == self_pane), None)
    if me is None:
        raise herdlib.Refusal('the lead pane %s is not in its own layout' % self_pane)
    right = [p for p in panes if p['rect']['x'] >= me['x'] + me['width']
             and p['rect']['y'] < me['y'] + me['height'] and me['y'] < p['rect']['y'] + p['rect']['height']]
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
    return ['--model', model, '--effort', effort, '--dangerously-skip-permissions', '--session-id', session_id]


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


def verify_banner(pane, model_text, effort):
    """The banner must show the model and the effort. relaylib.read_banner reads it again for up to its bound
    (relay-launch.sh shares it): after a startup dialog Claude redraws, and the pane can read blank while idle."""
    problem, text = relaylib.read_banner(pane, model_text, effort)
    if problem:
        raise herdr_failure(problem, text)


def herdr_failure(message, text):
    return herdlib.Refusal('%s (pane shows: %s)' % (message, relaylib.screen_tail(text)))


def run(a):
    self_pane = herdlib.require_herdr()
    pdir = herdlib.project_dir(a.projects, a.record_dir)
    rows = herdlib.read(pdir)
    repo = os.path.realpath(a.repo) if a.repo else (herdlib.git_toplevel(os.getcwd()) or os.path.realpath('.'))
    mode = 'builder' if a.builder else 'readonly'
    if a.kind == 'claude' and mode == 'readonly':
        raise herdlib.Refusal('a Claude worker has no sandbox, so it cannot be read-only: launch it with --builder '
                              '--base <ref> (its own worktree), or give read-only work to a Codex worker')
    if mode == 'builder' and not a.base:
        raise herdlib.Refusal('--builder needs --base <ref>: the commit the worktree is cut from')
    if mode == 'builder' and herdlib.git_toplevel(repo) != repo:
        raise herdlib.Refusal('--builder needs a git repo top level, and %s is not one' % repo)
    model = a.model or DEFAULTS[a.kind][0]
    effort = a.effort or DEFAULTS[a.kind][1]
    if not model:
        session = os.environ['CLAUDE_CODE_SESSION_ID']
        model = transcript.last_model(transcript.find_transcript(session, a.projects))
        if not model:
            raise herdlib.Refusal("the lead's transcript names no model: pass --model")
    taken = {agent.get('name') for agent in relaylib.herdr_list('agents', 'agent', 'list')}
    try:
        lid, name = herdlib.new_name(a.role, effort, rows, taken)
    except ValueError as e:
        raise herdlib.Refusal(str(e))
    session_id = str(uuid.uuid4()) if a.kind == 'claude' else None
    worktree = branch = None
    created_pane = None
    cwd = repo
    try:
        if mode == 'builder':
            worktree = os.path.join(repo, '.claude', 'worktrees', name)
            branch = '%s/%s-%s' % (a.type, name, datetime.date.today().strftime('%Y%m%d'))
            git('-C', repo, 'worktree', 'add', worktree, '-b', branch, a.base)
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
            pane = created_pane = split['result']['pane']['pane_id']
        started_at = herdlib.now_iso()   # a Codex session file is stamped with its start, before this row's `at`
        for _ in range(3):
            ok, out = relaylib.start_agent(name, a.kind, pane, agent_args(a.kind, mode, model, effort, cwd,
                                                                           session_id), stop_on=STOP_ON)
            if ok or relaylib.error_code(out) != 'agent_name_taken':
                break
            taken.add(name)   # a live agent elsewhere got the name first: a new launch id and name
            lid, name = herdlib.new_name(a.role, effort, rows, taken)
        if not ok and relaylib.error_code(out) == 'agent_not_ready':
            answer_startup_dialog(a.kind, pane, cwd)
            agent = (relaylib.herdr_json('agent', 'get', pane).get('result') or {}).get('agent') or {}
            if agent.get('name') != name:
                relaylib.herdr_text('agent', 'rename', pane, name)
        elif not ok:
            raise herdlib.Refusal('agent start failed: %s' % out)
        verify_banner(pane, relaylib.banner_model(a.kind, model), effort)
        agent = (relaylib.herdr_json('agent', 'get', pane).get('result') or {}).get('agent') or {}
        session_id = (agent.get('agent_session') or {}).get('value') or session_id
        row = herdlib.append(pdir, {
            'type': 'launch', 'launch_id': lid, 'name': name, 'pane_id': pane, 'kind': a.kind, 'model': model,
            'effort': effort, 'mode': mode, 'cwd': cwd, 'worktree': worktree, 'branch': branch,
            'session_id': session_id, 'lead_session': os.environ.get('CLAUDE_CODE_SESSION_ID'), 'adopted': False,
            'started_at': started_at})
    except (herdlib.Refusal, relaylib.HerdrError):
        undo(created_pane, repo, worktree, branch, a.base)
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

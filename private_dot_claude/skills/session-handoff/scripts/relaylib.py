"""Relay facts shared by relay-check.py, relay-gate.py and herd.py: the safe-point blockers, this session's
relays, lead names, and bounded herdr calls (reads, agent start, the banner check).

Stdlib only. The CLIs run under `python3 -I` and put this directory on sys.path before importing it.
relay-launch.sh runs it as a script: `start-agent` and `check-banner` (see main()).
"""
import datetime
import glob
import hashlib
import json
import os
import re
import subprocess
import sys
import time

GIT_BUSY = ('MERGE_HEAD', 'CHERRY_PICK_HEAD', 'REVERT_HEAD', 'rebase-merge', 'rebase-apply')
# Piece 1 waits at most 20 minutes for a receipt and 15 per fix round, and each wait starts from a fresh file
# (launch.json, fix-<round>): a relay dir with no activity for longer is abandoned.
ABANDONED_AFTER = 25 * 60
ACTIVITY = ('checklist.json', 'launch.json', 'receipt.json', 'fix-*', 'fired/*')
GIT_BOUND = 2   # seconds: the gate runs git on the Stop path, inside its 7 s budget
NAME_ROOM = 32 - len('lead-') - len('-next')   # herdr names are at most 32 characters
HASH_LEN = 4   # hex chars of the repo path, appended only when the slug must be cut


def slug(repo, override=None):
    text = override or os.path.basename(os.path.abspath(repo).rstrip('/'))
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-') or 'project'


def lead_name(repo, suffix=None, override=None):
    """lead-<slug>[-<suffix>]: what `relay-check.py name` prints.

    A slug that fits in NAME_ROOM is unchanged. One that must be cut is the cut slug, a hyphen, and the first
    4 hex characters of sha256(realpath of the repo top level), so two repos that share a prefix do not share
    a name. `-next` still fits inside herdr's 32-character limit `[a-z][a-z0-9_-]{0,31}`."""
    text = slug(repo, override)
    if len(text) <= NAME_ROOM:
        base = 'lead-' + text
    else:
        cut = text[:NAME_ROOM - 1 - HASH_LEN].rstrip('-')
        tag = hashlib.sha256(os.path.realpath(repo).encode()).hexdigest()[:HASH_LEN]
        base = 'lead-' + cut + '-' + tag
    return base + ('-' + suffix if suffix else '')


def write_lead(path, session_id, pane_id, name, relay_id, since=None):
    """Atomically write relay/lead.json in the shape relay-close.sh records.

    Keys, in order: session_id, pane_id, name (null when empty), since (UTC ISO with a numeric offset, as
    relay-close.sh stamps it), relay_id (null when this naming is not a relay). A stale file at path is replaced."""
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    since = since or datetime.datetime.now(datetime.timezone.utc).isoformat()
    data = {'session_id': session_id, 'pane_id': pane_id, 'name': name or None, 'since': since,
            'relay_id': relay_id}
    tmp = '%s.tmp.%d' % (path, os.getpid())
    try:
        with open(tmp, 'w') as fh:
            json.dump(data, fh, indent=1)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def run(cmd, timeout=GIT_BOUND):
    """(exit code, stripped stdout); (None, '') when cmd does not finish within timeout seconds."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, ''
    return r.returncode, r.stdout.strip()


def blockers(repo, tasks):
    """Why a relay may not start now: an agent or workflow running inside this session (tasks are
    transcript.open_tasks records), or the repo mid-merge, rebase, cherry-pick or revert.

    A git that fails or does not answer within GIT_BOUND cannot tell: it adds no line."""
    out = ['%s %s is running inside this session (%s)' % (t['kind'], t['id'], t['description'] or t['command'][:60])
           for t in tasks if t['kind'] in ('agent', 'workflow')]
    code, gitdir = run(['git', '-C', repo, 'rev-parse', '--absolute-git-dir'])
    if code == 0:
        out += ['git is mid-operation (%s present)' % name for name in GIT_BUSY
                if os.path.exists(os.path.join(gitdir, name))]
    return out


def read_json(path):
    with open(path) as fh:
        return json.load(fh)


def _mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


def _failure(path):
    """stage and reason of a failed.json; an unreadable one is a failure with neither."""
    try:
        data = read_json(path)
    except (OSError, ValueError):
        data = None
    data = data if isinstance(data, dict) else {}
    stage, reason = data.get('stage'), data.get('reason')
    return (stage if isinstance(stage, str) else None), (reason if isinstance(reason, str) else None)


def classify(rdir, now):
    """One relay dir, by fact: closed, failed, abandoned, frozen or in_progress.

    A later closed.json supersedes a failed.json. A failed.json beside handover.md is a hand-over failure whatever
    stage it names (the stage is written free-form). The failure time is failed.json's mtime (both writers make one;
    its `at` field is free-form and never parsed), or the last activity of an abandoned dir."""
    entry = {'id': os.path.basename(rdir), 'dir': rdir, 'state': None, 'stage': None, 'reason': None,
             'failed_at': None, 'handover_at': None}
    failed = os.path.join(rdir, 'failed.json')
    handover = os.path.join(rdir, 'handover.md')
    if os.path.exists(os.path.join(rdir, 'closed.json')):
        entry['state'] = 'closed'
    elif os.path.exists(failed):
        entry['state'], entry['failed_at'] = 'failed', _mtime(failed)
        entry['stage'], entry['reason'] = _failure(failed)
        if os.path.exists(handover):
            entry['stage'] = 'handover'
    elif os.path.exists(handover):
        entry['state'], entry['handover_at'] = 'frozen', _mtime(handover)
    else:
        times = [t for pattern in ACTIVITY for path in glob.glob(os.path.join(glob.escape(rdir), pattern))
                 if (t := _mtime(path)) is not None]
        newest = max(times) if times else None
        if newest is None or now - newest >= ABANDONED_AFTER:
            entry['state'], entry['failed_at'] = 'abandoned', newest if newest is not None else now
        else:
            entry['state'] = 'in_progress'
    return entry


def relays_of(project_dir, session_id, now=None):
    """The relay dirs under <project_dir>/relay/ whose checklist names this session as the predecessor."""
    now = time.time() if now is None else now
    out = []
    for path in sorted(glob.glob(os.path.join(glob.escape(project_dir), 'relay', '*', 'checklist.json'))):
        try:
            chk = read_json(path)
        except (OSError, ValueError):
            continue
        pred = chk.get('predecessor') if isinstance(chk, dict) else None
        if isinstance(pred, dict) and pred.get('session_id') == session_id:
            out.append(classify(os.path.dirname(path), now))
    return out


def will_repeat(entry):
    """A failure an automatic retry would meet again: an identity mismatch at the check, or a taken agent name."""
    reason = entry.get('reason') or ''
    return 'agent_name_taken' in reason or (entry.get('stage') == 'check' and 'identity:' in reason)


# Seconds for one herdr call; agent start and prompt --wait pass their own bound. RELAYLIB_HERDR_BOUND overrides it:
# the tests' fake herdr is a script, and on a loaded machine its start alone once took over 10 s.
HERDR_BOUND = float(os.environ.get('RELAYLIB_HERDR_BOUND') or 10)
# Seconds a banner check reads a pane again while it does not show the banner: a pane fresh from a start or a startup
# dialog can read blank while the agent draws. One read failed 2 of 8 relay launches at load ~35-48 (2026-10-14).
# RELAYLIB_BANNER_SECONDS overrides it (tests).
BANNER_BOUND = float(os.environ.get('RELAYLIB_BANNER_SECONDS') or 10)


class HerdrError(Exception):
    """A herdr call failed: recording it as an empty answer would hand over a herd with no workers.

    code: herdr's error code (agent_not_found, agent_pane_busy, ...) when its stderr carried one, else None."""

    def __init__(self, message, code=None):
        super().__init__(message)
        self.code = code


def error_code(text):
    """The `error.code` of herdr's JSON error answer, or None."""
    try:
        data = json.loads(text)
    except ValueError:
        return None
    error = data.get('error') if isinstance(data, dict) else None
    code = error.get('code') if isinstance(error, dict) else None
    return code if isinstance(code, str) else None


def herdr_text(*args, timeout=HERDR_BOUND):
    """herdr's stdout, or HerdrError naming the command and echoing herdr's stderr."""
    cmd = ' '.join(['herdr', *args])
    try:
        r = subprocess.run(['herdr', *args], capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        raise HerdrError('%s did not answer within %s s' % (cmd, timeout))
    except OSError as e:
        raise HerdrError('%s: %s' % (cmd, e))
    if r.returncode != 0:
        raise HerdrError('%s exited %d: %s' % (cmd, r.returncode, ' '.join(r.stderr.split()) or '(no stderr)'),
                         error_code(r.stderr))
    return r.stdout


def herdr_json(*args, timeout=HERDR_BOUND):
    """herdr's JSON answer, or HerdrError."""
    out = herdr_text(*args, timeout=timeout)
    try:
        data = json.loads(out)
    except ValueError:
        data = None
    if not isinstance(data, dict):
        raise HerdrError('%s printed no JSON object: %s' % (' '.join(['herdr', *args]), ' '.join(out.split())[:200]))
    return data


def herdr_list(key, *args, timeout=HERDR_BOUND):
    """herdr's result.<key> list, or HerdrError: a listing of another shape is not an empty herd."""
    result = herdr_json(*args, timeout=timeout).get('result')
    items = result.get(key) if isinstance(result, dict) else None
    if not isinstance(items, list):
        raise HerdrError('%s: result.%s is not a list (herdr answered %s)'
                         % (' '.join(['herdr', *args]), key, json.dumps(result)[:200]))
    return items


def start_agent(name, kind, pane, args, busy_wait=15, attempts=2, timeout_ms=90000, stop_on=(), log=None,
                progress=None):
    """`herdr agent start` with the retries relay-launch.sh and herd.py share: up to `attempts` attempts; inside
    one, an agent_pane_busy answer (a pane fresh from a split whose shell is not ready yet) is retried every second
    for up to busy_wait seconds. An answer carrying a code in stop_on ends the start at once.

    Returns (True, '') once herdr reports the agent ready, else (False, herdr's last answer on one line).
    progress, when supplied, receives (attempt count, last error) before each attempt and after each error;
    the launcher can retain that count even when a signal interrupts a later attempt."""
    out = ''
    for attempt in range(1, attempts + 1):
        if progress:
            progress(attempt, out)
        began = time.monotonic()
        while True:
            try:
                r = subprocess.run(['herdr', 'agent', 'start', name, '--kind', kind, '--pane', pane,
                                    '--timeout', str(timeout_ms), '--', *args],
                                   capture_output=True, text=True, timeout=timeout_ms / 1000 + 30)
            except subprocess.TimeoutExpired:
                out = 'herdr agent start did not answer within %d s' % (timeout_ms / 1000 + 30)
                if progress:
                    progress(attempt, out)
                break
            if r.returncode == 0:
                return True, ''
            out = ' '.join((r.stderr or r.stdout).split())
            if progress:
                progress(attempt, out)
            code = error_code(r.stderr)
            if code in stop_on:
                return False, out
            if code != 'agent_pane_busy' or time.monotonic() - began >= busy_wait:
                break
            time.sleep(1)
        if log:
            log('start attempt %d failed: %s' % (attempt, out))
    return False, out


def banner_model(kind, model):
    """The model as the agent's banner names it: Claude shows 'claude-opus-5-5' as 'Opus 5.5'; Codex shows its
    model id (in another case: 'GPT-6.1-Sol'); opencode shows 'gpt-6.1-sol' as 'GPT-6.1 Sol'."""
    if kind == 'claude':
        parts = model.removeprefix('claude-').split('-')
        return parts[0].capitalize() + ' ' + '.'.join(parts[1:])
    if kind == 'opencode':
        head, _, tail = model.rpartition('-')
        return '%s %s' % (head, tail) if head else model
    return model


def banner_problem(text, model_text, effort):
    """Why a banner does not show model_text (any case) and effort (a whole word, so 'high' is not found in
    'xhigh'), or None. An empty effort is not checked."""
    if model_text.lower() not in text.lower():
        return "banner does not show model '%s'" % model_text
    word = r'(?<![A-Za-z0-9_])' + re.escape(effort) + r'(?![A-Za-z0-9_])'
    if effort and not re.search(word, text, re.IGNORECASE):
        return "banner does not show effort '%s'" % effort
    return None


def read_banner(pane, model_text, effort, bound=None):
    """Read the pane until its banner shows model_text and effort, again every second for up to bound seconds
    (default BANNER_BOUND). Returns (None, text) once shown, else (the last problem, the last text read).
    A failed read raises HerdrError at once: only a readable pane is read again."""
    deadline = time.monotonic() + (BANNER_BOUND if bound is None else bound)
    while True:
        text = herdr_text('pane', 'read', pane, '--source', 'visible')
        problem = banner_problem(text, model_text, effort)
        if not problem or time.monotonic() >= deadline:
            return problem, text
        time.sleep(1)


class DialogError(Exception):
    """Claude's startup screen was not the folder-trust dialog, or the dialog did not settle."""


TRUST_OPTION = 'Yes, I trust this folder'
TRUST_YES = re.compile(r'❯\s*(?:\d+\.\s*)?Yes, I trust this folder')


def _screen(pane):
    """What the pane shows: its viewport, then the bottom buffer. A dialog in a short pane can sit below the
    viewport's top lines, and the bottom buffer alone can miss its header."""
    return (herdr_text('pane', 'read', pane, '--source', 'visible') + '\n'
            + herdr_text('pane', 'read', pane, '--source', 'detection'))


def answer_claude_trust(pane, cwd, settle_bound=None):
    """Answer Claude's folder-trust dialog and wait until the agent is idle or done.

    The dialog preselects "No, exit". cwd is the folder this launch chose (the repo, a worktree it just created,
    or a pane already in that folder), so the dialog can only be about cwd. DialogError when the screen is a
    different block, Yes does not select, or the agent does not settle. A herdr failure raises HerdrError.
    HERD_SETTLE_SECONDS bounds the wait (default 60), the same knob herd.py launch uses."""
    bound = int(os.environ.get('HERD_SETTLE_SECONDS', '60')) if settle_bound is None else settle_bound
    text = _screen(pane)
    if TRUST_OPTION not in text:
        raise DialogError('Claude is blocked at startup on something other than the trust dialog for %s '
                          '(pane shows: %s)' % (cwd, screen_tail(text)))
    herdr_text('agent', 'send-keys', pane, 'down')
    text = _screen(pane)
    if not TRUST_YES.search(text):
        raise DialogError('the trust dialog did not select "Yes, I trust this folder" (pane shows: %s)'
                          % screen_tail(text))
    herdr_text('agent', 'send-keys', pane, 'enter')
    # Not `agent wait`: it returns on the first settled state, and the pane is still blocked until the key lands.
    deadline = time.monotonic() + bound
    while True:
        agent = (herdr_json('agent', 'get', pane).get('result') or {}).get('agent') or {}
        if agent.get('agent_status') in ('idle', 'done'):
            return
        if time.monotonic() >= deadline:
            raise DialogError('the agent is still %s %d s after its startup dialog (pane shows: %s)'
                              % (agent.get('agent_status'), bound, screen_tail(text)))
        time.sleep(1)


def screen_tail(text, lines=3):
    """The last non-blank lines of a pane read, joined on one line: what a failure shows of the screen."""
    return ' | '.join([line.strip() for line in text.splitlines() if line.strip()][-lines:])


def _write_start_report(path, attempts, error):
    if not path:
        return
    with open(path + '.tmp', 'w') as fh:
        json.dump({'attempts': attempts, 'last_error': error}, fh)
    os.replace(path + '.tmp', path)


def _parse_start(argv):
    """(name, kind, pane, busy, report, cwd, args) for a start-agent invocation, or None."""
    if argv[:1] != ['start-agent'] or len(argv) < 6:
        return None
    name, kind, pane, busy = argv[1:5]
    rest = list(argv[5:])
    report = cwd = None
    while rest and rest[0] != '--':
        flag = rest.pop(0)
        if flag not in ('--report', '--cwd') or not rest:
            return None
        value = rest.pop(0)
        if flag == '--report':
            report = value
        else:
            cwd = value
    if not rest or rest[0] != '--':
        return None
    return name, kind, pane, busy, report, cwd, rest[1:]


def main(argv):
    """relay-launch.sh's entry points:
      start-agent NAME KIND PANE BUSY_WAIT [--report PATH] [--cwd PATH] -- ARGS...
                                                       exit 0 started, 1 not; report: attempts, last_error
                                                       a Claude start answered agent_not_ready is the folder-trust
                                                       dialog: answered (cwd is the folder this launch chose), not retried
      check-banner PANE KIND MODEL [EFFORT]             exit 0 shown (read again for up to BANNER_BOUND s),
                                                        1 with the reason and the screen's tail on stdout"""
    parsed = _parse_start(argv)
    if parsed:
        name, kind, pane, busy, report, cwd, args = parsed

        def progress(attempts, error, _report=report):
            _write_start_report(_report, attempts, error)

        stop_on = ('agent_not_ready',) if kind == 'claude' else ()
        ok, out = start_agent(name, kind, pane, args, busy_wait=int(busy), stop_on=stop_on, progress=progress,
                              log=lambda line: print('relay-launch: ' + line, file=sys.stderr))
        if ok:
            return 0
        if kind == 'claude' and error_code(out) == 'agent_not_ready':
            try:
                answer_claude_trust(pane, cwd or 'the launch folder')
                agent = (herdr_json('agent', 'get', pane).get('result') or {}).get('agent') or {}
                if agent.get('name') != name:
                    herdr_text('agent', 'rename', pane, name)
            except (DialogError, HerdrError) as e:
                progress(1, str(e))
                print('relay-launch: ' + str(e), file=sys.stderr)
                return 1
            return 0
        return 1
    if argv[:1] == ['check-banner'] and len(argv) in (4, 5):
        pane, kind, model = argv[1:4]
        try:
            problem, text = read_banner(pane, banner_model(kind, model), argv[4] if len(argv) == 5 else '')
        except HerdrError:
            print('could not read the new pane')
            return 1
        if problem:
            print('%s (pane shows: %s)' % (problem, screen_tail(text)))
        return 1 if problem else 0
    print(main.__doc__, file=sys.stderr)
    return 2


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))

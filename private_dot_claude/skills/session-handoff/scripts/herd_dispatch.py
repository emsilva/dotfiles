"""dispatch: send an idle worker one brief by file, confirm it arrived, read back its session, record it.

One line, at most 700 characters (Claude takes 850+ as a paste). --reset sends /new (Codex) or /clear (Claude)
first. Delivery is confirmed in the worker's own transcript (Claude) or session file (Codex), and a lost prompt
is sent once more. A Codex session id is read from herdr and from the new session file, cross-checked.
"""
import glob
import hashlib
import json
import os
import re
import time

import herd_launch
import herdlib
import relaylib
import transcript

LIMIT = 700
CONFIRM_BOUND = int(os.environ.get('HERD_CONFIRM_SECONDS', '60'))
RESEND_AFTER = int(os.environ.get('HERD_RESEND_SECONDS', '15'))
RESETS = {'new': 'codex', 'clear': 'claude'}
NEW_WHERE = 'Where should the new conversation run?'
KEEP_HERE = re.compile(r'›\s*1\.\s*Use current Git worktree')
WAIT = 'python3 -I ~/.claude/skills/session-handoff/scripts/herd.py wait'


def add_arguments(p):
    p.add_argument('name', help='the worker, as herd.py status names it')
    p.add_argument('--brief', required=True, help='the self-contained brief file')
    p.add_argument('--deliverable', required=True, help='the file the worker delivers')
    p.add_argument('--blocked', help='where the worker writes a question; default BLOCKED.md beside the deliverable')
    p.add_argument('--reset', choices=sorted(RESETS), help='new (Codex) or clear (Claude) before the brief')


def dispatch_line(brief, sha, deliverable, blocked):
    return ('Read and execute %s (sha256 %s). Deliver %s, reply with its path and sha256, then end your turn. '
            'For a ruling, write %s and end your turn.' % (brief, sha[:16], deliverable, blocked))


def sha256(path):
    with open(path, 'rb') as fh:
        return hashlib.file_digest(fh, 'sha256').hexdigest()


def codex_home():
    return os.environ.get('CODEX_HOME') or os.path.expanduser('~/.codex')


def rollouts():
    return set(glob.glob(os.path.join(glob.escape(codex_home()), 'sessions', '**', 'rollout-*.jsonl'),
                         recursive=True))


def session_meta(path):
    """The payload of a rollout's first line (session_meta), or None."""
    try:
        with open(path) as fh:
            first = json.loads(fh.readline())
    except (OSError, ValueError):
        return None
    if not isinstance(first, dict) or first.get('type') != 'session_meta':
        return None
    payload = first.get('payload')
    return payload if isinstance(payload, dict) else None


def holds_prompt(path, line, offset=0, kind='codex'):
    """The file records line as a user prompt in bytes appended after offset."""
    try:
        with open(path, 'rb') as fh:
            fh.seek(offset)
            for raw in fh:
                try:
                    rec = json.loads(raw)
                except ValueError:
                    continue
                if not isinstance(rec, dict):
                    continue
                if kind == 'claude':
                    if (rec.get('type') == 'user' and (rec.get('origin') or {}).get('kind') == 'human'
                            and line in transcript._user_text(rec)):
                        return True
                    if (rec.get('type') == 'queue-operation' and rec.get('operation') == 'enqueue'
                            and not transcript._is_notice(str(rec.get('content', '')))
                            and line in str(rec.get('content', ''))):
                        return True
                    continue
                payload = rec.get('payload')
                if (rec.get('type') == 'response_item' and isinstance(payload, dict)
                        and payload.get('type') == 'message' and payload.get('role') == 'user'
                        and any(line in (c.get('text') or '') for c in payload.get('content') or []
                                if isinstance(c, dict))):
                    return True
    except OSError:
        return False
    return False


def own_thread(meta):
    """The worker's own thread, not a subagent it spawned (same cwd, written after the prompt)."""
    return meta.get('thread_source', 'user') == 'user' and not meta.get('parent_thread_id')


def codex_candidates(before, cwd, not_before, claimed, line):
    """{id: path} of session files that did not exist before the prompt, for cwd, stamped at or after not_before,
    claimed by no row of the record, the worker's own thread, and holding the prompt."""
    out = {}
    for path in rollouts() - set(before):
        meta = session_meta(path)
        if not meta or meta.get('cwd') != cwd or not own_thread(meta) or meta.get('id') in claimed:
            continue
        try:
            stamped = herdlib.epoch(meta.get('timestamp') or '')
        except ValueError:
            continue
        if stamped >= not_before and holds_prompt(path, line):
            out[meta['id']] = path
    return out


def codex_file(session):
    hits = glob.glob(os.path.join(glob.escape(codex_home()), 'sessions', '**', 'rollout-*-%s.jsonl' % session),
                     recursive=True)
    return hits[0] if len(hits) == 1 else None


def herdr_session(pane):
    agent = (relaylib.herdr_json('agent', 'get', pane).get('result') or {}).get('agent') or {}
    return (agent.get('agent_session') or {}).get('value')


def arrived(launch, pane, line, known, stale, before, not_before, claimed, projects):
    """(session id, warning) once the prompt is in the worker's transcript or session file, else None.
    stale: the session a reset just ended; herdr reporting it still is no answer."""
    reported = herdr_session(pane)
    reported = None if reported == stale else reported
    if launch['kind'] == 'claude':
        session = reported or known
        try:
            path = transcript.find_transcript(session, projects) if session else None
        except LookupError:
            path = None
        if path and holds_prompt(path, line, before.get(path, 0), kind='claude'):
            return session, None
        return None
    if known:   # the session is running and was not reset: the prompt lands in its file
        path = codex_file(known)
        return (known, None) if path and holds_prompt(path, line, before.get(path, 0)) else None
    found = codex_candidates(before, launch['cwd'], not_before, claimed, line)
    if len(found) > 1:
        return None   # the per-cwd lock keeps herd dispatches apart; another Codex in cwd: wait for herdr
    if found:
        [(session, _)] = found.items()
        if reported and reported != session:
            return session, 'herdr reports session %s, the new session file says %s' % (reported, session)
        return session, None
    if reported and reported not in claimed:
        path = codex_file(reported)
        meta = session_meta(path) if path else None
        if (meta and meta.get('cwd') == launch['cwd'] and own_thread(meta) and meta.get('id') == reported
                and holds_prompt(path, line, before.get(path, 0))):
            return reported, 'no new session file passed the checks; herdr reports %s' % reported
    return None


def send(pane, text):
    """Type one prompt into the worker. herdr's agent_prompt_stalled (no lifecycle change seen within its window)
    does not mean the prompt was lost: the delivery check in the worker's own file decides."""
    try:
        relaylib.herdr_text('agent', 'prompt', pane, text)
    except relaylib.HerdrError as e:
        if e.code != 'agent_prompt_stalled':
            raise


def keep_worktree(pane):
    """In a git repo Codex's /new asks where the new conversation runs (herdr still reports the pane idle). The
    worker stays where it is: option 1, preselected, is confirmed before enter."""
    text = herd_launch.screen(pane)
    if NEW_WHERE not in text:
        return
    if not KEEP_HERE.search(text):
        raise herd_launch.herdr_failure('/new asks where to run, and "Use current Git worktree" is not selected',
                                        text)
    relaylib.herdr_text('agent', 'send-keys', pane, 'enter')
    time.sleep(1)


def settle(pane, what):
    deadline = time.monotonic() + CONFIRM_BOUND
    while True:
        status = (relaylib.herdr_json('agent', 'get', pane).get('result') or {}).get('agent', {}).get('agent_status')
        if status in ('idle', 'done'):
            return
        if time.monotonic() >= deadline:
            raise herdlib.Refusal('the worker is still %s %d s after %s' % (status, CONFIRM_BOUND, what))
        time.sleep(1)


def run(a):
    herdlib.require_herdr()
    pdir = herdlib.project_dir(a.projects, a.record_dir)
    launches = herdlib.replay(herdlib.read(pdir))
    launch = herdlib.by_name(launches, a.name)
    if a.reset and RESETS[a.reset] != launch['kind']:
        raise herdlib.Refusal('--reset %s is for %s workers; %s is %s' % (a.reset, RESETS[a.reset], a.name,
                                                                           launch['kind']))
    brief = os.path.abspath(a.brief)
    if not os.path.isfile(brief):
        raise herdlib.Refusal('no brief at %s' % brief)
    deliverable = os.path.abspath(a.deliverable)
    blocked = os.path.abspath(a.blocked) if a.blocked else os.path.join(os.path.dirname(deliverable), 'BLOCKED.md')
    sha = sha256(brief)
    line = dispatch_line(brief, sha, deliverable, blocked)
    if len(line) > LIMIT:
        raise herdlib.Refusal('the line is %d characters, over %d (Claude takes 850+ as a paste); shorten the '
                              'paths: brief %d, deliverable %d, blocked %d characters'
                              % (len(line), LIMIT, len(brief), len(deliverable), len(blocked)))
    pairs, _, _ = herdlib.match(launches, herdlib.live_panes())
    pane = next((p for l, p in pairs if l is launch), None)
    if pane is None:
        raise herdlib.Refusal('%s has no live pane (lost); herd.py status shows what is there' % a.name)
    if pane.get('agent_status') not in ('idle', 'done'):
        raise herdlib.Refusal('%s is %s: dispatch only to an idle worker' % (a.name, pane.get('agent_status')))
    pid = pane['pane_id']
    known = launch['session_id']
    # A new session file is stamped with the session's start: the launch's agent start, or the reset below.
    not_before = herdlib.epoch(launch['started_at']) if launch['started_at'] else 0
    stale = None
    if a.reset:
        stale, not_before = known, time.time() - 1
        send(pid, '/' + a.reset)
        time.sleep(2)   # Codex's post-/new splash drops a prompt sent into it
        if a.reset == 'new':
            keep_worktree(pid)
        settle(pid, '/' + a.reset)
        herd_launch.verify_banner(pid, relaylib.banner_model(launch['kind'], launch['model']), launch['effort'])
        known = herdr_session(pid) if launch['kind'] == 'claude' else None
    claimed = {l['session_id'] for l in launches.values() if l['session_id'] and l is not launch}
    claimed |= {d['session_id'] for l in launches.values() if l is not launch for d in l['dispatches']
                if d['session_id']}
    with herdlib.locked(pdir, 'herd.lock.' + hashlib.sha1(launch['cwd'].encode()).hexdigest()):
        paths = (rollouts() if launch['kind'] == 'codex' else
                 glob.glob(os.path.join(glob.escape(a.projects), '*', '*.jsonl')))
        before = {}
        try:
            for path in paths:
                try:
                    before[path] = os.path.getsize(path)
                except FileNotFoundError:
                    continue   # A file removed since discovery cannot receive this prompt.
        except OSError as e:
            raise herdlib.RecordError('cannot bound delivery to new transcript bytes: %s' % e)
        sent_at = herdlib.now_iso()
        result = None
        for attempt in (1, 2):
            send(pid, line)
            deadline = time.monotonic() + (RESEND_AFTER if attempt == 1 else CONFIRM_BOUND)
            while True:
                result = arrived(launch, pid, line, known, stale, before, not_before, claimed, a.projects)
                if result or time.monotonic() >= deadline:
                    break
                time.sleep(1)
            if result:
                break
    if result is None:
        raise herdlib.Refusal('the brief did not reach %s (sent twice; its %s holds no such prompt)'
                              % (a.name, 'transcript' if launch['kind'] == 'claude' else 'session file'))
    session, warning = result
    row = {'type': 'dispatch', 'launch_id': launch['launch_id'],
           'seq': max([d['seq'] for d in launch['dispatches']] or [0]) + 1, 'brief': brief, 'brief_sha256': sha,
           'deliverable': deliverable, 'blocked': blocked, 'reset': a.reset, 'sent_at': sent_at,
           'session_id': session}
    if warning:
        row['session_warning'] = warning
    row = herdlib.append(pdir, row)
    print(json.dumps(dict(row, wait=WAIT)))
    return 0

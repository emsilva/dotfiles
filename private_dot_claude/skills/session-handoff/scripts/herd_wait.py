"""wait: the herd's one waiter; exits on the first event of any open dispatch not yet closed.

Run it with the Bash tool's run_in_background (never nohup or &: only such a task wakes the session). Events:
deliverable (written after the dispatch, worker idle on 2 polls, and no background job open in the worker),
blocked (BLOCKED file written after it), status=blocked (the worker blocked for 4 polls), status=gone (no live
pane). Prints `<name> <event> <path>`. A deliverable or BLOCKED.md records a `reported` row and closes the
dispatch; a status= event is printed and does not, so a re-armed wait still has it. With --fired-dir touches
<dir>/<marker>. An event another waiter recorded for a dispatch this one watches fires here too (a relay's two
waiters on one worker).
"""
import os
import sys
import time

import herdlib
import relaylib
import transcript

DELIVERED_POLLS = 2
BLOCKED_POLLS = 4
CLOSES_DISPATCH = ('deliverable', 'blocked')


def add_arguments(p):
    p.add_argument('--marker', help="a plain argument relay-check.py compare finds in the process list")
    p.add_argument('--fired-dir', help='touch <dir>/<marker> when the waiter fires')
    p.add_argument('--names', nargs='+', help='watch only these workers')
    p.add_argument('--interval', type=float, default=30.0, help='seconds between polls (default 30)')


def fresh(path, dispatch):
    """path was written after the dispatch was sent."""
    try:
        return os.path.getmtime(path) > herdlib.epoch(dispatch['sent_at'])
    except OSError:
        return False


def pending(launches, names):
    """{(launch_id, seq): (launch, dispatch)} for each open launch's latest dispatch not yet reported."""
    out = {}
    for launch in herdlib.open_launches(launches):
        d = herdlib.latest(launch)
        if d and d['seq'] not in launch['reported'] and (not names or launch['name'] in names):
            out[(launch['launch_id'], d['seq'])] = (launch, d)
    return out


def background_open_claude(launch, projects):
    """True when the worker's transcript still has an open background task.

    No session id, or a transcript that cannot be read, is not done: a failed read is not proof the job
    finished. The session id is the one the herd record keeps, the same lookup bg-tasks.py uses.
    """
    session = launch.get('session_id')
    if not session:
        return None
    path = transcript.find_transcript(session, projects)
    return bool(transcript.open_tasks([path]))


def background_open_opencode(launch, projects):
    """Today's behaviour: a settled worker may count as done.

    Measured 2026-10-26 on opencode v2.0.32: `opencode session export` omits a shell tool whose live session
    row has state.status running, so the export does not mark a running shell. `opencode export <id>` is not a
    command. Do not treat that missing signal as an open job, and do not call the export on each poll.
    """
    return False


def background_open_codex(launch, projects):
    """No pane-footer scrape in this change (it needs fixtures captured from real panes). Today's behaviour."""
    return False


def background_open_grok(launch, projects):
    """No pane-footer scrape in this change (it needs fixtures captured from real panes). Today's behaviour."""
    return False


BACKGROUND_OPEN = {
    'claude': background_open_claude,
    'opencode': background_open_opencode,
    'codex': background_open_codex,
    'grok': background_open_grok,
}


def background_open(launch, projects):
    """True when a background job is open, False when none is, None when the read failed (keep waiting).

    A kind with no hook has no signal: today's behaviour, a settled worker may count as done. A hook that
    raises is a failed read, not proof the job finished.
    """
    hook = BACKGROUND_OPEN.get(launch.get('kind'))
    if hook is None:
        return False
    try:
        return hook(launch, projects)
    except Exception:
        return None


def fire(a, pdir, launch, seq, event, path, record=True):
    if record and event in CLOSES_DISPATCH:
        herdlib.append(pdir, {'type': 'reported', 'launch_id': launch['launch_id'], 'seq': seq, 'event': event})
    print('%s %s %s' % (launch['name'], event, path))
    if a.fired_dir:
        os.makedirs(a.fired_dir, exist_ok=True)
        open(os.path.join(a.fired_dir, a.marker), 'a').close()
    return 0


def run(a):
    if a.fired_dir and not a.marker:
        raise herdlib.Refusal('--fired-dir needs --marker: the fired file is named after it')
    herdlib.require_herdr()
    pdir = herdlib.project_dir(a.projects, a.record_dir)
    watched = pending(herdlib.replay(herdlib.read(pdir)), a.names)
    if not watched:
        raise herdlib.Refusal('nothing to wait on: no open dispatch without a report%s'
                              % (' among %s' % ', '.join(a.names) if a.names else ''))
    delivered, blocked = {}, {}
    while True:
        launches = herdlib.replay(herdlib.read(pdir))
        for key, (launch, d) in list(watched.items()):
            now = launches[launch['launch_id']]
            latest = herdlib.latest(now)
            if now['closed'] is not None or latest is None or latest['seq'] != d['seq']:
                del watched[key]
                delivered.pop(key, None)
                blocked.pop(key, None)
                continue
            event = now['reported'].get(d['seq'])
            if event:   # another waiter got there first: still this waiter's event
                path = (d['blocked'] if event == 'blocked' else now['pane_id'] if event.startswith('status=')
                        else d['deliverable'])
                return fire(a, pdir, now, d['seq'], event, path, record=False)
        watched.update(pending(launches, a.names))
        if not watched:
            raise herdlib.Refusal('nothing left to wait on: watched dispatches were closed, superseded or reported')
        try:
            pairs, _, _ = herdlib.match(launches, herdlib.live_panes())
        except relaylib.HerdrError as e:   # a failed read says nothing about the herd: poll again
            print('herd wait: %s' % e, file=sys.stderr)
            time.sleep(a.interval)
            continue
        panes = {launch['launch_id']: pane for launch, pane in pairs}
        for key, (launch, d) in watched.items():
            pane = panes.get(launch['launch_id'])
            status = pane.get('agent_status') if pane else None
            current = launches.get(launch['launch_id'], launch)
            ready = False
            if fresh(d['deliverable'], d) and status in ('idle', 'done'):
                ready = background_open(current, a.projects) is False
            delivered[key] = delivered.get(key, 0) + 1 if ready else 0
            blocked[key] = blocked.get(key, 0) + 1 if status == 'blocked' else 0
            if delivered[key] >= DELIVERED_POLLS:
                return fire(a, pdir, launch, d['seq'], 'deliverable', d['deliverable'])
            if fresh(d['blocked'], d):
                return fire(a, pdir, launch, d['seq'], 'blocked', d['blocked'])
            if blocked[key] >= BLOCKED_POLLS:
                return fire(a, pdir, launch, d['seq'], 'status=blocked', pane['pane_id'])
            if pane is None:
                return fire(a, pdir, launch, d['seq'], 'status=gone', launch['pane_id'])
        time.sleep(a.interval)

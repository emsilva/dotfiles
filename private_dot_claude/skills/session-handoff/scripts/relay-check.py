#!/usr/bin/env python3
"""Relay checklist, receipt comparison, quiet check and lead names.

  name      [--repo DIR] [--suffix S] [--slug SLUG]   print lead-<slug>[-<S>]
  identity                                          this session's identity, as JSON
  checklist --note PATH [--extra-root DIR ...] [--transcript PATH ...]
                                                    write <enc>/relay/<id>/checklist.json; print the dir
  compare   <relay-dir>                             receipt.json vs checklist.json: PASS or one FAIL per line
  quiet     <relay-dir>                             exit 1 if a prompt reached the predecessor after handover.md

Run as python3 -I. checklist and identity read $CLAUDE_CODE_SESSION_ID, $CLAUDE_EFFORT,
$CLAUDE_PID and $HERDR_PANE_ID of the session that runs them.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys

# In development this dir is chezmoi source: bytecode written beside the script would be deployed.
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import herdlib  # noqa: E402
import relaylib  # noqa: E402
from relaylib import HerdrError, herdr_json  # noqa: E402
import transcript  # noqa: E402

NAME_ROOM = 32 - len('lead-') - len('-next')   # herdr names are at most 32 characters


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, r.stdout.strip()


def slug(repo, override=None):
    text = override or os.path.basename(os.path.abspath(repo).rstrip('/'))
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-') or 'project'


def lead_name(repo, suffix=None, override=None):
    base = 'lead-' + slug(repo, override)[:NAME_ROOM].rstrip('-')
    return base + ('-' + suffix if suffix else '')


def sha256(path):
    with open(path, 'rb') as fh:
        return hashlib.file_digest(fh, 'sha256').hexdigest()


def settings_mode():
    """The user's own default permission mode (~/.claude/settings.json), else 'default'.

    Used only when the transcript has no permission-mode record. The repo's .claude/settings*.json
    are never read: they arrive with the repo, and bypassPermissions there would launch the relayed
    successor with --dangerously-skip-permissions. Only the observed runtime mode or the user's own
    settings may grant that.
    """
    try:
        mode = json.load(open(os.path.expanduser('~/.claude/settings.json'))).get('permissions', {}).get('defaultMode')
    except (OSError, ValueError, AttributeError):
        mode = None
    return mode or 'default'


def repo_root():
    code, top = run(['git', 'rev-parse', '--show-toplevel'])
    return top if code == 0 and top else os.getcwd()


def git_state(repo):
    _, head = run(['git', '-C', repo, 'rev-parse', '--short', 'HEAD'])
    _, branch = run(['git', '-C', repo, 'rev-parse', '--abbrev-ref', 'HEAD'])
    # Not run(): its strip() would eat the leading space of " M path" and line[3:] would cut the path.
    porcelain = subprocess.run(['git', '-C', repo, 'status', '--porcelain'], capture_output=True, text=True).stdout
    return {'head': head, 'branch': branch, 'dirty': [line[3:] for line in porcelain.splitlines() if line]}


def herd_lists(pdir, repo, extra_roots, self_pane):
    """The checklist's herd (version 2), from the record joined with live panes: workers (open launches with a
    live pane, each with its latest dispatch), unclassified (live panes in scope matching no open launch) and
    lost (open launches with no live pane). Outside herdr there is no herd to read."""
    if not self_pane:
        return [], [], []
    got = herdlib.herd(pdir, repo, extra_roots, self_pane)
    workers = []
    for launch, pane in got['workers']:
        d = herdlib.latest(launch)
        workers.append({
            'launch_id': launch['launch_id'], 'name': launch['name'], 'pane_id': pane['pane_id'],
            'kind': launch['kind'], 'model': launch['model'], 'effort': launch['effort'],
            'status': pane.get('agent_status'), 'session_id': herdlib.session_of(pane) or launch['session_id'],
            'dispatch': {k: d[k] for k in ('seq', 'brief', 'brief_sha256', 'deliverable', 'blocked', 'sent_at')}
            if d else None})
    unclassified = [{'pane_id': p['pane_id'], 'name': p.get('name'), 'kind': p.get('agent', 'shell'),
                     'status': p.get('agent_status'), 'session_id': herdlib.session_of(p), 'cwd': p.get('cwd'),
                     'looks_like_worker': herdlib.looks_like_worker(p.get('name'))} for p in got['unclassified']]
    lost = [{'launch_id': l['launch_id'], 'name': l['name'], 'pane_id': l['pane_id'], 'session_id': l['session_id'],
             'cwd': l['cwd']} for l in got['lost']]
    return workers, unclassified, lost


def new_relay_dir(project_dir, now):
    base = os.path.join(project_dir, 'relay', now.strftime('%Y%m%dT%H%M%SZ'))
    path, n = base, 1
    while True:
        try:
            os.makedirs(path)
            return path
        except FileExistsError:
            n += 1
            path = '%s-%d' % (base, n)


def own_transcript(a):
    session = os.environ.get('CLAUDE_CODE_SESSION_ID')
    if not session:
        sys.exit('relay-check: CLAUDE_CODE_SESSION_ID is not set; run this inside the Claude session')
    return session, transcript.find_transcript(session, a.projects)


def cmd_name(a):
    print(lead_name(a.repo, a.suffix, a.slug))
    return 0


def claude_pid():
    pid = os.environ.get('CLAUDE_PID', '')
    return int(pid) if pid.isdigit() else None


def cmd_identity(a):
    session, tpath = own_transcript(a)
    print(json.dumps({'session_id': session, 'pane_id': os.environ.get('HERDR_PANE_ID'),
                      'model': transcript.last_model(tpath), 'effort': os.environ.get('CLAUDE_EFFORT'),
                      'permission_mode': transcript.permission_mode(tpath) or settings_mode(),
                      'pid': claude_pid()}))
    return 0


def cmd_checklist(a):
    session, tpath = own_transcript(a)
    repo = os.path.realpath(repo_root())
    paths = a.transcript + [tpath]
    tasks = transcript.open_tasks(paths)
    blocked = relaylib.blockers(repo, tasks)
    if blocked:
        for line in blocked:
            print('relay-check: not yet: %s' % line, file=sys.stderr)
        return 3
    try:
        note = {'path': os.path.abspath(a.note), 'sha256': sha256(a.note)}
    except OSError as e:
        print('relay-check: cannot read the note: %s' % e, file=sys.stderr)
        return 2
    self_pane = os.environ.get('HERDR_PANE_ID')
    me = herdr_json('agent', 'get', self_pane).get('result', {}).get('agent', {}) if self_pane else {}
    herd_workers, unclassified, lost = herd_lists(os.path.dirname(tpath), repo, a.extra_root, self_pane)
    record = {
        'version': 2,
        'repo': repo,
        'predecessor': {
            'session_id': session, 'transcript': tpath, 'pane_id': self_pane, 'herdr_name': me.get('name'),
            'herdr_session': (me.get('agent_session') or {}).get('value'),
            'model': transcript.last_model(tpath), 'effort': os.environ.get('CLAUDE_EFFORT'),
            'permission_mode': transcript.permission_mode(tpath) or settings_mode(),
            'pid': claude_pid()},
        'git': git_state(repo),
        'note': note,
        'background_tasks': tasks,
        'crons': transcript.open_crons(paths),
        'workers': herd_workers,
        'unclassified': unclassified,
        'lost': lost,
        'recent_prompts': transcript.prompts(tpath)[-3:],
    }
    # Every read that can fail is done: only now does the relay dir exist.
    now = datetime.datetime.now(datetime.timezone.utc)
    rdir = new_relay_dir(os.path.dirname(tpath), now)
    data = dict({'relay_id': os.path.basename(rdir), 'created_at': now.isoformat().replace('+00:00', 'Z')}, **record)
    with open(os.path.join(rdir, 'checklist.json'), 'w') as fh:
        json.dump(data, fh, indent=1)
    print(rdir)
    return 0


class PsError(Exception):
    """The process list could not be read: no marker can be shown live."""


def processes():
    """One snapshot of the process table: {pid: (ppid, command line)}.

    -ww: never cut a command line at a terminal width ($COLUMNS). macOS ps prints a newline inside an
    argument as \\012, so each process is one line; a line that does not start with two numbers is skipped."""
    try:
        r = subprocess.run(['ps', '-ww', '-axo', 'pid=,ppid=,command='], capture_output=True, text=True,
                           errors='replace')
    except OSError as e:
        raise PsError('ps: %s' % e)
    if r.returncode != 0:
        raise PsError('ps exited %d: %s' % (r.returncode, ' '.join(r.stderr.split()) or '(no stderr)'))
    table = {}
    for line in r.stdout.splitlines():
        parts = line.split(None, 2)
        if len(parts) >= 2 and parts[0].isdigit() and parts[1].isdigit():
            table[int(parts[0])] = (int(parts[1]), parts[2] if len(parts) > 2 else '')
    return table


def carriers(table, marker):
    """Pids whose command line carries the whole marker: relay-R1-w1 is not satisfied by relay-R1-w10."""
    pattern = re.compile(re.escape(marker) + '([^0-9A-Za-z_-]|$)')
    return sorted(pid for pid, (_, command) in table.items() if pattern.search(command))


def descends(table, pid, ancestor):
    """pid is a (grand)child of ancestor in the snapshot. Stops at a pid the snapshot lacks, at pid 0 or 1
    (launchd/init adopts orphans: a detached waiter ends there) and on a cycle."""
    seen = set()
    while pid in table and pid not in seen:
        seen.add(pid)
        pid = table[pid][0]
        if pid == ancestor:
            return True
        if pid <= 1:
            return False
    return False


def marker_problem(relay_dir, relay_id, marker, table, successor_pid):
    """Why `marker` does not cover its item, or None.

    The marker must be this relay's (relay-<id>-w...): the predecessor's own waiters from an earlier relay are
    alive until the hand-over, and a generic string like 'while' matches anything. A waiter that already fired
    has exited; the successor's waiters leave <relay-dir>/fired/<marker> behind when they do. A live waiter
    covers its item only when it descends from the successor's claude (successor_pid): that is what a Bash
    run_in_background task is, and only such a task wakes the session when it ends. A nohup/& waiter is
    re-parented away (to launchd): it fires, but nobody is woken to act on it. table is processes()'s
    snapshot, or None when ps failed (the caller reports that once). Without a usable successor pid (missing,
    or not running: also reported once by the caller) descent cannot be checked, and a live carrier is not
    failed again here."""
    prefix = 'relay-%s-w' % relay_id
    if not (marker or '').startswith(prefix):
        return "marker %r is not this relay's (expected prefix %r)" % (marker, prefix)
    if os.path.isfile(os.path.join(relay_dir, 'fired', marker)):
        return None
    if table is None:
        return 'the process list is unreadable, so marker %r cannot be shown live, and fired/%s does not exist' % (
            marker, marker)
    pids = carriers(table, marker)
    if not pids:
        return 'no live process carries marker %r and fired/%s does not exist' % (marker, marker)
    if successor_pid is None or any(descends(table, pid, successor_pid) for pid in pids):
        return None
    return ('marker %r is carried only by a process detached from the successor (pid %s, not under successor '
            'pid %d): it cannot wake the successor; arm the waiter with run_in_background, never nohup or &'
            % (marker, ', '.join(map(str, pids)), successor_pid))


def _reason(entry):
    return bool((entry.get('reason') or '').strip())


def cmd_compare(a):
    chk = json.load(open(os.path.join(a.relay_dir, 'checklist.json')))
    try:
        rec = json.load(open(os.path.join(a.relay_dir, 'receipt.json')))
    except (OSError, ValueError) as e:
        print('FAIL receipt.json unreadable: %s' % e)
        return 1
    fails = []
    successor_pid = (rec.get('successor') or {}).get('pid')
    if not (isinstance(successor_pid, int) and not isinstance(successor_pid, bool) and successor_pid > 1):
        fails.append('receipt has no successor pid; write the successor block from relay-check.py identity'
                     + ('' if successor_pid is None else ' (it holds %r)' % (successor_pid,)))
        successor_pid = None
    try:
        table = processes()
    except PsError as e:
        fails.append('cannot read the process list: %s' % e)
        table = None
    if successor_pid is not None and table is not None and successor_pid not in table:
        # The successor died, or herdr resumed it under a new pid: no waiter can descend from this one, and
        # re-arming them would not help. Reported once; live waiters are not failed again as detached.
        fails.append('successor pid %d is not running; rewrite the successor block from relay-check.py identity'
                     % successor_pid)
        successor_pid = None
    if rec.get('relay_id') != chk.get('relay_id'):
        fails.append('relay_id %r is not %r' % (rec.get('relay_id'), chk.get('relay_id')))
    for key in ('model', 'effort', 'permission_mode'):
        want, got = chk['predecessor'].get(key), (rec.get('successor') or {}).get(key)
        if want != got:
            fails.append('identity: successor %s %r, predecessor %r' % (key, got, want))
    note = rec.get('note') or {}
    if note.get('path') != chk['note']['path']:
        fails.append('note: the successor read %r, the checklist names %r' % (note.get('path'), chk['note']['path']))
    else:
        on_disk = sha256(chk['note']['path'])
        if note.get('sha256') != on_disk:
            fails.append('note: the successor read sha256 %s, the note on disk is %s (re-read it)'
                         % (note.get('sha256'), on_disk))
    tasks = {t.get('id'): t for t in rec.get('tasks') or []}
    for t in chk.get('background_tasks', []):
        got = tasks.get(t['id'])
        label = t.get('description') or t.get('command', '')[:60]
        if not got:
            fails.append('task %s (%s) is not in the receipt' % (t['id'], label))
        elif got.get('action') == 'drop':
            if not _reason(got):
                fails.append('task %s dropped without a reason' % t['id'])
        elif got.get('action') in ('rearmed', 'watching-exit-file'):
            problem = marker_problem(a.relay_dir, chk.get('relay_id'), got.get('marker'), table, successor_pid)
            if problem:
                fails.append('task %s: %s' % (t['id'], problem))
        else:
            fails.append('task %s: unknown action %r' % (t['id'], got.get('action')))
    # A version-2 checklist names workers by launch id (pane ids change after a herdr restore); version 1 (a relay
    # started before the herd record) keeps its pane-id rules.
    key = 'launch_id' if chk.get('version') == 2 else 'pane_id'
    seen = {w.get(key): w for w in rec.get('workers') or []}
    for w in chk.get('workers', []):
        got = seen.get(w[key])
        label = w.get('name') or w.get('kind')
        if not got:
            fails.append('worker %s (%s) is not in the receipt' % (w[key], label))
        elif got.get('waiter_marker'):
            problem = marker_problem(a.relay_dir, chk.get('relay_id'), got['waiter_marker'], table, successor_pid)
            if problem:
                fails.append('worker %s: %s' % (w[key], problem))
        elif not _reason(got):
            fails.append('worker %s (%s) has neither a waiter nor a reason' % (w[key], label))
    lost = {x.get('launch_id'): x for x in rec.get('lost') or []}
    for x in chk.get('lost', []):
        if not _reason(lost.get(x['launch_id'], {})):
            fails.append('lost launch %s (%s) has no reason' % (x['launch_id'], x.get('name')))
    unclassified = {x.get('pane_id'): x for x in rec.get('unclassified') or []}
    for x in chk.get('unclassified', []):
        if x.get('looks_like_worker') and not _reason(unclassified.get(x['pane_id'], {})):
            fails.append('unclassified pane %s (%s) looks like a worker and has no reason' % (x['pane_id'], x.get('name')))
    crons = {c.get('id'): c for c in rec.get('crons') or []}
    for c in chk.get('crons', []):
        got = crons.get(c['id'], {})
        if got.get('action') != 'rearmed' and not (got.get('action') == 'drop' and _reason(got)):
            fails.append('cron %s (%s) is neither re-armed nor dropped with a reason' % (c['id'], c.get('cron')))
    fails += ['open question: %s' % q for q in rec.get('questions') or []]
    fails += ['open disagreement: %s' % d for d in rec.get('disagreements') or []]
    if rec.get('tier') not in ('clean', 'drift'):
        fails.append('tier %r is neither clean nor drift' % rec.get('tier'))
    fails += ['unexplained drift: %s' % d.get('item') for d in rec.get('drift') or []
              if not (d.get('explanation') or '').strip()]
    for line in fails:
        print('FAIL ' + line)
    if not fails:
        print('PASS')
    return 1 if fails else 0


def cmd_quiet(a):
    chk = json.load(open(os.path.join(a.relay_dir, 'checklist.json')))
    handover = os.path.join(a.relay_dir, 'handover.md')
    if not os.path.exists(handover):
        print('relay-check: no handover.md in %s yet' % a.relay_dir, file=sys.stderr)
        return 2
    after = os.path.getmtime(handover)
    # This gates closing the old lead: a prompt that cannot be dated counts as after the hand-over.
    late = [p for p in transcript.prompts(chk['predecessor']['transcript'])
            if (when := transcript.epoch(p['timestamp'])) is None or when > after]
    for p in late:
        print('prompt at %s: %s' % (p['timestamp'], p['text'][:120]))
    return 1 if late else 0


def main(argv=None):
    p = argparse.ArgumentParser(description='Relay checklist, receipt comparison, quiet check and lead names.')
    sub = p.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('name')
    s.add_argument('--repo', default='.')
    s.add_argument('--suffix')
    s.add_argument('--slug')
    sub.add_parser('identity')
    s = sub.add_parser('checklist')
    s.add_argument('--note', required=True)
    s.add_argument('--extra-root', action='append', default=[])
    s.add_argument('--transcript', action='append', default=[])
    for name in ('compare', 'quiet'):
        sub.add_parser(name).add_argument('relay_dir')
    for parser in sub.choices.values():
        parser.add_argument('--projects', default=transcript.PROJECTS, help=argparse.SUPPRESS)
    a = p.parse_args(argv)
    try:
        return {'name': cmd_name, 'identity': cmd_identity, 'checklist': cmd_checklist,
                'compare': cmd_compare, 'quiet': cmd_quiet}[a.cmd](a)
    except HerdrError as e:
        print('relay-check: herdr read failed: %s' % e, file=sys.stderr)
        return 2
    except herdlib.RecordError as e:
        print('relay-check: the herd record is unreadable: %s' % e, file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())

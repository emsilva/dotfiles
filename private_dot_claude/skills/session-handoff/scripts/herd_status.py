"""status: the herd as markdown: workers, unclassified panes in scope, lost launches (closed with --all).

Read-only: it never prompts, focuses or writes to a pane. Scope is the repo's git worktrees, every open launch's
cwd and the extra roots. herd-snapshot.sh is this command (its arguments are extra roots).
"""
import os
import sys
import time

import herdlib
import relaylib


def add_arguments(p):
    p.add_argument('roots', nargs='*', metavar='ROOT', help='extra roots, as herd-snapshot.sh takes them')
    p.add_argument('--extra-root', action='append', default=[], help='a dir outside the repo this front uses')
    p.add_argument('--all', action='store_true', help='also list closed launches')
    p.add_argument('--repo', help='default: the git top level of the current directory, else the directory')


def short(value, n=8):
    return value[:n] if value else 'unknown'


def deliverable_state(dispatch):
    """missing, stale (older than its dispatch) or new; '-' before any dispatch."""
    if not dispatch:
        return '-'
    try:
        mtime = os.path.getmtime(dispatch['deliverable'])
    except OSError:
        return 'missing'
    return 'new' if mtime >= herdlib.epoch(dispatch['sent_at']) else 'stale'


def last_event(launch):
    d = herdlib.latest(launch)
    if d is None:
        return 'launched %s' % launch['at'][:16]
    if d['seq'] in launch['reported']:
        return 'reported %s (dispatch %d)' % (launch['reported'][d['seq']], d['seq'])
    return 'dispatch %d sent %s' % (d['seq'], d['sent_at'][:16])


def shell_tail(pane):
    """A shell pane carries no command: its last visible lines are the evidence."""
    text = relaylib.herdr_text('pane', 'read', pane['pane_id'], '--source', 'visible', '--lines', '40')
    lines = [line.strip()[:120] for line in text.splitlines() if line.strip()][-2:]
    return ' / '.join(lines) or 'blank'


def cell(value):
    return ' '.join(str(value).splitlines()).replace('|', '\\|')


def table(header, rows):
    out = ['| ' + ' | '.join(header) + ' |', '|' + '---|' * len(header)]
    return out + ['| ' + ' | '.join(cell(v) for v in row) + ' |' for row in rows]


def run(a):
    if os.environ.get('HERDR_ENV') != '1':
        print('herd: not inside herdr (HERDR_ENV unset), nothing to record')
        return 0
    try:
        pdir = herdlib.project_dir(a.projects, a.record_dir)
        source = os.path.join(pdir, herdlib.RECORD)
    except herdlib.RecordError as e:
        pdir, source = None, 'none: %s' % e
    repo = os.path.realpath(a.repo) if a.repo else (herdlib.git_toplevel(os.getcwd()) or os.path.realpath('.'))
    got = herdlib.herd(pdir, repo, extra_roots=a.roots + a.extra_root, self_pane=os.environ.get('HERDR_PANE_ID'))
    print('# herd status %s' % time.strftime('%Y-%m-%dT%H:%MZ', time.gmtime()))
    print()
    print('record: %s · scope: %s' % (source, ', '.join(got['roots'])))
    print()
    print('## workers (%d)' % len(got['workers']))
    rows = []
    for launch, pane in got['workers']:
        d = herdlib.latest(launch)
        rows.append([launch['name'], '%s · %s · %s' % (launch['kind'], launch['model'], launch['effort']),
                     pane['pane_id'], pane.get('agent_status', '-'), short(herdlib.session_of(pane) or
                                                                           launch['session_id']),
                     d['brief_sha256'][:16] if d else '-', deliverable_state(d),
                     '%s · %s' % (launch['worktree'], launch['branch']) if launch['worktree'] else '-',
                     last_event(launch)])
    print('\n'.join(table(['name', 'kind · model · effort', 'pane', 'status', 'session', 'brief', 'deliverable',
                           'worktree · branch', 'last event'], rows)) if rows else 'none')
    print()
    print('## unclassified (%d)' % len(got['unclassified']))
    rows = []
    failed_read = False
    for pane in got['unclassified']:
        note = 'looks like a worker' if herdlib.looks_like_worker(pane.get('name')) else ''
        if not pane.get('agent'):
            try:
                note = 'shell: ' + shell_tail(pane)
            except relaylib.HerdrError as e:
                note = 'shell: unreadable'
                failed_read = True
                print('herd status: %s' % e, file=sys.stderr)
        rows.append([pane['pane_id'], pane.get('agent', 'shell'), pane.get('name') or '-',
                     pane.get('agent_status', '-'), short(herdlib.session_of(pane)), pane.get('cwd'), note or '-'])
    print('\n'.join(table(['pane', 'kind', 'name', 'status', 'session', 'cwd', 'note'], rows)) if rows else 'none')
    print()
    print('## lost (%d)' % len(got['lost']))
    rows = [[l['name'], l['pane_id'], short(l['session_id']), l['cwd'], last_event(l)] for l in got['lost']]
    print('\n'.join(table(['name', 'last pane', 'session', 'cwd', 'last event'], rows)) if rows else 'none')
    if a.all:
        closed = [l for l in got['launches'].values() if l['closed'] is not None]
        print()
        print('## closed (%d)' % len(closed))
        rows = [[l['name'], l['pane_id'], l['closed'], last_event(l)] for l in closed]
        print('\n'.join(table(['name', 'last pane', 'closed', 'last event'], rows)) if rows else 'none')
    return 2 if failed_read else 0

"""The herd record: what a lead launched, dispatched and closed, and the live panes it explains.

The record is <project>/herd.jsonl (the project dir relay-check.py resolves for relay/ and lead.json: beside
memory/, never inside it). Append-only JSON lines, mode 0600, every append under an exclusive flock on herd.lock
and every read under a shared one. A line that does not parse, or a row missing a field, stops every reader with
the line number: a damaged record never reads as an empty herd.

Stdlib only; imported by herd.py, its command modules and relay-check.py.
"""
import contextlib
import datetime
import fcntl
import json
import os
import re
import subprocess
import uuid

import relaylib
import transcript

RECORD = 'herd.jsonl'
LOCK = 'herd.lock'
COMMON = ('at', 'type', 'launch_id')
FIELDS = {
    'launch': ('name', 'pane_id', 'kind', 'model', 'effort', 'mode', 'cwd', 'worktree', 'branch', 'session_id',
               'lead_session', 'adopted', 'started_at'),
    'dispatch': ('seq', 'brief', 'brief_sha256', 'deliverable', 'blocked', 'reset', 'sent_at', 'session_id'),
    'reported': ('seq', 'event'),
    'close': ('reason',),
}
EFFORTS = ('minimal', 'low', 'medium', 'high', 'xhigh', 'max')
ROLE = re.compile(r'[a-z][a-z0-9-]*\Z')
HERDR_NAME = re.compile(r'[a-z][a-z0-9_-]{0,31}\Z')
WORKER_NAME = re.compile(r'-(?:%s)(?:-[0-9a-f]{4})?\Z' % '|'.join(EFFORTS))


class RecordError(Exception):
    """The record cannot be read or written as a record."""


class Refusal(Exception):
    """A herd command refuses or fails: herd.py exits 1 with this message, nothing recorded."""


def require_herdr():
    """This session's herdr pane id, or Refusal outside herdr."""
    if os.environ.get('HERDR_ENV') != '1' or not os.environ.get('HERDR_PANE_ID'):
        raise Refusal('not inside herdr (HERDR_ENV or HERDR_PANE_ID unset)')
    return os.environ['HERDR_PANE_ID']


def git_toplevel(path):
    """The git top level of path, or None."""
    try:
        r = subprocess.run(['git', '-C', path, 'rev-parse', '--show-toplevel'], capture_output=True, text=True,
                           timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return os.path.realpath(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip() else None


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00', 'Z')


def epoch(iso):
    """Seconds since the epoch of a record timestamp."""
    return datetime.datetime.fromisoformat(iso.replace('Z', '+00:00')).timestamp()


def project_dir(projects=transcript.PROJECTS, override=None):
    """The lead's project dir: where its own transcript lives (as relay-check.py resolves it). override (herd.py's
    hidden --record-dir) keeps a trial run's record away from the real one."""
    if override:
        return override
    session = os.environ.get('CLAUDE_CODE_SESSION_ID')
    if not session:
        raise RecordError("CLAUDE_CODE_SESSION_ID is not set: run herd.py inside the lead's Claude session")
    try:
        return os.path.dirname(transcript.find_transcript(session, projects))
    except LookupError as e:
        raise RecordError(str(e))


@contextlib.contextmanager
def locked(pdir, name=LOCK, shared=False):
    """Hold flock on <pdir>/<name> (created 0600) for the block; closing the descriptor releases it."""
    os.makedirs(pdir, exist_ok=True)
    fd = os.open(os.path.join(pdir, name), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_SH if shared else fcntl.LOCK_EX)
        yield
    finally:
        os.close(fd)


def validate(row, where):
    if not isinstance(row, dict):
        raise RecordError('%s is not a JSON object' % where)
    for key in COMMON:
        if not isinstance(row.get(key), str) or not row[key]:
            raise RecordError('%s has no %s' % (where, key))
    if row['type'] not in FIELDS:
        raise RecordError('%s has unknown type %r' % (where, row['type']))
    missing = [key for key in FIELDS[row['type']] if key not in row]
    if missing:
        raise RecordError('%s (%s) lacks %s' % (where, row['type'], ', '.join(missing)))


def append(pdir, row):
    """Append one row (stamped with `at` unless it has one) and return it."""
    row = dict(row)
    row.setdefault('at', now_iso())
    validate(row, 'the new row')
    line = (json.dumps(row) + '\n').encode()
    with locked(pdir):
        fd = os.open(os.path.join(pdir, RECORD), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            os.write(fd, line)
        finally:
            os.close(fd)
    return row


def read(pdir):
    """Every row, oldest first; [] when there is no record yet."""
    path = os.path.join(pdir, RECORD)
    with locked(pdir, shared=True):
        try:
            with open(path) as fh:
                text = fh.read()
        except FileNotFoundError:
            return []
    rows = []
    for n, line in enumerate(text.splitlines(), 1):
        try:
            row = json.loads(line)
        except ValueError:
            raise RecordError('%s line %d does not parse' % (path, n))
        validate(row, '%s line %d' % (path, n))
        rows.append(row)
    return rows


def replay(rows):
    """{launch_id: launch}, in launch order. A launch is its launch row's fields plus launch_id, at, dispatches
    (its dispatch rows, oldest first), reported ({seq: event}) and closed (None while open, else why).

    session_id is the latest known session: the launch's, replaced by a dispatch that read one back; a dispatch
    with a reset replaces it even with null (the old session is over). A new launch on a pane an open launch still
    holds closes that launch (the pane was reused)."""
    launches = {}
    for n, row in enumerate(rows, 1):
        lid = row['launch_id']
        if row['type'] == 'launch':
            for other in launches.values():
                if other['closed'] is None and other['pane_id'] == row['pane_id']:
                    other['closed'] = 'pane %s reused by %s' % (row['pane_id'], row['name'])
            launch = {key: row[key] for key in FIELDS['launch']}
            launch.update(launch_id=lid, at=row['at'], dispatches=[], reported={}, closed=None)
            launches[lid] = launch
            continue
        launch = launches.get(lid)
        if launch is None:
            raise RecordError('row %d (%s) names launch %s, which has no launch row' % (n, row['type'], lid))
        if row['type'] == 'dispatch':
            launch['dispatches'].append(row)
            if row['reset'] or row['session_id']:
                launch['session_id'] = row['session_id']
        elif row['type'] == 'reported':
            launch['reported'][row['seq']] = row['event']
        elif launch['closed'] is None:
            launch['closed'] = row['reason'] or 'closed'
    return launches


def open_launches(launches):
    return [launch for launch in launches.values() if launch['closed'] is None]


def by_name(launches, name):
    """The open launch called name, or RecordError."""
    hits = [launch for launch in open_launches(launches) if launch['name'] == name]
    if not hits:
        raise RecordError('no open launch is called %r (herd.py status lists them)' % name)
    return hits[-1]


def latest(launch):
    """The launch's latest dispatch row, or None."""
    return launch['dispatches'][-1] if launch['dispatches'] else None


def new_name(role, effort, rows, taken=(), draw=lambda: uuid.uuid4().hex):
    """(launch_id, name) for a new worker: <role>-<effort>-<first 4 hex of launch_id>, the 4 hex unused by any
    launch in the record and the name not in taken. A role or name herdr cannot carry is refused, never cut."""
    if not ROLE.match(role or ''):
        raise ValueError('role %r must match [a-z][a-z0-9-]*' % role)
    used = {row['launch_id'][:4] for row in rows if row['type'] == 'launch'}
    for _ in range(1000):
        lid = draw()
        name = '%s-%s-%s' % (role, effort, lid[:4])
        if lid[:4] not in used and name not in taken:
            break
    else:
        raise ValueError('no free launch id after 1000 draws')
    if not HERDR_NAME.match(name):
        raise ValueError("name %r does not fit herdr's [a-z][a-z0-9_-]{0,31}: use a shorter role" % name)
    return lid, name


def looks_like_worker(name):
    """A herd worker's name: it ends in -<effort> or -<effort>-<4 hex>."""
    return bool(name and WORKER_NAME.search(name))


def session_of(pane):
    return (pane.get('agent_session') or {}).get('value')


def live_panes():
    """herdr's panes, each with its agent's name (the pane list carries none) as 'name'."""
    names = {a.get('pane_id'): a.get('name') for a in relaylib.herdr_list('agents', 'agent', 'list')}
    panes = relaylib.herdr_list('panes', 'pane', 'list')
    for pane in panes:
        pane['name'] = names.get(pane.get('pane_id'))
    return panes


def match(launches, panes):
    """Join the open launches with the live agent panes: (pairs [(launch, pane)], free panes, lost launches).

    A launch matches the pane whose agent_session.value equals its latest session; failing that, the pane holding
    its pane_id; failing that, the pane whose agent carries its name. A pane whose session is known and differs
    from the launch's known session never matches it by pane id or name (a pane renumbered after a restore, or
    reused). Only a pane hosting an agent can match: a worker whose agent exited is lost."""
    def same_session(launch, pane):
        return bool(launch['session_id']) and session_of(pane) == launch['session_id']

    def compatible(launch, pane):
        return not (launch['session_id'] and session_of(pane) and session_of(pane) != launch['session_id'])

    rules = (same_session,
             lambda launch, pane: pane.get('pane_id') == launch['pane_id'] and compatible(launch, pane),
             lambda launch, pane: bool(launch['name']) and pane.get('name') == launch['name']
             and compatible(launch, pane))
    free = [pane for pane in panes if pane.get('agent')]
    shells = [pane for pane in panes if not pane.get('agent')]
    pending = open_launches(launches)
    pairs = []
    for rule in rules:
        for launch in list(pending):
            hit = next((pane for pane in free if rule(launch, pane)), None)
            if hit is not None:
                pairs.append((launch, hit))
                free.remove(hit)
                pending.remove(launch)
    return pairs, free + shells, pending


def scope_roots(repo, launches, extra_roots=()):
    """The dirs whose panes the herd answers for: the repo's git worktrees (or the repo), each open launch's cwd,
    and extra roots; real paths, without a trailing slash."""
    try:
        listing = subprocess.run(['git', '-C', repo, 'worktree', 'list', '--porcelain'], capture_output=True,
                                 text=True, timeout=10).stdout
    except (OSError, subprocess.TimeoutExpired):
        listing = ''
    roots = [line[len('worktree '):] for line in listing.splitlines() if line.startswith('worktree ')] or [repo]
    roots += [launch['cwd'] for launch in open_launches(launches)] + list(extra_roots)
    out = []
    for root in roots:
        real = os.path.realpath(root).rstrip('/') or '/'
        if real not in out:
            out.append(real)
    return out


def in_scope(cwd, roots):
    cwd = os.path.realpath(cwd or '/').rstrip('/') or '/'
    return any(cwd == root or cwd.startswith(root.rstrip('/') + '/') for root in roots)


def herd(pdir, repo, extra_roots=(), self_pane=None, panes=None):
    """The record joined with live panes: {'launches', 'workers': [(launch, pane)], 'unclassified': [pane],
    'lost': [launch], 'roots'}. unclassified: panes in scope matching no open launch, never this session's own.
    pdir None: no record (every pane in scope is unclassified). panes: herdr's live panes; read here when None."""
    launches = replay(read(pdir)) if pdir else {}
    panes = live_panes() if panes is None else panes
    pairs, free, lost = match(launches, panes)
    roots = scope_roots(repo, launches, extra_roots)
    unclassified = [pane for pane in free if pane.get('pane_id') != self_pane and in_scope(pane.get('cwd'), roots)]
    return {'launches': launches, 'workers': pairs, 'unclassified': unclassified, 'lost': lost, 'roots': roots}

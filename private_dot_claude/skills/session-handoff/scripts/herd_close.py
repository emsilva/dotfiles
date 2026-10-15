"""close: close an idle worker's pane once its work is safe, and record it closed.

A builder's worktree must be clean (a dirty one is reported, never closed); the worktree and branch stay, since
pruning after the merge is the lead's job. A launch with no live pane (lost) is only recorded closed.
"""
import json
import os
import subprocess
import time

import herdlib
import relaylib

CLOSE_BOUND = int(os.environ.get('HERD_CLOSE_SECONDS', '10'))


def add_arguments(p):
    p.add_argument('name', help='the worker, as herd.py status names it')
    p.add_argument('--reason', default='', help='why, for the record')


def gone(pane):
    try:
        relaylib.herdr_json('agent', 'get', pane)
    except relaylib.HerdrError as e:
        if e.code == 'agent_not_found':
            return True
        raise
    return False


def run(a):
    herdlib.require_herdr()
    pdir = herdlib.project_dir(a.projects, a.record_dir)
    launches = herdlib.replay(herdlib.read(pdir))
    launch = herdlib.by_name(launches, a.name)
    pairs, _, _ = herdlib.match(launches, herdlib.live_panes())
    pane = next((p for l, p in pairs if l is launch), None)
    if pane is None:
        row = herdlib.append(pdir, {'type': 'close', 'launch_id': launch['launch_id'],
                                    'reason': a.reason or 'lost: no live pane'})
        print(json.dumps(row))
        return 0
    if pane.get('agent_status') not in ('idle', 'done'):
        raise herdlib.Refusal('%s is %s: close only an idle worker' % (a.name, pane.get('agent_status')))
    checkout = launch['worktree']
    if launch['mode'] == 'builder' and not checkout:
        checkout = herdlib.git_toplevel(launch['cwd'])
        if not checkout:
            raise herdlib.Refusal('cannot locate the builder checkout for %s, so it stays open' % a.name)
    if checkout:
        dirty = subprocess.run(['git', '-C', checkout, 'status', '--porcelain'], capture_output=True,
                               text=True, timeout=30)
        if dirty.returncode != 0 or dirty.stdout.strip():
            raise herdlib.Refusal('the worktree %s is not clean, so %s stays open:\n%s'
                                  % (checkout, a.name, dirty.stdout.rstrip() or dirty.stderr.strip()))
    relaylib.herdr_text('pane', 'close', pane['pane_id'])
    deadline = time.monotonic() + CLOSE_BOUND
    while not gone(pane['pane_id']):
        if time.monotonic() >= deadline:
            raise herdlib.Refusal('pane %s still hosts an agent %d s after the close' % (pane['pane_id'], CLOSE_BOUND))
        time.sleep(0.5)
    row = herdlib.append(pdir, {'type': 'close', 'launch_id': launch['launch_id'], 'reason': a.reason or 'closed'})
    print(json.dumps(row))
    return 0

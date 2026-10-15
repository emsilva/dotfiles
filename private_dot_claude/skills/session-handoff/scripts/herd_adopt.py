"""adopt: record a worker that is already running (launched by hand, or before herd.py) as a launch.

It keeps its herdr name (waiters may key on it) unless --rename, or unless it has none: then it gets
<role>-<effort>-<4 hex>. A Claude worker is recorded as a builder (it has no sandbox). With --brief it also records
the brief it is working on, sent now.
"""
import json
import os
import subprocess
import uuid

import herd_dispatch
import herdlib
import relaylib


def add_arguments(p):
    p.add_argument('pane', help='the pane hosting the worker')
    p.add_argument('--role', required=True, help='what the worker does: [a-z][a-z0-9-]*')
    p.add_argument('--model')
    p.add_argument('--effort')
    p.add_argument('--mode', choices=('builder', 'readonly'),
                   help='default: builder for a Claude worker (no sandbox) or one in .claude/worktrees/, else readonly')
    p.add_argument('--rename', action='store_true', help='give it a generated name')
    p.add_argument('--brief')
    p.add_argument('--deliverable')
    p.add_argument('--blocked')


def run(a):
    if bool(a.brief) != bool(a.deliverable) or (a.blocked and not a.brief):
        raise herdlib.Refusal('--brief and --deliverable go together (--blocked only with them)')
    brief = os.path.abspath(a.brief) if a.brief else None
    if brief and not os.path.isfile(brief):
        raise herdlib.Refusal('no brief at %s' % brief)
    herdlib.require_herdr()
    pdir = herdlib.project_dir(a.projects, a.record_dir)
    rows = herdlib.read(pdir)
    launches = herdlib.replay(rows)
    try:
        agent = (relaylib.herdr_json('agent', 'get', a.pane).get('result') or {}).get('agent') or {}
    except relaylib.HerdrError as e:
        raise herdlib.Refusal('pane %s hosts no agent (%s)' % (a.pane, e))
    if agent.get('agent') not in ('claude', 'codex'):
        raise herdlib.Refusal('pane %s hosts %s, not a Claude or Codex worker' % (a.pane, agent.get('agent')))
    pane = {'pane_id': a.pane, 'agent': agent['agent'], 'agent_session': agent.get('agent_session'),
            'name': agent.get('name')}
    pairs, _, _ = herdlib.match(launches, [pane])
    if pairs:
        raise herdlib.Refusal('pane %s is already recorded as %s' % (a.pane, pairs[0][0]['name']))
    name = agent.get('name')
    if a.rename or not name:
        if not a.effort:
            raise herdlib.Refusal('pass --effort: the generated name is <role>-<effort>-<4 hex>')
        taken = {x.get('name') for x in relaylib.herdr_list('agents', 'agent', 'list')}
        try:
            lid, name = herdlib.new_name(a.role, a.effort, rows, taken)
        except ValueError as e:
            raise herdlib.Refusal(str(e))
        relaylib.herdr_text('agent', 'rename', a.pane, name)
    else:
        if any(l['name'] == name for l in herdlib.open_launches(launches)):
            raise herdlib.Refusal('an open launch is already called %s: adopt with --rename' % name)
        lid = uuid.uuid4().hex
    if agent['agent'] == 'claude' and a.mode == 'readonly':
        raise herdlib.Refusal('a Claude worker has no sandbox, so it cannot be recorded read-only')
    cwd = os.path.realpath(agent.get('cwd') or '/')
    in_worktree = '/.claude/worktrees/' in cwd + '/'
    mode = a.mode or ('builder' if agent['agent'] == 'claude' or in_worktree else 'readonly')
    worktree = branch = None
    if in_worktree:
        worktree = herdlib.git_toplevel(cwd)
        branch = subprocess.run(['git', '-C', cwd, 'branch', '--show-current'], capture_output=True, text=True,
                                timeout=10).stdout.strip() or None
    session = (agent.get('agent_session') or {}).get('value')
    launch = herdlib.append(pdir, {
        'type': 'launch', 'launch_id': lid, 'name': name, 'pane_id': a.pane, 'kind': agent['agent'],
        'model': a.model, 'effort': a.effort, 'mode': mode, 'cwd': cwd, 'worktree': worktree, 'branch': branch,
        'session_id': session, 'lead_session': os.environ.get('CLAUDE_CODE_SESSION_ID'), 'adopted': True,
        'started_at': None})
    dispatch = None
    if brief:
        deliverable = os.path.abspath(a.deliverable)
        dispatch = herdlib.append(pdir, {
            'type': 'dispatch', 'launch_id': lid, 'seq': 1, 'brief': brief,
            'brief_sha256': herd_dispatch.sha256(brief), 'deliverable': deliverable,
            'blocked': os.path.abspath(a.blocked) if a.blocked else os.path.join(os.path.dirname(deliverable),
                                                                                 'BLOCKED.md'),
            'reset': None, 'sent_at': herdlib.now_iso(), 'session_id': session})
    print(json.dumps({'launch': launch, 'dispatch': dispatch}))
    return 0

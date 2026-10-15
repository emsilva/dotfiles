"""Shared fixtures for the herd.py tests: a lead session with a transcript, a git repo, a fake herdr and the
record. herdr answers are queued per verb ("pane read", "agent get", ...) as handoff_fixtures.STUB describes."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from handoff_fixtures import SCRIPTS, herdr_calls, herdr_stub, tool_use, write_transcript

sys.path.insert(0, str(SCRIPTS))
import herdlib  # noqa: E402

HERD = SCRIPTS / 'herd.py'
SID = '55555555-5555-4555-8555-555555555555'
LEAD = 'wT:p1'
CODEX_BANNER = {'out': '\n  GPT-6.1-Sol xhigh · ~/x/repo · main · Context 100% left\n'}
NOT_READY = {'out': json.dumps({'error': {'code': 'agent_not_ready', 'message': 'blocked during startup'}}),
             'code': 1}
TAKEN = {'out': json.dumps({'error': {'code': 'agent_name_taken', 'message': 'name is taken'}}), 'code': 1}
NOT_FOUND = {'out': json.dumps({'error': {'code': 'agent_not_found', 'message': 'not found'}}), 'code': 1}


def ok(obj=None):
    return {'out': json.dumps(obj if obj is not None else {'result': {}})}


def layout(*panes):
    """herdr pane layout: panes as (pane_id, x, y, width, height)."""
    return ok({'result': {'layout': {'panes': [{'pane_id': p, 'rect': {'x': x, 'y': y, 'width': w, 'height': h}}
                                               for p, x, y, w, h in panes], 'splits': []}, 'type': 'pane_layout'}})


def split(pane):
    return ok({'result': {'pane': {'pane_id': pane}}})


def pane_entry(pid, cwd, kind='codex', status='idle', session=None, name=None):
    """One live pane as herd reads it: herdr's pane list entry; name is the agent list's."""
    p = {'pane_id': pid, 'tab_id': 'wT:t1', 'cwd': str(cwd)}
    if kind:
        p.update(agent=kind, agent_status=status)
    if session:
        p['agent_session'] = {'value': session}
    if name:
        p['name'] = name
    return p


def listing(*entries):
    """(pane list answer, agent list answer) for these pane entries."""
    panes = [{k: v for k, v in e.items() if k != 'name'} for e in entries]
    agents = [{'pane_id': e['pane_id'], 'name': e.get('name'), 'agent': e['agent']} for e in entries if e.get('agent')]
    return ok({'result': {'panes': panes}}), ok({'result': {'agents': agents}})


def agent(status, pane, session=None, name=None, kind='codex'):
    a = {'agent': kind, 'agent_status': status, 'pane_id': pane}
    if session:
        a['agent_session'] = {'kind': 'id', 'value': session}
    if name:
        a['name'] = name
    return ok({'result': {'agent': a, 'type': 'agent_info'}})


class HerdCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(os.path.realpath(self.tmp.name))
        self.projects = self.root / 'projects'
        self.transcript = write_transcript(self.projects, SID, [tool_use('t0', 'Bash', {'command': 'true'})])
        self.pdir = self.transcript.parent
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        git = ['git', '-C', str(self.repo), '-c', 'user.name=T', '-c', 'user.email=t@example.invalid']
        subprocess.run(['git', 'init', '-q', str(self.repo)], check=True)
        (self.repo / 'README.md').write_text('x\n')
        subprocess.run(git + ['add', '.'], check=True)
        subprocess.run(git + ['commit', '-qm', 'init'], check=True)
        self.codex_home = self.root / 'codex'

    def tearDown(self):
        self.tmp.cleanup()

    def env(self, responses, env=None, drop=()):
        """The environment of the lead's session with this fake herdr; env adds variables, drop removes them."""
        full, self.log = herdr_stub(str(self.root), responses)
        # A banner drawn late is read again until it shows: a loaded machine cannot run out a long bound. The test of
        # a wrong banner sets 0 (one read).
        full.update(CLAUDE_CODE_SESSION_ID=SID, HERDR_PANE_ID=LEAD, CODEX_HOME=str(self.codex_home),
                    RELAYLIB_BANNER_SECONDS='120')
        full.update(env or {})
        for key in drop:
            full.pop(key, None)
        return full

    def herd(self, responses, *args, cwd=None, env=None, drop=(), timeout=60, code=None):
        """Run herd.py to completion."""
        command = ['python3', '-I', '-B']
        if code is None:
            command += [str(HERD)]
        else:
            command += ['-c', 'import sys; sys.path.insert(0, %r); ' % str(SCRIPTS) + code]
        return subprocess.run([*command, *args, '--projects', str(self.projects)],
                              capture_output=True, text=True, env=self.env(responses, env, drop),
                              cwd=str(cwd or self.repo), timeout=timeout)

    def start(self, responses, *args):
        """Start herd.py and return the running process (stdout and stderr piped, text)."""
        return subprocess.Popen(['python3', '-I', str(HERD), *args, '--projects', str(self.projects)],
                                env=self.env(responses), cwd=str(self.repo), stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True)

    def calls(self, verb):
        return [c for c in herdr_calls(self.log) if c[:len(verb)] == verb]

    def rows(self):
        return herdlib.read(self.pdir)

    def record(self, *rows):
        for row in rows:
            herdlib.append(self.pdir, row)

    def launch_row(self, name, pane, lid=None, session=None, kind='codex', cwd=None, mode='readonly',
                   worktree=None, at='2026-10-14T10:00:00Z'):
        lid = lid or (name.encode().hex() + '0' * 32)[:32]
        return {'at': at, 'type': 'launch', 'launch_id': lid, 'name': name, 'pane_id': pane, 'kind': kind,
                'model': 'gpt-6.1-sol', 'effort': 'xhigh', 'mode': mode, 'cwd': str(cwd or self.repo),
                'worktree': worktree, 'branch': None, 'session_id': session, 'lead_session': SID, 'adopted': False,
                'started_at': at}

    def dispatch_row(self, lid, seq=1, deliverable=None, blocked=None, sent_at='2026-10-14T10:05:00Z', session=None,
                     reset=None):
        return {'at': sent_at, 'type': 'dispatch', 'launch_id': lid, 'seq': seq, 'brief': str(self.root / 'b.md'),
                'brief_sha256': 'ab' * 32, 'deliverable': str(deliverable or self.root / 'r.md'),
                'blocked': str(blocked or self.root / 'BLOCKED.md'), 'reset': reset, 'sent_at': sent_at,
                'session_id': session}

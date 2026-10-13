import datetime
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

from handoff_fixtures import (SCRIPTS, agent_json, herdr_stub, prompt, tool_result, tool_use,
                              write_transcript)

RC = SCRIPTS / 'relay-check.py'
SID = '33333333-3333-4333-8333-333333333333'
HERDR_NAME = re.compile(r'^[a-z][a-z0-9_-]{0,31}$')


def load_module():
    spec = importlib.util.spec_from_file_location('relay_check', RC)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def rc(*args, env=None, cwd=None):
    return subprocess.run(['python3', '-I', str(RC), *args], capture_output=True, text=True, env=env, cwd=cwd)


def git_repo(root):
    repo = Path(root) / 'repo'
    repo.mkdir()
    subprocess.run(['git', 'init', '-q', str(repo)], check=True)
    (repo / 'README.md').write_text('x\n')
    subprocess.run(['git', '-C', str(repo), 'add', '.'], check=True)
    subprocess.run(['git', '-C', str(repo), '-c', 'user.name=T', '-c', 'user.email=t@example.invalid',
                    'commit', '-qm', 'init'], check=True)
    return Path(os.path.realpath(repo))


class NameTests(unittest.TestCase):
    def test_lead_names_are_valid_herdr_names(self):
        for repo, canonical in [('/x/acme-consult-agent-alpha-beta', 'lead-acme-consult-agent-alp'),
                                ('/x/9 Lives.Repo', 'lead-9-lives-repo'),
                                ('/x/UPPER_case', 'lead-upper-case'),
                                ('/x/...', 'lead-project')]:
            got = rc('name', '--repo', repo).stdout.strip()
            nxt = rc('name', '--repo', repo, '--suffix', 'next').stdout.strip()
            self.assertEqual(got, canonical)
            self.assertEqual(nxt, canonical + '-next')
            for name in (got, nxt):
                self.assertRegex(name, HERDR_NAME)
        self.assertEqual(rc('name', '--repo', '/x/anything', '--slug', 'alpha').stdout.strip(), 'lead-alpha')


class ChecklistTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.repo = git_repo(self.root)
        self.projects = self.root / 'projects'
        self.note = self.root / 'note.md'
        self.note.write_text('# note\n')

    def tearDown(self):
        self.tmp.cleanup()

    def env(self, recs, panes=None):
        self.transcript = write_transcript(self.projects, SID, recs)
        panes = panes if panes is not None else [
            {'pane_id': 'wT:p1', 'tab_id': 'wT:t1', 'cwd': str(self.repo), 'agent': 'claude', 'agent_status': 'working'},
            {'pane_id': 'wT:p2', 'tab_id': 'wT:t1', 'cwd': str(self.repo / 'sub'), 'agent': 'codex',
             'agent_status': 'working', 'agent_session': {'value': 'W2'}},
            {'pane_id': 'wT:p3', 'tab_id': 'wT:t9', 'cwd': '/elsewhere', 'agent': 'claude', 'agent_status': 'idle'}]
        env, self.log = herdr_stub(self.tmp.name, {
            'agent get': [{'out': agent_json('working', session='S1', pane='wT:p1', name='lead-repo')}],
            'agent list': [{'out': json.dumps({'result': {'agents': [{'pane_id': 'wT:p2', 'name': 'worker-a'}]}})}],
            'pane list': [{'out': json.dumps({'result': {'panes': panes}})}]})
        env.update(CLAUDE_CODE_SESSION_ID=SID, CLAUDE_EFFORT='xhigh', CLAUDE_PID='4242')
        return env

    def transcript_recs(self):
        return [{'type': 'permission-mode', 'permissionMode': 'bypassPermissions'},
                prompt('drive iteration 1', 1),
                tool_use('t1', 'Bash', {'command': 'until [ -f r ]; do sleep 5; done', 'description': 'wait r',
                                        'run_in_background': True}, 2),
                tool_result('t1', 'Command running in background with ID: bwait0001. Output is being written to: '
                            '/tmp/x/bwait0001.output', 2, tool_use_result={'backgroundTaskId': 'bwait0001'}),
                tool_use('c1', 'CronCreate', {'cron': '7 * * * *', 'prompt': 'status'}, 3),
                tool_result('c1', 'Scheduled recurring task cr000001 (7 * * * *).', 3)]

    def test_checklist_records_identity_tasks_crons_workers_and_prompts(self):
        env = self.env(self.transcript_recs())
        r = rc('checklist', '--note', str(self.note), '--projects', str(self.projects), env=env, cwd=self.repo)
        self.assertEqual(r.returncode, 0, r.stderr)
        rdir = Path(r.stdout.strip())
        self.assertEqual(rdir.parent, self.projects / '-tmp-repo' / 'relay')
        c = json.loads((rdir / 'checklist.json').read_text())
        self.assertEqual(c['relay_id'], rdir.name)
        self.assertEqual(c['repo'], str(self.repo))
        self.assertEqual(c['predecessor'], {
            'session_id': SID, 'transcript': str(self.transcript), 'pane_id': 'wT:p1', 'herdr_name': 'lead-repo',
            'herdr_session': 'S1', 'model': 'claude-opus-5-5', 'effort': 'xhigh',
            'permission_mode': 'bypassPermissions', 'pid': 4242})
        git = lambda *args: subprocess.run(['git', '-C', str(self.repo), *args],
                                           capture_output=True, text=True).stdout.strip()
        self.assertEqual(c['git'], {'head': git('rev-parse', '--short', 'HEAD'),
                                    'branch': git('rev-parse', '--abbrev-ref', 'HEAD'), 'dirty': []})
        self.assertEqual([t['id'] for t in c['background_tasks']], ['bwait0001'])
        self.assertEqual([x['id'] for x in c['crons']], ['cr000001'])
        self.assertEqual(c['workers'], [{'pane_id': 'wT:p2', 'name': 'worker-a', 'kind': 'codex',
                                         'status': 'working', 'session_id': 'W2', 'cwd': str(self.repo / 'sub')}])
        self.assertEqual([p['text'] for p in c['recent_prompts']], ['drive iteration 1'])
        self.assertEqual(c['note']['path'], str(self.note))
        self.assertEqual(len(c['note']['sha256']), 64)

    def test_checklist_lists_dirty_paths_whole(self):
        # git status --porcelain starts an unstaged change with a space (" M README.md"): it must survive.
        with (self.repo / 'README.md').open('a') as fh:
            fh.write('y\n')
        (self.repo / 'new.txt').write_text('n\n')
        r = rc('checklist', '--note', str(self.note), '--projects', str(self.projects),
               env=self.env(self.transcript_recs()), cwd=self.repo)
        self.assertEqual(r.returncode, 0, r.stderr)
        c = json.loads((Path(r.stdout.strip()) / 'checklist.json').read_text())
        self.assertEqual(c['git']['dirty'], ['README.md', 'new.txt'])

    def test_checklist_refuses_while_a_workflow_runs(self):
        recs = self.transcript_recs() + [
            tool_use('w1', 'Workflow', {'script': 'x'}, 4),
            tool_result('w1', 'Workflow launched in background. Task ID: wrun00001 Summary: x', 4,
                        tool_use_result={'status': 'async_launched', 'taskId': 'wrun00001'})]
        r = rc('checklist', '--note', str(self.note), '--projects', str(self.projects), env=self.env(recs),
               cwd=self.repo)
        self.assertEqual(r.returncode, 3)
        self.assertIn('workflow wrun00001', r.stderr)
        self.assertFalse((self.projects / '-tmp-repo' / 'relay').exists())

    def test_checklist_refuses_mid_merge(self):
        (self.repo / '.git' / 'MERGE_HEAD').write_text('0' * 40 + '\n')
        r = rc('checklist', '--note', str(self.note), '--projects', str(self.projects),
               env=self.env(self.transcript_recs()), cwd=self.repo)
        self.assertEqual(r.returncode, 3)
        self.assertIn('MERGE_HEAD', r.stderr)

    def test_relay_dir_collision_gets_a_suffix(self):
        module = load_module()
        now = datetime.datetime(2026, 10, 12, 20, 24, 23, tzinfo=datetime.timezone.utc)
        first = module.new_relay_dir(str(self.root / 'proj'), now)
        second = module.new_relay_dir(str(self.root / 'proj'), now)
        self.assertEqual(os.path.basename(first), '20261012T202423Z')
        self.assertEqual(os.path.basename(second), '20261012T202423Z-2')

    def test_identity_reads_the_current_session(self):
        env = self.env(self.transcript_recs())
        r = rc('identity', '--projects', str(self.projects), env=env, cwd=self.repo)
        self.assertEqual(json.loads(r.stdout), {'session_id': SID, 'pane_id': 'wT:p1', 'model': 'claude-opus-5-5',
                                                'effort': 'xhigh', 'permission_mode': 'bypassPermissions'})


if __name__ == '__main__':
    unittest.main()

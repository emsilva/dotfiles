import datetime
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import tempfile
import unittest

from handoff_fixtures import (SCRIPTS, agent_json, herdr_calls, herdr_stub, prompt, tool_result, tool_use,
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

    def env(self, recs, panes=None, herdr=None):
        self.transcript = write_transcript(self.projects, SID, recs)
        panes = panes if panes is not None else [
            {'pane_id': 'wT:p1', 'tab_id': 'wT:t1', 'cwd': str(self.repo), 'agent': 'claude', 'agent_status': 'working'},
            {'pane_id': 'wT:p2', 'tab_id': 'wT:t1', 'cwd': str(self.repo / 'sub'), 'agent': 'codex',
             'agent_status': 'working', 'agent_session': {'value': 'W2'}},
            {'pane_id': 'wT:p3', 'tab_id': 'wT:t9', 'cwd': '/elsewhere', 'agent': 'claude', 'agent_status': 'idle'}]
        env, self.log = herdr_stub(self.tmp.name, dict({
            'agent get': [{'out': agent_json('working', session='S1', pane='wT:p1', name='lead-repo')}],
            'agent list': [{'out': json.dumps({'result': {'agents': [{'pane_id': 'wT:p2', 'name': 'worker-a'}]}})}],
            'pane list': [{'out': json.dumps({'result': {'panes': panes}})}]}, **(herdr or {})))
        env.update(CLAUDE_CODE_SESSION_ID=SID, CLAUDE_EFFORT='xhigh', CLAUDE_PID='4242')
        return env

    def relay_root(self):
        return self.projects / '-tmp-repo' / 'relay'

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

    def test_a_failed_herdr_read_stops_the_checklist(self):
        # Real herdr reports errors as JSON on stderr with exit 1; an empty observation must not be recorded.
        error = {'out': json.dumps({'error': {'code': 'server_unavailable', 'message': 'no herdr server'}}),
                 'code': 1}
        for cmd in ('agent get', 'agent list', 'pane list'):
            with self.subTest(cmd=cmd):
                r = rc('checklist', '--note', str(self.note), '--projects', str(self.projects),
                       env=self.env(self.transcript_recs(), herdr={cmd: [error]}), cwd=self.repo)
                self.assertEqual(r.returncode, 2, r.stderr)
                self.assertEqual(len(r.stderr.splitlines()), 1, r.stderr)
                self.assertIn('herdr ' + cmd, r.stderr)
                self.assertIn('no herdr server', r.stderr)
                self.assertFalse(self.relay_root().exists())

    def test_herdr_output_that_is_not_json_stops_the_checklist(self):
        r = rc('checklist', '--note', str(self.note), '--projects', str(self.projects),
               env=self.env(self.transcript_recs(), herdr={'pane list': [{'out': 'garbled'}]}), cwd=self.repo)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn('herdr pane list', r.stderr)
        self.assertFalse(self.relay_root().exists())

    def test_a_herdr_listing_of_another_shape_stops_the_checklist(self):
        # A herdr JSON shape change must not read as an empty herd: `workers: []` would pass a lost worker.
        for cmd, key in (('pane list', 'panes'), ('agent list', 'agents')):
            for answer in ({'result': {'items': []}}, {'result': {key: {}}}, {'result': None}, {}):
                with self.subTest(cmd=cmd, answer=answer):
                    r = rc('checklist', '--note', str(self.note), '--projects', str(self.projects),
                           env=self.env(self.transcript_recs(), herdr={cmd: [{'out': json.dumps(answer)}]}),
                           cwd=self.repo)
                    self.assertEqual(r.returncode, 2, r.stderr)
                    self.assertEqual(len(r.stderr.splitlines()), 1, r.stderr)
                    self.assertIn('herdr ' + cmd, r.stderr)
                    self.assertIn('result.' + key, r.stderr)
                    self.assertFalse(self.relay_root().exists())

    def test_a_missing_note_leaves_no_relay_dir(self):
        r = rc('checklist', '--note', str(self.root / 'absent.md'), '--projects', str(self.projects),
               env=self.env(self.transcript_recs()), cwd=self.repo)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn('absent.md', r.stderr)
        self.assertFalse(self.relay_root().exists())

    def test_outside_herdr_the_checklist_reads_no_herdr(self):
        env = self.env(self.transcript_recs())
        del env['HERDR_PANE_ID'], env['HERDR_ENV']
        r = rc('checklist', '--note', str(self.note), '--projects', str(self.projects), env=env, cwd=self.repo)
        self.assertEqual(r.returncode, 0, r.stderr)
        c = json.loads((Path(r.stdout.strip()) / 'checklist.json').read_text())
        self.assertEqual(c['workers'], [])
        self.assertEqual((c['predecessor']['pane_id'], c['predecessor']['herdr_name']), (None, None))
        self.assertEqual(herdr_calls(self.log), [])

    def test_relay_dir_collision_gets_a_suffix(self):
        module = load_module()
        now = datetime.datetime(2026, 10, 12, 20, 24, 23, tzinfo=datetime.timezone.utc)
        first = module.new_relay_dir(str(self.root / 'proj'), now)
        second = module.new_relay_dir(str(self.root / 'proj'), now)
        self.assertEqual(os.path.basename(first), '20261012T202423Z')
        self.assertEqual(os.path.basename(second), '20261012T202423Z-2')

    def mode_without_a_transcript_record(self, project_file, project_mode, home_mode=None):
        """checklist and identity's permission_mode when the transcript has no permission-mode record.
        HOME is a temp home, so the real ~/.claude/settings.json is never read."""
        home = self.root / 'home'
        (home / '.claude').mkdir(parents=True, exist_ok=True)
        user = home / '.claude' / 'settings.json'
        if home_mode:
            user.write_text(json.dumps({'permissions': {'defaultMode': home_mode}}))
        elif user.exists():
            user.unlink()
        project = self.repo / '.claude' / project_file
        project.parent.mkdir(exist_ok=True)
        project.write_text(json.dumps({'permissions': {'defaultMode': project_mode}}))
        try:
            env = dict(self.env(self.transcript_recs()[1:]), HOME=str(home))
            r = rc('checklist', '--note', str(self.note), '--projects', str(self.projects), env=env, cwd=self.repo)
            self.assertEqual(r.returncode, 0, r.stderr)
            ident = rc('identity', '--projects', str(self.projects), env=env, cwd=self.repo)
            self.assertEqual(ident.returncode, 0, ident.stderr)
        finally:
            project.unlink()
        return (json.loads((Path(r.stdout.strip()) / 'checklist.json').read_text())['predecessor']['permission_mode'],
                json.loads(ident.stdout)['permission_mode'])

    def test_project_settings_never_grant_bypass(self):
        # A cloned repo's .claude/settings*.json must not put the relayed successor into bypass mode.
        for project_file in ('settings.json', 'settings.local.json'):
            with self.subTest(project_file=project_file):
                self.assertEqual(self.mode_without_a_transcript_record(project_file, 'bypassPermissions'),
                                 ('default', 'default'))

    def test_the_users_own_settings_give_the_mode(self):
        for project_file in ('settings.json', 'settings.local.json'):
            with self.subTest(project_file=project_file):
                self.assertEqual(self.mode_without_a_transcript_record(project_file, 'acceptEdits',
                                                                       home_mode='bypassPermissions'),
                                 ('bypassPermissions', 'bypassPermissions'))

    def test_identity_reads_the_current_session(self):
        env = self.env(self.transcript_recs())
        r = rc('identity', '--projects', str(self.projects), env=env, cwd=self.repo)
        self.assertEqual(json.loads(r.stdout), {'session_id': SID, 'pane_id': 'wT:p1', 'model': 'claude-opus-5-5',
                                                'effort': 'xhigh', 'permission_mode': 'bypassPermissions'})


class CompareTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        # The relay id carries the pid, so the markers (relay-<id>-w<k>) are unique to this run.
        self.relay_id = 'test%d' % os.getpid()
        self.dir = Path(self.tmp.name) / 'relay' / self.relay_id
        self.dir.mkdir(parents=True)
        self.note = Path(self.tmp.name) / 'note.md'
        self.note.write_text('# note\n')
        self.marker = 'relay-%s-w' % self.relay_id
        self.procs = []
        for k in (1, 2):
            self.spawn(': %s%d; while :; do sleep 1; done' % (self.marker, k))
        identity = {'model': 'claude-opus-5-5', 'effort': 'xhigh', 'permission_mode': 'bypassPermissions'}
        self.checklist = {
            'relay_id': self.relay_id, 'predecessor': dict(identity, session_id='P', transcript='/dev/null'),
            'note': {'path': str(self.note), 'sha256': load_module().sha256(str(self.note))},
            'background_tasks': [{'id': 'b4tcyp53v', 'kind': 'shell', 'description': 'Watch free disk', 'command': 'df'}],
            'crons': [{'id': 'cr1', 'cron': '7 * * * *', 'prompt': 'status', 'recurring': True}],
            'workers': [{'pane_id': 'wT:p2', 'name': 'worker-a', 'kind': 'codex', 'status': 'working'}]}
        self.receipt = {
            'relay_id': self.relay_id, 'successor': dict(identity, session_id='N'),
            'note': {'path': str(self.note), 'sha256': self.checklist['note']['sha256']},
            'tier': 'clean', 'drift': [],
            'tasks': [{'id': 'b4tcyp53v', 'action': 'rearmed', 'marker': self.marker + '1'}],
            'workers': [{'pane_id': 'wT:p2', 'status_seen': 'working', 'waiter_marker': self.marker + '2'}],
            'crons': [{'id': 'cr1', 'action': 'rearmed'}],
            'disagreements': [], 'questions': [], 'gaps': []}

    def spawn(self, script, *args):
        """A bash carrying a marker in its argv. The script must end in a loop, not a simple command: bash >= 5.1
        execs a final simple command, and `sleep 60` would replace bash and drop the marker. Own process group,
        so kill() takes the loop's sleep too. stderr: bash may report the sleep's SIGKILL before dying itself."""
        proc = subprocess.Popen(['bash', '-c', script, *args], start_new_session=True, stderr=subprocess.DEVNULL)
        self.procs.append(proc)
        return proc

    def kill(self, proc):
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait()

    def tearDown(self):
        for proc in self.procs:
            self.kill(proc)
        self.tmp.cleanup()

    def assert_alive(self, marker, alive=True):
        r = subprocess.run(['pgrep', '-f', marker], capture_output=True)
        self.assertEqual(r.returncode == 0, alive, '%r is %s: the test would pass for the wrong reason'
                         % (marker, 'not carried by any process' if alive else 'still carried by a process'))

    def fired(self, marker):
        (self.dir / 'fired').mkdir(exist_ok=True)
        (self.dir / 'fired' / marker).touch()

    def compare(self):
        (self.dir / 'checklist.json').write_text(json.dumps(self.checklist))
        (self.dir / 'receipt.json').write_text(json.dumps(self.receipt))
        return rc('compare', str(self.dir))

    def test_complete_receipt_passes(self):
        r = self.compare()
        self.assertEqual((r.returncode, r.stdout.strip()), (0, 'PASS'), r.stdout)

    def test_dropped_disk_watcher_fails(self):
        self.receipt['tasks'] = []
        r = self.compare()
        self.assertEqual(r.returncode, 1)
        self.assertIn('FAIL task b4tcyp53v (Watch free disk) is not in the receipt', r.stdout)

    def test_identity_mismatch_fails(self):
        self.receipt['successor']['effort'] = 'high'
        self.assertIn("identity: successor effort 'high', predecessor 'xhigh'", self.compare().stdout)

    def test_note_changed_after_the_successor_read_it_fails(self):
        self.note.write_text('# note\n## Relay Q&A\nanswer\n')
        self.assertIn('re-read it', self.compare().stdout)

    def test_dead_marker_fails(self):
        self.receipt['tasks'][0]['marker'] = self.marker + '9'
        self.assertIn("no live process carries marker '%s9'" % self.marker, self.compare().stdout)

    def test_a_live_marker_of_another_relay_fails(self):
        # From the second relay on, the predecessor's own waiters carry the previous relay's markers and stay
        # alive until the hand-over: copying one must not cover the task.
        old = 'relay-test%dold-w' % os.getpid()
        self.spawn(': %s1; while :; do sleep 1; done' % old)
        self.assert_alive(old + '1')
        self.receipt['tasks'][0]['marker'] = old + '1'
        self.receipt['workers'][0]['waiter_marker'] = old + '1'
        out = self.compare().stdout
        for what in ('task b4tcyp53v', 'worker wT:p2'):
            self.assertIn("FAIL %s: marker '%s1' is not this relay's (expected prefix '%s')"
                          % (what, old, self.marker), out)

    def test_a_generic_string_is_not_a_marker(self):
        for marker in ('while', ' ', None):
            with self.subTest(marker=marker):
                self.receipt['tasks'][0]['marker'] = marker
                self.assertIn("FAIL task b4tcyp53v: marker %r is not this relay's" % marker, self.compare().stdout)

    def test_a_fired_waiter_counts(self):
        # A waiter that fired between arming and the compare has exited; its fired file stands in for it.
        for proc in self.procs:
            self.kill(proc)
        for k in (1, 2):
            self.assert_alive('%s%d' % (self.marker, k), alive=False)
            self.fired('%s%d' % (self.marker, k))
        r = self.compare()
        self.assertEqual((r.returncode, r.stdout.strip()), (0, 'PASS'), r.stdout)

    def test_a_fired_file_does_not_rescue_another_relays_marker(self):
        old = 'relay-test%dold-w1' % os.getpid()
        self.fired(old)
        self.receipt['tasks'][0]['marker'] = old
        self.assertIn("FAIL task b4tcyp53v: marker '%s' is not this relay's" % old, self.compare().stdout)

    def test_a_longer_marker_does_not_stand_in_for_a_shorter_one(self):
        self.kill(self.procs[0])
        self.spawn(': %s10; while :; do sleep 1; done' % self.marker)
        self.assert_alive(self.marker + '10')
        self.assertIn("FAIL task b4tcyp53v: no live process carries marker '%s1'" % self.marker, self.compare().stdout)

    def test_a_marker_is_matched_literally(self):
        # Unescaped, the '.' would match the live '...-w1'.
        self.assert_alive(self.marker + '1')
        self.receipt['tasks'][0]['marker'] = self.marker + '.'
        self.assertIn("no live process carries marker '%s.'" % self.marker, self.compare().stdout)

    def test_a_marker_at_the_end_of_the_command_line_is_live(self):
        self.kill(self.procs[0])
        self.spawn('while :; do sleep 1; done', self.marker + '1')   # bash's $0: the last word of the argv
        self.assertEqual(self.compare().returncode, 0)

    def test_drop_needs_a_reason(self):
        self.receipt['tasks'] = [{'id': 'b4tcyp53v', 'action': 'drop', 'reason': ''}]
        self.assertIn('dropped without a reason', self.compare().stdout)
        self.receipt['tasks'] = [{'id': 'b4tcyp53v', 'action': 'drop', 'reason': 'disk is 60 GiB free'}]
        self.assertEqual(self.compare().returncode, 0)

    def test_missing_worker_cron_question_and_unexplained_drift_fail(self):
        self.receipt.update(workers=[], crons=[], questions=['what is the walkthrough headline?'],
                            tier='drift', drift=[{'item': 'HEAD moved', 'explanation': ''}])
        out = self.compare().stdout
        for text in ('worker wT:p2 (worker-a) is not in the receipt', 'cron cr1', 'open question: what is',
                     'unexplained drift: HEAD moved'):
            self.assertIn(text, out)

    def test_worker_status_change_does_not_fail_when_its_waiter_is_live(self):
        self.receipt['workers'][0]['status_seen'] = 'done'
        self.assertEqual(self.compare().returncode, 0)

    def test_unreadable_receipt_fails(self):
        (self.dir / 'checklist.json').write_text(json.dumps(self.checklist))
        r = rc('compare', str(self.dir))
        self.assertEqual(r.returncode, 1)
        self.assertIn('FAIL receipt.json unreadable', r.stdout)


class QuietTests(unittest.TestCase):
    def run_quiet(self, prompt_seconds, handover_second, extra=()):
        from handoff_fixtures import ts
        with tempfile.TemporaryDirectory() as tmp:
            path = write_transcript(tmp, SID, [prompt('p%d' % s, s) for s in prompt_seconds] + list(extra))
            rdir = Path(tmp) / 'relay' / 'R1'
            rdir.mkdir(parents=True)
            (rdir / 'checklist.json').write_text(json.dumps({'predecessor': {'transcript': str(path)}}))
            if handover_second is not None:
                (rdir / 'handover.md').write_text('# Hand-over R1\n')
                when = datetime.datetime.fromisoformat(ts(handover_second).replace('Z', '+00:00')).timestamp()
                os.utime(rdir / 'handover.md', (when, when))
            return rc('quiet', str(rdir))

    def test_no_prompt_after_the_handover_is_quiet(self):
        self.assertEqual(self.run_quiet([10], 30).returncode, 0)

    def test_a_prompt_after_the_handover_is_not_quiet(self):
        r = self.run_quiet([10, 40], 30)
        self.assertEqual(r.returncode, 1)
        self.assertIn('p40', r.stdout)

    def test_a_prompt_that_cannot_be_placed_in_time_is_not_quiet(self):
        # quiet gates closing the old lead: a prompt it cannot date counts as after the hand-over.
        garbled = dict(prompt('pgarbled', 20), timestamp='garbled')
        undated = {k: v for k, v in prompt('pundated', 20).items() if k != 'timestamp'}
        r = self.run_quiet([10], 30, extra=[garbled, undated])
        self.assertEqual(r.returncode, 1)
        self.assertIn('pgarbled', r.stdout)
        self.assertIn('pundated', r.stdout)

    def test_no_handover_yet_exits_2(self):
        # argparse also exits 2 (on an unknown subcommand): the reason pins which 2 this is.
        r = self.run_quiet([10], None)
        self.assertEqual(r.returncode, 2)
        self.assertIn('no handover.md', r.stderr)


if __name__ == '__main__':
    unittest.main()

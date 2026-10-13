import json
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import time
import unittest

from handoff_fixtures import SCRIPTS, agent_json, herdr_calls, herdr_stub

LAUNCH = SCRIPTS / 'relay-launch.sh'
SPLIT = {'out': json.dumps({'result': {'pane': {'pane_id': 'wT:p9'}}})}
BANNER = {'out': ' Claude Code v2.1.296\n Opus 5.5 with xhigh effort · Claude Max\n ~/code/repo\n'}


class LaunchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name) / 'relay' / 'R1'
        self.dir.mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def prepare(self, responses, mode='bypassPermissions', with_env=True, effort='xhigh'):
        (self.dir / 'checklist.json').write_text(json.dumps({
            'relay_id': 'R1', 'repo': '/x/repo',
            'predecessor': {'model': 'claude-opus-5-5', 'effort': effort, 'permission_mode': mode}}))
        for name in ('launch.json', 'failed.json'):
            (self.dir / name).unlink(missing_ok=True)
        env, self.log = herdr_stub(self.tmp.name, responses)
        if not with_env:
            env.pop('HERDR_ENV')
        return env

    def launch(self, responses, mode='bypassPermissions', with_env=True, effort='xhigh', locale=None, timeout=None):
        env = self.prepare(responses, mode, with_env, effort)
        if locale:
            env['LC_ALL'] = locale
        return subprocess.run(['bash', str(LAUNCH), str(self.dir)], capture_output=True, text=True, env=env,
                              timeout=timeout)

    def call(self, verb):
        return [c for c in herdr_calls(self.log) if c[:2] == verb]

    def test_starts_the_successor_with_matching_identity_and_sends_pickup(self):
        r = self.launch({'pane split': [SPLIT], 'pane read': [BANNER],
                         'agent get': [{'out': agent_json('idle', session='S2', pane='wT:p9')}]})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), 'wT:p9')
        start = self.call(['agent', 'start'])[0]
        self.assertEqual(start[2:7], ['lead-repo-next', '--kind', 'claude', '--pane', 'wT:p9'])
        tail = start[start.index('--', 7) + 1:]
        self.assertEqual(tail[:2], ['--model', 'claude-opus-5-5'])
        self.assertIn('--session-id', tail)
        self.assertEqual(tail[tail.index('--effort') + 1], 'xhigh')
        self.assertIn('--dangerously-skip-permissions', tail)
        self.assertEqual(self.call(['agent', 'prompt'])[0][2:], ['lead-repo-next', '/pickup relay=%s' % self.dir])
        launch = json.loads((self.dir / 'launch.json').read_text())
        self.assertEqual((launch['pane_id'], launch['name'], launch['session_id']), ('wT:p9', 'lead-repo-next', 'S2'))

    def test_default_permission_mode_adds_no_bypass_flag(self):
        r = self.launch({'pane split': [SPLIT], 'pane read': [BANNER]}, mode='default')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn('--dangerously-skip-permissions', self.call(['agent', 'start'])[0])

    def test_two_failed_starts_close_the_pane_and_record_failure(self):
        r = self.launch({'pane split': [SPLIT], 'agent start': [{'out': 'boom', 'code': 1}]})
        self.assertEqual(r.returncode, 1)
        self.assertEqual(len(self.call(['agent', 'start'])), 2)
        self.assertEqual(self.call(['pane', 'close']), [['pane', 'close', 'wT:p9']])
        failed = json.loads((self.dir / 'failed.json').read_text())
        self.assertEqual((failed['stage'], failed['reason'], failed['attempts']), ('launch', 'agent start failed twice', 2))
        self.assertFalse((self.dir / 'launch.json').exists())

    def test_banner_without_the_model_fails(self):
        r = self.launch({'pane split': [SPLIT], 'pane read': [{'out': ' Haiku 5.5 with xhigh effort\n'}]})
        self.assertEqual(r.returncode, 1)
        self.assertIn("banner does not show model 'Opus 5.5'", json.loads((self.dir / 'failed.json').read_text())['reason'])
        self.assertEqual(self.call(['pane', 'close']), [['pane', 'close', 'wT:p9']])
        self.assertEqual(self.call(['agent', 'prompt']), [])

    def test_effort_must_appear_as_a_whole_word(self):
        r = self.launch({'pane split': [SPLIT], 'pane read': [{'out': ' Opus 5.5 with xhigh effort\n'}]}, effort='high')
        self.assertEqual(r.returncode, 1)
        self.assertIn("banner does not show effort 'high'", json.loads((self.dir / 'failed.json').read_text())['reason'])
        self.assertEqual(self.call(['pane', 'close']), [['pane', 'close', 'wT:p9']])
        self.assertEqual(self.call(['agent', 'prompt']), [])
        self.assertFalse((self.dir / 'launch.json').exists())

    def test_effort_as_its_own_word_passes(self):
        for banner in (' Opus 5.5 with high effort · Claude Max\n', ' Opus 5.5 · Claude Max\n ◐ high · /effort\n'):
            with self.subTest(banner=banner):
                r = self.launch({'pane split': [SPLIT], 'pane read': [{'out': banner}]}, effort='high')
                self.assertEqual(r.returncode, 0, r.stderr)

    def test_a_pane_sized_banner_is_checked_in_linear_time(self):
        # bash 3.2 took about a minute to rewrite a 200x50 banner word by word under a UTF-8 locale.
        rows = ['\u2502' + '\u2500' * 198 + '\u2502'] * 50
        rows[3] = ' Opus 5.5 with xhigh effort \u00b7 Claude Max'.ljust(200)
        big = {'out': '\n'.join(rows) + '\n'}
        for effort, code in (('xhigh', 0), ('high', 1)):
            with self.subTest(effort=effort):
                began = time.monotonic()
                r = self.launch({'pane split': [SPLIT], 'pane read': [big]}, effort=effort,
                                locale='en_US.UTF-8', timeout=60)
                self.assertLess(time.monotonic() - began, 5)
                self.assertEqual(r.returncode, code, r.stderr)

    def test_a_killed_launch_closes_its_pane_and_records_failure(self):
        # Killing the whole tree (as a tool timeout does) must not wait out the start; killing only the
        # script lets the start return first. Either way the created pane is closed and the failure recorded.
        for group, sleep in ((True, 30), (False, 1)):
            with self.subTest(kill='process group' if group else 'script only'):
                env = self.prepare({'pane split': [SPLIT], 'agent start': [{'out': '{}', 'sleep': sleep}]})
                proc = subprocess.Popen(['bash', str(LAUNCH), str(self.dir)], env=env, start_new_session=True,
                                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                deadline = time.monotonic() + 10
                while not self.call(['agent', 'start']) and time.monotonic() < deadline:
                    time.sleep(0.05)
                self.assertTrue(self.call(['agent', 'start']), 'the script never reached agent start')
                (os.killpg if group else os.kill)(proc.pid, signal.SIGTERM)
                _, err = proc.communicate(timeout=15)
                self.assertEqual(proc.returncode, 1, err)
                self.assertEqual(json.loads((self.dir / 'failed.json').read_text())['reason'], 'interrupted')
                self.assertEqual(self.call(['pane', 'close']), [['pane', 'close', 'wT:p9']])
                self.assertFalse((self.dir / 'launch.json').exists())

    def test_outside_herdr_exits_2(self):
        self.assertEqual(self.launch({}, with_env=False).returncode, 2)


if __name__ == '__main__':
    unittest.main()

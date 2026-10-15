"""relaylib's herdr helpers: bounded reads, agent start with the busy-pane retry, and the banner check."""
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

from handoff_fixtures import SCRIPTS, herdr_calls, herdr_stub

sys.path.insert(0, str(SCRIPTS))
import relaylib  # noqa: E402

BUSY = {'out': json.dumps({'error': {'code': 'agent_pane_busy', 'message': 'not an available shell'}}), 'code': 1}
NOT_READY = {'out': json.dumps({'error': {'code': 'agent_not_ready', 'message': 'blocked during startup'}}),
             'code': 1}


class HerdrTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tmp.cleanup()

    def stub(self, responses):
        env, self.log = herdr_stub(self.tmp.name, responses)
        patcher = mock.patch.dict(os.environ, env)
        patcher.start()
        self.addCleanup(patcher.stop)

    def calls(self, verb):
        return [c for c in herdr_calls(self.log) if c[:2] == verb]


class HerdrJsonTests(HerdrTestCase):
    def test_a_herdr_that_does_not_answer_is_an_error_within_the_bound(self):
        self.stub({'agent list': [{'out': '{"result": {"agents": []}}', 'sleep': 5}]})
        began = time.monotonic()
        with self.assertRaisesRegex(relaylib.HerdrError, 'did not answer within 1 s'):
            relaylib.herdr_list('agents', 'agent', 'list', timeout=1)
        self.assertLess(time.monotonic() - began, 4)

    def test_the_fake_herdr_lifts_the_bound_and_the_override_is_read(self):
        # Under load (about 30 on 10 cores) a fake herdr once took over 10 s to start, failing two checklist tests
        # that are not about the bound.
        env, _ = herdr_stub(self.tmp.name, {})
        self.assertEqual(env['RELAYLIB_HERDR_BOUND'], '120')
        r = subprocess.run(['python3', '-I', '-B', '-c', 'import sys; sys.path.insert(0, sys.argv[1]); import relaylib; '
                            'print(relaylib.HERDR_BOUND)', str(SCRIPTS)], env=env, capture_output=True, text=True)
        self.assertEqual(r.stdout.strip(), '120.0', r.stderr)

    def test_a_listing_of_another_shape_is_an_error_not_an_empty_list(self):
        self.stub({'pane list': [{'out': '{"result": {"panes": {}}}'}]})
        with self.assertRaisesRegex(relaylib.HerdrError, 'result.panes is not a list'):
            relaylib.herdr_list('panes', 'pane', 'list')

    def test_herdr_errors_carry_the_error_code(self):
        self.stub({'agent get': [NOT_READY]})
        with self.assertRaises(relaylib.HerdrError) as cm:
            relaylib.herdr_json('agent', 'get', 'wT:p2')
        self.assertEqual(cm.exception.code, 'agent_not_ready')

    def test_text_reads_are_bounded_too(self):
        self.stub({'pane read': [{'out': 'hello\n'}]})
        self.assertEqual(relaylib.herdr_text('pane', 'read', 'wT:p2', '--source', 'visible'), 'hello\n')


class StartAgentTests(HerdrTestCase):
    def test_a_busy_pane_is_retried_inside_the_attempt(self):
        self.stub({'agent start': [BUSY, BUSY, {'out': '{}'}]})
        self.assertEqual(relaylib.start_agent('w-xhigh-ab12', 'codex', 'wT:p9', ['-m', 'x'], busy_wait=10),
                         (True, ''))
        starts = self.calls(['agent', 'start'])
        self.assertEqual(len(starts), 3)
        self.assertEqual(starts[0], ['agent', 'start', 'w-xhigh-ab12', '--kind', 'codex', '--pane', 'wT:p9',
                                     '--timeout', '90000', '--', '-m', 'x'])

    def test_two_failed_attempts(self):
        self.stub({'agent start': [{'out': 'boom', 'code': 1}]})
        ok, out = relaylib.start_agent('n', 'claude', 'wT:p9', [], busy_wait=1)
        self.assertEqual((ok, out), (False, 'boom'))
        self.assertEqual(len(self.calls(['agent', 'start'])), 2)

    def test_a_stop_code_ends_the_start_at_once(self):
        self.stub({'agent start': [NOT_READY, {'out': '{}'}]})
        ok, out = relaylib.start_agent('n', 'claude', 'wT:p9', [], stop_on=('agent_not_ready',))
        self.assertFalse(ok)
        self.assertIn('agent_not_ready', out)
        self.assertEqual(len(self.calls(['agent', 'start'])), 1)


class BannerTests(unittest.TestCase):
    def test_claude_model_ids_read_as_the_banner_names_them(self):
        self.assertEqual(relaylib.banner_model('claude', 'claude-opus-5-5'), 'Opus 5.5')
        self.assertEqual(relaylib.banner_model('codex', 'gpt-6.1-sol'), 'gpt-6.1-sol')

    def test_model_is_matched_without_case_and_effort_as_a_whole_word(self):
        codex = '  GPT-6.1-Sol xhigh · ~/code/repo · main · Context 100% left\n'
        self.assertIsNone(relaylib.banner_problem(codex, 'gpt-6.1-sol', 'xhigh'))
        self.assertEqual(relaylib.banner_problem(codex, 'gpt-6.1-sol', 'high'), "banner does not show effort 'high'")
        self.assertEqual(relaylib.banner_problem(codex, 'Opus 5.5', 'xhigh'), "banner does not show model 'Opus 5.5'")
        self.assertIsNone(relaylib.banner_problem(' Opus 5.5 · Claude Max\n ◐ high · /effort\n', 'Opus 5.5', 'high'))

    def test_no_effort_checks_the_model_only(self):
        self.assertIsNone(relaylib.banner_problem('Opus 5.5', 'Opus 5.5', ''))


class ReadBannerTests(HerdrTestCase):
    # One read failed 2 of 8 relay launches at load ~35-48 (2026-10-14): a pane fresh from a start can read blank.
    # The tests that wait for a late banner pass a long bound, so a loaded machine cannot end them early.
    def test_a_banner_drawn_late_is_read_again(self):
        banner = ' Opus 5.5 with xhigh effort\n'
        self.stub({'pane read': [{'out': '\n\n'}, {'out': ''}, {'out': banner}]})
        self.assertEqual(relaylib.read_banner('wT:p9', 'Opus 5.5', 'xhigh', bound=120), (None, banner))
        self.assertEqual(len(self.calls(['pane', 'read'])), 3)

    def test_a_banner_that_never_shows_returns_the_last_problem_and_text(self):
        self.stub({'pane read': [{'out': ' Haiku 5.5 with xhigh effort\n'}]})
        self.assertEqual(relaylib.read_banner('wT:p9', 'Opus 5.5', 'xhigh', bound=0),
                         ("banner does not show model 'Opus 5.5'", ' Haiku 5.5 with xhigh effort\n'))

    def test_an_unreadable_pane_ends_the_check_at_once(self):
        self.stub({'pane read': [{'out': 'gone', 'code': 1}]})
        with self.assertRaises(relaylib.HerdrError):
            relaylib.read_banner('wT:p9', 'Opus 5.5', 'xhigh', bound=120)
        self.assertEqual(len(self.calls(['pane', 'read'])), 1)

    def test_the_fake_herdr_reads_a_banner_once_and_the_override_is_read(self):
        env, _ = herdr_stub(self.tmp.name, {})
        self.assertEqual(env['RELAYLIB_BANNER_SECONDS'], '0')
        env['RELAYLIB_BANNER_SECONDS'] = '3'
        r = subprocess.run(['python3', '-I', '-B', '-c', 'import sys; sys.path.insert(0, sys.argv[1]); import relaylib; '
                            'print(relaylib.BANNER_BOUND)', str(SCRIPTS)], env=env, capture_output=True, text=True)
        self.assertEqual(r.stdout.strip(), '3.0', r.stderr)


class CliTests(unittest.TestCase):
    def test_start_report_keeps_attempts_and_the_last_error_after_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            env, _ = herdr_stub(tmp, {'agent start': [{'out': 'first error', 'code': 1}, {'out': '{}'}]})
            report = os.path.join(tmp, 'start.json')
            r = subprocess.run(['python3', '-I', str(SCRIPTS / 'relaylib.py'), 'start-agent', 'lead-x-next',
                                'claude', 'wT:p9', '0', '--report', report, '--'], env=env,
                               capture_output=True, text=True, timeout=60)
            self.assertEqual(r.returncode, 0, r.stderr)
            with open(report) as fh:
                self.assertEqual(json.load(fh), {'attempts': 2, 'last_error': 'first error'})

    def run_cli(self, responses, *args, env=None):
        with tempfile.TemporaryDirectory() as tmp:
            full, log = herdr_stub(tmp, responses)
            full.update(env or {})
            r = subprocess.run(['python3', '-I', str(SCRIPTS / 'relaylib.py'), *args], capture_output=True,
                               text=True, env=full, timeout=60)
            return r, herdr_calls(log)

    def test_check_banner_prints_the_problem_and_what_the_pane_shows(self):
        r, _ = self.run_cli({'pane read': [{'out': ' Haiku 5.5 with xhigh effort\n ~/code/repo\n'}]},
                            'check-banner', 'wT:p9', 'claude', 'claude-opus-5-5', 'xhigh')
        self.assertEqual((r.returncode, r.stdout.strip()),
                         (1, "banner does not show model 'Opus 5.5' (pane shows: Haiku 5.5 with xhigh effort | "
                             "~/code/repo)"))

    def test_check_banner_reads_a_late_banner_again(self):
        r, calls = self.run_cli({'pane read': [{'out': ''}, {'out': ' Opus 5.5 with xhigh effort\n'}]},
                                'check-banner', 'wT:p9', 'claude', 'claude-opus-5-5', 'xhigh',
                                env={'RELAYLIB_BANNER_SECONDS': '120'})
        self.assertEqual((r.returncode, r.stdout), (0, ''), r.stderr)
        self.assertEqual(len([c for c in calls if c[:2] == ['pane', 'read']]), 2)

    def test_check_banner_on_an_unreadable_pane(self):
        r, _ = self.run_cli({'pane read': [{'out': 'gone', 'code': 1}]},
                            'check-banner', 'wT:p9', 'claude', 'claude-opus-5-5', 'xhigh')
        self.assertEqual((r.returncode, r.stdout.strip()), (1, 'could not read the new pane'))

    def test_start_agent_passes_the_native_arguments_through(self):
        r, calls = self.run_cli({'agent start': [{'out': '{}'}]},
                                'start-agent', 'lead-x-next', 'claude', 'wT:p9', '15', '--', '--model', 'm')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(calls[0][-3:], ['--', '--model', 'm'])


if __name__ == '__main__':
    unittest.main()

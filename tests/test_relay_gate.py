import datetime
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest import mock
import uuid

from handoff_fixtures import (SCRIPTS, agent_json, agents_killed, cron_fire, herdr_calls, herdr_stub, hook_cancelled,
                              hook_context, prompt, teammate_spawn, tool_result, tool_use, usage, write_transcript)
from test_relaylib import make_relay, slow_git

GATE = SCRIPTS / 'relay-gate.py'
SID = '55555555-5555-4555-8555-555555555555'


def load_gate():
    spec = importlib.util.spec_from_file_location('relay_gate', GATE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def iso(seconds_ago):
    when = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=seconds_ago)
    return when.isoformat().replace('+00:00', 'Z')


def ago(timestamp):
    """Seconds since an ISO UTC timestamp."""
    return time.time() - datetime.datetime.fromisoformat(timestamp.replace('Z', '+00:00')).timestamp()


def shell(tid, desc='Wait for r', status='running'):
    return {'id': tid, 'type': 'shell', 'status': status, 'description': desc, 'command': 'until [ -f r ]; do sleep 5; done'}


def git_repo(root):
    repo = Path(root) / 'repo'
    repo.mkdir()
    subprocess.run(['git', 'init', '-q', str(repo)], check=True)
    return Path(os.path.realpath(repo))


class GateCase(unittest.TestCase):
    """A project dir under a fake ~/.claude/projects, a git repo as cwd, and a fake herdr."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.home = root / 'home'
        self.home.mkdir()
        self.projects = root / 'projects'
        self.project = self.projects / '-tmp-repo'
        self.project.mkdir(parents=True)
        self.repo = git_repo(root)
        self.recs = [usage(100_000, 1)]
        self.herd({'agent get': [{'out': agent_json('idle', pane='wT:p1', name='worker-high')}]})
        self.extra_env = {}
        self.printed = {}    # tool_use_id -> what the gate printed after that tool call

    def tearDown(self):
        self.tmp.cleanup()

    def herd(self, responses):
        self.env, self.log = herdr_stub(self.tmp.name, responses)
        self.env = {k: v for k, v in self.env.items() if not k.startswith('RELAY_GATE_')}
        self.env['HOME'] = str(self.home)

    def make_lead(self):
        (self.project / 'relay').mkdir(exist_ok=True)
        (self.project / 'relay' / 'lead.json').write_text(json.dumps({'session_id': SID, 'name': 'lead-repo'}))

    def at(self, pct, *before):
        """The transcript: `before` records, then a main-thread usage record at pct of a 1M window."""
        self.recs = list(before) + [usage(int(pct * 10_000), 50)]

    def gate(self, mode='stop', tasks=(), env=None, **fields):
        path = write_transcript(self.projects, SID, self.recs)
        inp = {'session_id': SID, 'transcript_path': str(path), 'cwd': str(self.repo),
               'hook_event_name': 'Stop' if mode == 'stop' else 'PostToolUse', 'prompt_id': str(uuid.uuid4()),
               'background_tasks': list(tasks), 'stop_hook_active': False}
        if mode == 'tool':
            inp.update(tool_name='Bash', tool_input={'command': 'ls'}, tool_use_id='toolu_%s' % uuid.uuid4().hex[:24])
            del inp['background_tasks'], inp['stop_hook_active']
        inp.update(fields)
        inp = {k: v for k, v in inp.items() if v is not None}
        run_env = dict(self.env)
        run_env.update(self.extra_env)
        run_env.update(env or {})
        r = subprocess.run(['python3', '-I', str(GATE), mode], input=json.dumps(inp), capture_output=True, text=True,
                           env=run_env, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout) if r.stdout.strip() else None
        if out is not None and inp.get('tool_use_id'):
            self.printed[inp['tool_use_id']] = out
        return out

    def state(self):
        path = self.project / 'relay' / 'gate' / (SID + '.json')
        return json.loads(path.read_text()) if path.exists() else None

    def toasts(self, expect, wait=3.0):
        """The toasts raised so far: they are detached, so wait until `expect` arrived, then a little longer."""
        end = time.time() + wait
        while time.time() < end:
            got = [c for c in herdr_calls(self.log) if c[:2] == ['notification', 'show']]
            if len(got) >= expect:
                break
            time.sleep(0.05)
        time.sleep(0.3)
        return [c for c in herdr_calls(self.log) if c[:2] == ['notification', 'show']]

    def assertAsk(self, out, attempt=1):
        self.assertIsNotNone(out)
        self.assertEqual(out['decision'], 'block')
        self.assertIn('Run /relay now, automatic relay attempt %d of 2.' % attempt, out['reason'])


class IdentityTests(GateCase):
    def test_outside_herdr_nothing_happens(self):
        self.make_lead()
        self.at(52)
        env = {k: v for k, v in self.env.items() if k != 'HERDR_ENV'}
        self.env = env
        self.assertIsNone(self.gate())
        self.assertIsNone(self.state())

    def test_a_subagent_or_teammate_is_never_gated(self):
        self.make_lead()
        self.at(52)
        for agent in ('ac8338d111984a8ec', 'aprobe-teammate-e833e05d3a936ff6'):
            for mode in ('stop', 'tool'):
                self.assertIsNone(self.gate(mode, agent_id=agent, agent_type='general-purpose'), (agent, mode))
        self.assertIsNone(self.state())
        self.assertFalse((self.project / 'relay' / 'gate').exists())

    def test_the_child_session_flag_does_not_exempt_the_lead(self):
        self.make_lead()
        self.at(52)
        self.assertAsk(self.gate(env={'CLAUDE_CODE_CHILD_SESSION': '1'}))

    def test_lead_json_is_a_fast_path_with_no_herdr_call(self):
        self.make_lead()
        self.at(52)
        self.assertAsk(self.gate())
        self.assertEqual([c for c in herdr_calls(self.log) if c[:2] == ['agent', 'get']], [])

    def test_a_lead_name_is_gated(self):
        self.herd({'agent get': [{'out': agent_json('idle', pane='wT:p1', name='lead-repo')}]})
        self.at(52)
        self.assertAsk(self.gate())
        self.assertEqual(self.state()['asked']['band'], 50)

    def test_a_worker_is_never_gated_and_gets_no_state(self):
        self.at(52)
        self.assertIsNone(self.gate())
        self.assertIsNone(self.gate('tool'))
        self.assertFalse((self.project / 'relay').exists())

    def test_an_input_without_a_transcript_or_session_is_ignored(self):
        self.make_lead()
        self.at(52)
        self.assertIsNone(self.gate(transcript_path=None))
        self.assertIsNone(self.gate(session_id=None))
        self.assertFalse((self.project / 'relay' / 'gate').exists())

    def test_below_the_threshold_nothing_is_read_or_written(self):
        self.at(49.9)
        self.assertIsNone(self.gate())
        self.assertEqual(herdr_calls(self.log), [])
        self.assertFalse((self.project / 'relay').exists())

    def test_an_unknown_model_toasts_a_lead_once_and_stays_inert(self):
        self.make_lead()
        self.recs = [usage(600_000, 1, model='claude-sonnet-5-5')]
        self.assertIsNone(self.gate())
        self.assertIsNone(self.gate())
        toasts = self.toasts(1)
        self.assertEqual(len(toasts), 1, toasts)
        self.assertIn('claude-sonnet-5-5', ' '.join(toasts[0]))
        self.assertEqual(self.state()['toasted'], ['unknown-model'])

    def test_an_unknown_model_on_a_worker_is_silent(self):
        self.recs = [usage(600_000, 1, model='claude-sonnet-5-5')]
        self.assertIsNone(self.gate())
        self.assertEqual(self.toasts(0, wait=0.2), [])


class StateTests(GateCase):
    def test_an_old_state_without_hold_keeps_its_existing_bands(self):
        gate = load_gate()
        path = Path(self.tmp.name) / 'old-state.json'
        older = {k: v for k, v in dict(gate.fresh(), nudged=[50]).items() if k != 'hold'}
        path.write_text(json.dumps(older))
        self.assertEqual(gate.load_state(str(path)), dict(older, hold=None))

    def test_a_wrong_shaped_state_is_a_fresh_one(self):
        self.make_lead()
        self.at(52)
        gate_dir = self.project / 'relay' / 'gate'
        gate_dir.mkdir(parents=True)
        (gate_dir / (SID + '.json')).write_text(json.dumps({'version': 1, 'nudged': 'fifty',
                                                            'asked': {'band': 50, 'attempt': 1, 'tasks': [],
                                                                      'count': 3}}))
        self.assertAsk(self.gate())
        self.assertEqual(self.state()['asked']['count'], 1)

    def test_the_state_is_written_whole_and_no_temp_file_is_left(self):
        self.make_lead()
        self.at(52)
        self.gate()
        state = self.state()
        self.assertEqual((state['version'], state['meter']['pct']), (1, 52.0))
        self.assertEqual(sorted(p.name for p in (self.project / 'relay' / 'gate').iterdir()), [SID + '.json'])

    def test_other_sessions_old_state_files_are_pruned(self):
        self.make_lead()
        self.at(52)
        gate_dir = self.project / 'relay' / 'gate'
        gate_dir.mkdir(parents=True)
        old, recent = gate_dir / 'old-session.json', gate_dir / 'recent-session.json'
        for path in (old, recent):
            path.write_text('{}')
        week = time.time() - 8 * 24 * 3600
        os.utime(old, (week, week))
        self.gate()
        self.assertFalse(old.exists())
        self.assertTrue(recent.exists())

    def test_bands_follow_the_threshold(self):
        gate = load_gate()
        cfg = gate.Config({'RELAY_GATE_THRESHOLD': '7', 'RELAY_GATE_STEP': '1'})
        self.assertEqual([gate.band_of(p, cfg) for p in (7.0, 7.9, 8.2, 10.5)], [7, 7, 8, 10])
        cfg = gate.Config({})
        self.assertEqual([gate.band_of(p, cfg) for p in (50.0, 59.9, 60.0, 83.8)], [50, 50, 60, 80])
        self.assertEqual((cfg.threshold, cfg.cap, cfg.step, cfg.backoff, cfg.throttle, cfg.owner, cfg.window),
                         (50, 60, 10, 1800, 60, 600, None))
        self.assertEqual(gate.Config({'RELAY_GATE_STEP': '0', 'RELAY_GATE_CAP': 'x'}).step, 10)

    def test_a_drop_of_more_than_a_step_above_the_threshold_forgets_the_bands(self):
        gate = load_gate()
        cfg = gate.Config({})
        when = iso(5)

        def at_80():
            return dict(gate.fresh(), nudged=[80], alerted=[80], drain_owed=True,
                        asked={'band': 80, 'attempt': 1, 'tasks': [], 'count': 1},
                        pending={'band': 80, 'tool_use_id': 'toolu_A', 'drain': True, 'at': when})

        for pct in (72, 70):    # one step below the lowest band is not more than one step
            state = at_80()
            self.assertFalse(gate.reset_bands(state, pct, cfg), pct)
            self.assertEqual(state, at_80(), pct)
        state = at_80()
        self.assertTrue(gate.reset_bands(state, 55, cfg))
        self.assertEqual(state, dict(at_80(), nudged=[], alerted=[], asked=None, drain_owed=False, pending=None))

    def test_a_pending_band_alone_is_forgotten_after_a_drop_of_more_than_a_step(self):
        gate = load_gate()
        cfg = gate.Config({})

        def pending_80():
            return dict(gate.fresh(), pending={'band': 80, 'tool_use_id': 'toolu_A', 'drain': False, 'at': 'x'})

        state = pending_80()
        self.assertFalse(gate.reset_bands(state, 70, cfg))
        self.assertEqual(state, pending_80())
        state = pending_80()
        self.assertTrue(gate.reset_bands(state, 69, cfg))
        self.assertEqual(state, gate.fresh())

    def test_a_state_file_without_pending_loads_with_pending_none(self):
        gate = load_gate()
        path = Path(self.tmp.name) / 'state.json'
        older = {k: v for k, v in dict(gate.fresh(), nudged=[50]).items() if k != 'pending'}
        path.write_text(json.dumps(older))
        self.assertEqual(gate.load_state(str(path)), dict(older, pending=None))

    def test_a_wrong_shaped_pending_is_a_fresh_state(self):
        gate = load_gate()
        path = Path(self.tmp.name) / 'state.json'
        good = {'band': 50, 'tool_use_id': 'toolu_A', 'drain': False, 'at': iso(5)}
        for ok in (good, dict(good, band=50.5)):
            path.write_text(json.dumps(dict(gate.fresh(), nudged=[50], pending=ok)))
            self.assertEqual(gate.load_state(str(path))['pending'], ok)
        no_id = {k: v for k, v in good.items() if k != 'tool_use_id'}
        for bad in ([], 'toolu_A', dict(good, band=True), dict(good, band='50'), dict(good, tool_use_id=''),
                    dict(good, tool_use_id=7), no_id, dict(good, drain=0), dict(good, at=None)):
            with self.subTest(bad=bad):
                path.write_text(json.dumps(dict(gate.fresh(), nudged=[50], pending=bad)))
                self.assertEqual(gate.load_state(str(path)), gate.fresh())

class FailOpenTests(GateCase):
    def test_garbage_input_is_logged_and_toasted_once(self):
        for _ in range(2):
            r = subprocess.run(['python3', '-I', str(GATE), 'stop'], input='{torn', capture_output=True, text=True,
                               env=self.env, timeout=30)
            self.assertEqual((r.returncode, r.stdout), (0, ''))
        log = (self.home / '.claude' / 'relay-gate-errors.log').read_text()
        self.assertEqual(log.count('== '), 2)
        self.assertIn('JSONDecodeError', log)
        self.assertTrue((self.home / '.claude' / 'relay-gate-unknown.error').exists())
        self.assertEqual(len(self.toasts(1)), 1)

    def test_a_raising_helper_is_logged_beside_the_project(self):
        self.make_lead()
        broken = self.project / ('%s.jsonl' % SID)
        broken.mkdir()
        inp = {'session_id': SID, 'transcript_path': str(broken), 'cwd': str(self.repo), 'background_tasks': []}
        r = subprocess.run(['python3', '-I', str(GATE), 'stop'], input=json.dumps(inp), capture_output=True,
                           text=True, env=self.env, timeout=30)
        self.assertEqual((r.returncode, r.stdout), (0, ''))
        gate_dir = self.project / 'relay' / 'gate'
        self.assertIn('IsADirectoryError', (gate_dir / 'errors.log').read_text())
        self.assertTrue((gate_dir / (SID + '.error')).exists())
        self.assertEqual(len(self.toasts(1)), 1)

    def test_the_error_log_is_trimmed(self):
        log = self.home / '.claude' / 'relay-gate-errors.log'
        log.parent.mkdir()
        log.write_text('x' * 150_000)
        subprocess.run(['python3', '-I', str(GATE), 'stop'], input='[]', capture_output=True, text=True,
                       env=self.env, timeout=30)
        self.assertLessEqual(log.stat().st_size, 100 * 1024)
        self.assertIn('not a JSON object', log.read_text())

    def test_a_usage_error_never_exits_2(self):
        r = subprocess.run(['python3', '-I', str(GATE)], input='{}', capture_output=True, text=True, env=self.env)
        self.assertEqual(r.returncode, 1)

    def test_the_toast_is_detached_and_its_failure_changes_nothing(self):
        self.herd({'notification show': [{'out': 'boom', 'code': 1, 'sleep': 3}]})
        self.make_lead()
        self.recs = [usage(600_000, 1, model='claude-sonnet-5-5')]
        started = time.time()
        self.assertIsNone(self.gate())
        self.assertLess(time.time() - started, 2.5)
        self.assertEqual(self.state()['toasted'], ['unknown-model'])

    def test_the_state_is_written_before_the_output(self):
        gate = load_gate()
        self.make_lead()
        self.at(52)
        path = write_transcript(self.projects, SID, self.recs)
        state_path = self.project / 'relay' / 'gate' / (SID + '.json')
        seen = []

        class Out(io.StringIO):
            def write(self, text):
                seen.append(state_path.exists() and json.loads(state_path.read_text())['asked'] is not None)
                return super().write(text)

        inp = json.dumps({'session_id': SID, 'transcript_path': str(path), 'cwd': str(self.repo),
                          'background_tasks': []})
        with mock.patch.dict(os.environ, self.env, clear=True), mock.patch.object(sys, 'stdin', io.StringIO(inp)), \
                mock.patch.object(sys, 'stdout', Out()):
            self.assertEqual(gate.main(['stop']), 0)
        self.assertEqual(seen, [True])

    def ask_with_a_toast(self, gate, body):
        """main(['stop']) in-process for a lead at 52% whose decision also queues a toast: (exit code, output)."""
        self.make_lead()
        self.at(52)
        path = write_transcript(self.projects, SID, self.recs)
        inp = json.dumps({'session_id': SID, 'transcript_path': str(path), 'cwd': str(self.repo),
                          'background_tasks': []})
        asks = gate.decide

        def decide(call, state, pct, band):
            call.toasts.append(('Relay gate: repo', body))
            return asks(call, state, pct, band)

        out = io.StringIO()
        with mock.patch.dict(os.environ, self.env, clear=True), mock.patch.object(sys, 'stdin', io.StringIO(inp)), \
                mock.patch.object(sys, 'stdout', out), mock.patch.object(gate, 'decide', decide):
            code = gate.main(['stop'])
        return code, (json.loads(out.getvalue()) if out.getvalue() else None)

    def assertToastFailureChangesNothing(self, code, out, error):
        self.assertEqual(code, 0)
        self.assertAsk(out)
        self.assertEqual(self.state()['asked']['count'], 1)
        gate_dir = self.project / 'relay' / 'gate'
        self.assertIn(error, (gate_dir / 'errors.log').read_text())
        self.assertFalse((gate_dir / (SID + '.error')).exists())    # logged, never a second toast
        self.assertEqual(self.toasts(0, wait=0.2), [])

    def test_a_toast_body_with_a_nul_byte_changes_neither_the_exit_code_nor_the_output(self):
        code, out = self.ask_with_a_toast(load_gate(), 'Open task: a description with a NUL \x00 byte')
        self.assertToastFailureChangesNothing(code, out, 'ValueError')

    def test_a_toast_that_cannot_start_for_any_reason_changes_nothing(self):
        gate = load_gate()
        real = gate.subprocess.Popen

        def no_herdr(args, *rest, **kwargs):    # the gate's own git calls (relaylib.blockers) still run
            if args and args[0] == 'herdr':
                raise RuntimeError('cannot spawn')
            return real(args, *rest, **kwargs)

        with mock.patch.object(gate.subprocess, 'Popen', side_effect=no_herdr):
            code, out = self.ask_with_a_toast(gate, 'Lead repo is at 62%')
        self.assertToastFailureChangesNothing(code, out, 'RuntimeError: cannot spawn')


class StopTests(GateCase):
    def test_a_hold_records_unsafe_tasks_and_the_time(self):
        self.make_lead()
        self.at(52)
        self.assertIsNone(self.gate(tasks=[{'id': 'a1', 'type': 'subagent', 'status': 'running',
                                          'description': 'review'}]))
        held = self.state().get('hold')
        self.assertIsNotNone(held)
        self.assertEqual(held['reasons'], ['subagent a1 is running (review)'])
        self.assertLess(abs(ago(held['at'])), 30)
        self.assertAsk(self.gate())
        self.assertIsNone(self.state()['hold'])

    def test_a_hold_records_transcript_blockers(self):
        self.make_lead()
        self.at(52, tool_use('a1', 'Agent', {'description': 'review'}),
                tool_result('a1', 'running', tool_use_result={'status': 'async_launched', 'agentId': 'agent1'}))
        self.assertIsNone(self.gate())
        self.assertEqual((self.state().get('hold') or {}).get('reasons'),
                         ['agent agent1 is running inside this session (review)'])

    def test_a_hold_records_owner_recent(self):
        self.make_lead()
        self.at(52, dict(prompt('status?'), timestamp=iso(1)))
        self.assertIsNone(self.gate())
        self.assertEqual((self.state().get('hold') or {}).get('reasons'), ['owner_recent'])

    def test_a_hold_records_the_relay_hold(self):
        self.make_lead()
        self.at(52)
        make_relay(self.project, 'R-active', session=SID)
        self.assertIsNone(self.gate())
        held = self.state().get('hold')
        self.assertIsNotNone(held)
        self.assertEqual(held['reasons'], ['relay_hold:in_progress'])
        self.assertLess(abs(ago(held['at'])), 30)

    def test_a_hold_from_a_tool_hook_records_the_relay_hold(self):
        self.make_lead()
        self.at(52)
        make_relay(self.project, 'R-active', session=SID)
        self.assertIsNone(self.gate('tool'))
        self.assertEqual((self.state().get('hold') or {}).get('reasons'), ['relay_hold:in_progress'])

    def setUp(self):
        super().setUp()
        self.make_lead()

    def test_below_the_threshold(self):
        self.at(49)
        self.assertIsNone(self.gate())

    def test_safe_lead_is_asked_with_its_tasks_listed(self):
        self.at(52)
        out = self.gate(tasks=[shell('b1', 'Wait for the slice 13 report')])
        self.assertEqual(out['reason'], (
            "relay-gate: context is 52% (threshold 50%). Run /relay now, automatic relay attempt 1 of 2. Open "
            "background tasks: b1 'Wait for the slice 13 report' (shell). The successor re-arms waiters. If one of "
            "them is long work that must finish first, end your turn instead: the gate asks again when a listed "
            "task closes or the next band starts."))
        asked = self.state()['asked']
        self.assertLess(ago(asked.pop('at')), 60)
        self.assertEqual(asked, {'band': 50, 'attempt': 1, 'tasks': ['b1'], 'count': 1})

    def test_a_relay_in_progress_silences_the_gate(self):
        make_relay(self.project, 'R1', SID, files=['launch.json'])
        self.at(55)
        self.assertIsNone(self.gate())

    def test_a_frozen_relay_is_silent_then_alerts_once_after_30_minutes(self):
        rdir = make_relay(self.project, 'R1', SID, files=['launch.json', 'receipt.json', 'handover.md'])
        self.at(55)
        self.assertIsNone(self.gate())
        old = time.time() - 31 * 60
        os.utime(rdir / 'handover.md', (old, old))
        out = self.gate()
        self.assertIn('hand-over of relay R1 is not closed', out['reason'])
        self.assertIn('select:PushNotification', out['reason'])
        self.assertIsNone(self.gate())
        self.assertEqual(len(self.toasts(1)), 1)

    def test_two_failures_give_up_with_one_alert(self):
        make_relay(self.project, 'R1', SID, files=[('failed.json', {'stage': 'receipt'})], age=3 * 3600)
        make_relay(self.project, 'R2', SID, files=[('failed.json', {'stage': 'launch'})], age=3600)
        self.at(55)
        out = self.gate()
        self.assertIn('failed (R1, R2) and will not be retried', out['reason'])
        self.assertIsNone(self.gate())
        self.assertTrue(self.state()['given_up'])
        self.assertEqual(len(self.toasts(1)), 1)

    def test_a_failure_that_will_repeat_gives_up_at_once(self):
        make_relay(self.project, 'R1', SID, files=[('failed.json', {
            'stage': 'check', 'reason': "FAIL identity: successor permission_mode 'default', predecessor "
                                        "'bypassPermissions'"})], age=3600)
        self.at(55)
        self.assertIn('will not be retried', self.gate()['reason'])

    def test_a_handover_stage_failure_is_never_retried(self):
        make_relay(self.project, 'R1', SID, files=['handover.md', ('failed.json', {'stage': 'handover'})],
                   age=3600)
        self.at(55)
        self.assertIsNone(self.gate())

    def test_one_failure_waits_out_the_back_off_then_asks_attempt_2(self):
        rdir = make_relay(self.project, 'R1', SID, files=[('failed.json', {'stage': 'receipt'})], age=60)
        self.at(52)
        self.assertIsNone(self.gate(tasks=[shell('b1')]))
        gate_dir = self.project / 'relay' / 'gate'
        (gate_dir / (SID + '.json')).write_text(json.dumps(dict(load_gate().fresh(), asked={
            'band': 50, 'attempt': 1, 'tasks': ['b1'], 'count': 1, 'at': iso(120)})))
        old = time.time() - 31 * 60
        os.utime(rdir / 'failed.json', (old, old))
        self.assertAsk(self.gate(tasks=[shell('b1')]), attempt=2)

    def test_an_abandoned_relay_counts_as_a_failure(self):
        make_relay(self.project, 'R1', SID, files=['launch.json'], age=26 * 60)
        self.at(52)
        self.assertIsNone(self.gate(env={'RELAY_GATE_BACKOFF_S': '3600'}))
        self.assertAsk(self.gate(env={'RELAY_GATE_BACKOFF_S': '60'}), attempt=2)

    def test_not_safe_below_the_cap_owes_a_drain_nudge(self):
        self.at(52)
        self.assertIsNone(self.gate(tasks=[{'id': 'a1', 'type': 'subagent', 'status': 'running'}]))
        self.assertTrue(self.state()['drain_owed'])

    def test_an_ask_clears_a_drain_owed(self):
        # The lead is asked to run /relay: a drain nudge owed from an earlier unsafe Stop no longer applies.
        self.at(52)
        self.assertIsNone(self.gate(tasks=[{'id': 'a1', 'type': 'subagent', 'status': 'running'}]))
        self.assertTrue(self.state()['drain_owed'])
        self.assertAsk(self.gate())
        self.assertFalse(self.state()['drain_owed'])

    def test_not_safe_at_the_cap_alerts_once_per_band(self):
        running = [{'id': 'a1', 'type': 'subagent', 'status': 'running', 'description': 'review'}]
        self.at(61)
        out = self.gate(tasks=running)
        self.assertIn('cannot relay yet: subagent a1 is running (review)', out['reason'])
        self.assertIn('keep draining', out['reason'])
        self.assertNotIn('Run /relay now', out['reason'])
        self.assertIsNone(self.gate(tasks=running))
        self.at(71)
        self.assertIn('is at 71%', self.gate(tasks=running)['reason'])
        self.assertEqual(len(self.toasts(2)), 2)

    def test_an_alert_toast_that_fails_changes_nothing(self):
        self.herd({'notification show': [{'out': 'boom', 'code': 1, 'sleep': 3}]})
        self.make_lead()
        self.at(61)
        started = time.time()
        out = self.gate(tasks=[{'id': 'a1', 'type': 'subagent', 'status': 'running', 'description': 'review'}])
        self.assertLess(time.time() - started, 2.5)
        self.assertIn('cannot relay yet', out['reason'])

    def test_a_missing_task_list_an_unknown_type_and_a_teammate_are_not_safe(self):
        self.at(52)
        self.assertIsNone(self.gate(background_tasks=None))
        self.assertIsNone(self.gate(tasks=[{'id': 'w1', 'type': 'workflow', 'status': 'running'}]))
        self.assertIsNone(self.gate(tasks=[{'id': 't1', 'type': 'teammate', 'status': 'running'}]))
        self.assertIsNone(self.state()['asked'])
        self.at(61)
        self.assertIn('workflow w1 is running', self.gate(tasks=[{'id': 'w1', 'type': 'workflow',
                                                                   'status': 'running'}])['reason'])

    def teammate_unsafe(self, tasks):
        path = write_transcript(self.projects, SID, self.recs)
        call = SimpleNamespace(inp={'cwd': str(self.repo)}, project=str(self.project), transcript=str(path))
        return load_gate().unsafe(call, tasks)

    def test_ended_transcript_teammates_allow_the_gate_to_ask(self):
        self.make_lead()
        self.at(52, *teammate_spawn('mate1'), *teammate_spawn('mate2'), agents_killed())
        self.assertEqual(self.teammate_unsafe([]), [])
        self.assertAsk(self.gate())

    def test_a_running_transcript_teammate_still_holds_the_gate(self):
        self.make_lead()
        self.at(52, *teammate_spawn())
        self.assertEqual(self.teammate_unsafe([]),
                         ['teammate mate1 is running inside this session (review)'])
        self.assertIsNone(self.gate())
        self.assertEqual(self.state()['hold']['reasons'], self.teammate_unsafe([]))

    def test_a_live_running_teammate_holds_after_transcript_teammates_ended(self):
        self.make_lead()
        self.at(52, *teammate_spawn(), agents_killed())
        running = [{'id': 'mate1', 'type': 'teammate', 'status': 'running', 'description': 'review'}]
        self.assertEqual(self.teammate_unsafe(running), ['teammate mate1 is running (review)'])
        self.assertIsNone(self.gate(tasks=running))
        self.assertEqual(self.state()['hold']['reasons'], self.teammate_unsafe(running))
        self.assertEqual(self.teammate_unsafe([dict(running[0], status='killed')]), [])
        self.assertAsk(self.gate(tasks=[dict(running[0], status='killed')]))

    def test_a_task_entry_that_is_not_an_object_is_not_safe(self):
        # An entry the gate cannot read is unknown, and unknown counts as not safe: it may be a running subagent.
        self.at(52)
        self.assertIsNone(self.gate(tasks=['a1-subagent-id']))
        self.assertTrue(self.state()['drain_owed'])
        self.assertIsNone(self.state()['asked'])
        self.at(61)
        self.assertIn("cannot relay yet: background task entry 'a1-subagent-id' is not a JSON object",
                      self.gate(tasks=[shell('b1'), 'a1-subagent-id'])['reason'])

    def test_a_finished_subagent_does_not_block(self):
        self.at(52)
        self.assertAsk(self.gate(tasks=[{'id': 'a1', 'type': 'subagent', 'status': 'completed'}]))

    def test_a_workflow_open_in_the_transcript_is_not_safe(self):
        self.at(52, tool_use('w', 'Workflow', {'script': 'export const meta = {}'}, 2),
                tool_result('w', 'Workflow launched in background. Task ID: wf0001', 2,
                            tool_use_result={'status': 'async_launched', 'taskId': 'wf0001'}))
        self.assertIsNone(self.gate())
        self.at(61, *self.recs[:-1])
        self.assertIn('workflow wf0001 is running inside this session', self.gate()['reason'])

    def test_git_mid_merge_is_not_safe(self):
        (self.repo / '.git' / 'MERGE_HEAD').write_text('0' * 40 + '\n')
        self.at(52)
        self.assertIsNone(self.gate())

    def test_a_hung_git_cannot_hold_the_stop_past_its_budget(self):
        # Past its 2 s bound git cannot tell, like a git that fails: no git blocker, and the call stays well
        # inside the 7 s budget and the 10 s hook timeout.
        self.at(52)
        started = time.time()
        out = self.gate(env={'PATH': '%s:%s' % (slow_git(self.tmp.name), self.env['PATH'])})
        self.assertLess(time.time() - started, 5)
        self.assertAsk(out)

    def test_a_recent_owner_prompt_defers_below_the_cap_only(self):
        typed = dict(prompt('how is it going?'), timestamp=iso(300))
        self.at(52, typed)
        self.assertIsNone(self.gate())
        self.assertAsk(self.gate(env={'RELAY_GATE_OWNER_S': '60'}))   # the test-only window (live e2e)
        (self.project / 'relay' / 'gate' / (SID + '.json')).unlink()
        self.at(61, typed)
        self.assertAsk(self.gate())

    def test_empty_queued_entries_do_not_defer_the_owner_check(self):
        self.make_lead()
        for content in ('', ' \t', None):
            with self.subTest(content=content):
                self.at(52, {'type': 'queue-operation', 'operation': 'enqueue',
                             'timestamp': iso(1), 'content': content})
                self.assertAsk(self.gate())
                (self.project / 'relay' / 'gate' / (SID + '.json')).unlink()

    def test_cron_fires_do_not_defer_the_owner_check(self):
        for head in (None, 200):
            with self.subTest(head=head):
                recs = cron_fire('cron1', 'check the work and report progress; ' * 17,
                                 head=head, origin_null=head is not None)
                for rec in recs:
                    rec['timestamp'] = iso(1)
                self.at(52, *recs)
                self.assertAsk(self.gate())
                self.assertIsNone(self.state()['hold'])
                (self.project / 'relay' / 'gate' / (SID + '.json')).unlink()

    def test_a_prompt_without_a_readable_time_does_not_defer(self):
        self.at(52, dict(prompt('hi'), timestamp='yesterday'))
        self.assertAsk(self.gate())

    def test_an_owner_prompt_older_than_10_minutes_does_not_defer(self):
        self.at(52, dict(prompt('earlier'), timestamp=iso(900)))
        self.assertAsk(self.gate())

    def test_the_same_band_attempt_and_tasks_are_asked_once(self):
        self.at(52)
        self.assertAsk(self.gate(tasks=[shell('b1')]))
        self.assertIsNone(self.gate(tasks=[shell('b1')]))

    def test_an_added_task_does_not_ask_again(self):
        self.at(52)
        self.assertAsk(self.gate(tasks=[shell('b1')]))
        self.assertIsNone(self.gate(tasks=[shell('b1'), shell('b2')]))

    def test_a_listed_task_closing_asks_again(self):
        self.at(52)
        self.assertAsk(self.gate(tasks=[shell('b1'), shell('b2')]))
        self.assertAsk(self.gate(tasks=[shell('b2')]))
        self.assertEqual(self.state()['asked']['count'], 2)

    def test_a_band_rise_asks_again_with_the_owner_alert(self):
        self.at(52)
        self.assertAsk(self.gate(tasks=[shell('b1')]))
        self.at(61)
        out = self.gate(tasks=[shell('b1')])
        self.assertAsk(out)
        self.assertIn('select:PushNotification', out['reason'])
        self.assertEqual(len(self.toasts(1)), 1)

    def test_a_band_fall_never_asks_again(self):
        # Turn-end readings can fall a band with no compaction (real transcripts: 66.4% to 59.4%): only a rise asks.
        self.at(61)
        self.assertAsk(self.gate(tasks=[shell('b1')]))
        self.at(59)
        self.assertIsNone(self.gate(tasks=[shell('b1')]))
        self.at(61)
        self.assertIsNone(self.gate(tasks=[shell('b1')]))
        self.assertEqual(self.state()['asked']['count'], 1)

    def test_an_ask_after_a_fall_keeps_the_band_asked(self):
        self.at(61)
        self.assertAsk(self.gate(tasks=[shell('b1'), shell('b2')]))
        self.at(59)
        self.assertAsk(self.gate(tasks=[shell('b2')]))    # a listed task closed
        self.assertEqual((self.state()['asked']['band'], self.state()['asked']['count']), (60, 2))
        self.at(61)
        self.assertIsNone(self.gate(tasks=[shell('b2')]))    # back in band 60 is not a rise

    def test_a_fall_of_more_than_a_step_still_asks_again(self):
        self.at(71)
        self.assertAsk(self.gate(tasks=[shell('b1')]))
        self.at(55)    # more than a step below band 70: the bands are forgotten
        self.assertAsk(self.gate(tasks=[shell('b1')]))

    def test_a_fourth_ask_in_a_band_is_silent(self):
        self.at(52)
        gate_dir = self.project / 'relay' / 'gate'
        gate_dir.mkdir(parents=True)
        (gate_dir / (SID + '.json')).write_text(json.dumps(dict(load_gate().fresh(), asked={
            'band': 50, 'attempt': 1, 'tasks': ['b1'], 'count': 3, 'at': iso(120)})))
        self.assertIsNone(self.gate(tasks=[]))

    def test_a_drop_of_more_than_a_step_forgets_the_bands(self):
        self.at(52)
        self.assertAsk(self.gate(tasks=[shell('b1')]))
        self.assertIsNone(self.gate(tasks=[shell('b1')]))
        self.at(15)
        self.assertIsNone(self.gate(tasks=[shell('b1')]))
        self.assertIsNone(self.state()['asked'])
        self.at(52)
        self.assertAsk(self.gate(tasks=[shell('b1')]))

    def test_a_relay_never_loops_after_a_failure(self):
        """T13: 40 Stops with notification turns, new prompt ids and churning waiters around two failures."""
        blocks = []

        def stop(n, tag):
            out = self.gate(tasks=[shell('w%d' % n)])
            if out:
                blocks.append((tag, n, out['reason']))

        first = make_relay(self.project, 'R1', SID, files=[('failed.json', {'stage': 'receipt'})])
        self.at(52)
        for n in range(20):
            stop(n, 'back-off')
        old = time.time() - 31 * 60
        os.utime(first / 'failed.json', (old, old))
        stop(20, 'retry')
        second = make_relay(self.project, 'R2', SID, files=['launch.json'])
        for n in range(21, 26):
            stop(n, 'relaying')
        (second / 'failed.json').write_text(json.dumps({'stage': 'receipt'}))
        for n in range(26, 40):
            stop(n, 'after')
        self.assertEqual([(tag, n) for tag, n, _ in blocks], [('retry', 20), ('after', 26)], blocks)
        self.assertIn('attempt 2 of 2', blocks[0][2])
        self.assertIn('will not be retried', blocks[1][2])


class ToolTests(GateCase):
    def setUp(self):
        super().setUp()
        self.make_lead()
        self.extra_env = {'RELAY_GATE_THROTTLE_S': '0.001'}

    def assertNudge(self, out, pct):
        self.assertEqual(out['hookSpecificOutput']['hookEventName'], 'PostToolUse')
        self.assertTrue(out['hookSpecificOutput']['additionalContext'].startswith(
            'relay-gate: context is %d%%. A relay is due.' % pct))

    def delivered(self, tid):
        """The transcript's record that the nudge printed after tool call tid reached the model, carrying the text
        the gate actually printed."""
        return hook_context(tid, [self.printed[tid]['hookSpecificOutput']['additionalContext']])

    def rewrite_pending(self, **fields):
        state = self.state()
        state['pending'].update(fields)
        (self.project / 'relay' / 'gate' / (SID + '.json')).write_text(json.dumps(state))

    def test_once_per_band(self):
        self.at(52)
        self.assertNudge(self.gate('tool', tool_use_id='toolu_A'), 52)
        self.at(52, self.delivered('toolu_A'))
        self.assertIsNone(self.gate('tool'))
        self.assertIsNone(self.gate('tool'))
        self.at(61, self.delivered('toolu_A'))
        self.assertNudge(self.gate('tool', tool_use_id='toolu_B'), 61)
        self.at(61, self.delivered('toolu_A'), self.delivered('toolu_B'))
        self.assertIsNone(self.gate('tool'))
        self.assertEqual(self.state()['nudged'], [50, 60])

    def test_a_drain_owed_by_stop_is_delivered_past_the_throttle(self):
        self.at(52)
        self.assertNudge(self.gate('tool', tool_use_id='toolu_A'), 52)
        self.at(52, self.delivered('toolu_A'))
        self.assertIsNone(self.gate('tool'))    # confirms the nudge
        self.assertIsNone(self.gate(tasks=[{'id': 'a1', 'type': 'subagent', 'status': 'running'}]))
        self.assertFalse(self.state()['drain_owed'])   # band 50 was already nudged: nothing owed
        state_path = self.project / 'relay' / 'gate' / (SID + '.json')
        state_path.write_text(json.dumps(dict(self.state(), drain_owed=True, nudged=[],
                                              meter={'pct': 52.0, 'read_at': iso(0)})))
        self.assertNudge(self.gate('tool', tool_use_id='toolu_B', env={'RELAY_GATE_THROTTLE_S': '3600'}), 52)
        self.assertTrue(self.state()['pending']['drain'])
        self.at(52, self.delivered('toolu_A'), self.delivered('toolu_B'))
        self.assertIsNone(self.gate('tool', env={'RELAY_GATE_THROTTLE_S': '3600'}))    # still owed: not throttled
        self.assertFalse(self.state()['drain_owed'])

    def test_a_printed_nudge_is_pending_and_not_yet_nudged(self):
        self.at(52)
        self.assertNudge(self.gate('tool', tool_use_id='toolu_A'), 52)
        state = self.state()
        pending = state['pending']
        self.assertLess(ago(pending.pop('at')), 60)
        self.assertEqual(pending, {'band': 50, 'tool_use_id': 'toolu_A', 'drain': False})
        self.assertEqual(state['nudged'], [])

    def test_a_delivered_nudge_counts_its_band(self):
        # The call that confirms it then decides as if nothing were pending: silent in the same band, and a print
        # in a new band in that same call.
        self.at(52)
        self.assertNudge(self.gate('tool', tool_use_id='toolu_A'), 52)
        self.at(53, self.delivered('toolu_A'))
        self.assertIsNone(self.gate('tool', tool_use_id='toolu_B'))
        state = self.state()
        self.assertEqual((state['nudged'], state['pending']), ([50], None))
        (self.project / 'relay' / 'gate' / (SID + '.json')).unlink()
        self.at(52)
        self.assertNudge(self.gate('tool', tool_use_id='toolu_C'), 52)
        self.at(61, self.delivered('toolu_C'))
        self.assertNudge(self.gate('tool', tool_use_id='toolu_D'), 61)
        state = self.state()
        self.assertEqual((state['nudged'], state['pending']['band'], state['pending']['tool_use_id']),
                         ([50], 60, 'toolu_D'))

    def test_a_cancelled_nudge_is_printed_again(self):
        # Claude Code killed the hook past its timeout and dropped the output (e2e defect D2): the band is not
        # counted, and the next call prints it.
        self.at(52)
        self.assertNudge(self.gate('tool', tool_use_id='toolu_A'), 52)
        self.at(53, hook_cancelled('toolu_A'))
        self.assertNudge(self.gate('tool', tool_use_id='toolu_B'), 53)
        state = self.state()
        self.assertEqual(state['nudged'], [])
        self.assertEqual((state['pending']['band'], state['pending']['tool_use_id']), (50, 'toolu_B'))

    def test_an_unconfirmed_nudge_holds_every_band_for_2_minutes(self):
        self.at(52)
        self.assertNudge(self.gate('tool', tool_use_id='toolu_A'), 52)
        before = self.state()['pending']
        self.assertIsNone(self.gate('tool'))
        self.at(61)    # a higher band
        self.assertIsNone(self.gate('tool'))
        self.assertEqual(self.state()['pending'], before)
        self.rewrite_pending(at=iso(110))
        held = self.state()['pending']
        self.assertIsNone(self.gate('tool'))
        self.assertEqual(self.state()['pending'], held)
        self.assertEqual(self.state()['nudged'], [])

    def assertCountedUnconfirmed(self, at):
        """A nudge whose transcript shows neither outcome, with pending['at'] rewritten to at, counts as delivered:
        its band goes into nudged and is not printed again."""
        self.at(52)
        self.assertNudge(self.gate('tool', tool_use_id='toolu_A'), 52)
        self.rewrite_pending(at=at)
        self.assertIsNone(self.gate('tool', tool_use_id='toolu_B'))
        state = self.state()
        self.assertEqual((state['nudged'], state['pending']), ([50], None))
        self.assertIsNone(self.gate('tool'))

    def test_an_unconfirmed_nudge_2_minutes_old_counts_as_delivered(self):
        # Neither record after 2 minutes: the transcript cannot tell (Claude Code renamed the records, say). Counting
        # the band degrades to one print per band, never to a reprint every 2 minutes; a lost nudge is caught by its
        # hook_cancelled, not by this expiry.
        self.assertCountedUnconfirmed(iso(120))

    def test_an_unconfirmed_nudge_with_an_unreadable_time_counts_as_delivered(self):
        self.assertCountedUnconfirmed('not a time')

    def test_an_unconfirmed_nudge_stamped_in_the_future_counts_as_delivered(self):
        # A clock stepped back (or a hand-edited state) must not hold the band until the clock catches up.
        self.assertCountedUnconfirmed(iso(-3600))

    def test_an_unconfirmed_drain_nudge_2_minutes_old_pays_drain_owed(self):
        self.at(52)
        state_path = self.project / 'relay' / 'gate' / (SID + '.json')
        state_path.parent.mkdir(parents=True)
        state_path.write_text(json.dumps(dict(load_gate().fresh(), nudged=[50], drain_owed=True)))
        self.assertNudge(self.gate('tool', tool_use_id='toolu_A'), 52)
        self.rewrite_pending(at=iso(120))
        self.assertIsNone(self.gate('tool', tool_use_id='toolu_B'))
        state = self.state()
        self.assertEqual((state['nudged'], state['drain_owed'], state['pending']), ([50], False, None))

    def test_a_pending_nudge_is_aged_when_the_state_is_read_not_when_the_call_started(self):
        # A parallel call can save its nudge after this call began (call.now). Aged against call.now, that nudge
        # would read as stamped in the future and count as delivered before its outcome can exist (review N1).
        gate = load_gate()
        self.at(52)
        path = write_transcript(self.projects, SID, self.recs)
        call = gate.Call({'session_id': SID, 'transcript_path': str(path), 'cwd': str(self.repo)}, gate.Config({}),
                         gate.Clock(3), time.time() - 10)
        pending = {'band': 50, 'tool_use_id': 'toolu_A', 'drain': True, 'at': iso(5)}   # after call.now, before now
        state = dict(gate.fresh(), drain_owed=True, pending=dict(pending))
        self.assertIsNone(gate.nudge(call, state, 52.0, 50))
        self.assertEqual((state['pending'], state['nudged'], state['drain_owed']), (pending, [], True))

    def test_a_cancelled_nudge_is_printed_again_however_old(self):
        # The transcript is read before the age: a lost nudge is printed again even past the 2 minutes.
        self.at(52)
        self.assertNudge(self.gate('tool', tool_use_id='toolu_A'), 52)
        self.rewrite_pending(at=iso(600))
        self.at(52, hook_cancelled('toolu_A'))
        self.assertNudge(self.gate('tool', tool_use_id='toolu_B'), 52)
        state = self.state()
        self.assertEqual((state['nudged'], state['pending']['tool_use_id']), ([], 'toolu_B'))

    def test_a_drain_nudge_pays_drain_owed_only_once_delivered(self):
        self.at(52)
        self.assertIsNone(self.gate(tasks=[{'id': 'a1', 'type': 'subagent', 'status': 'running'}]))
        self.assertTrue(self.state()['drain_owed'])
        self.assertNudge(self.gate('tool', tool_use_id='toolu_A'), 52)
        self.assertTrue(self.state()['pending']['drain'])
        self.assertTrue(self.state()['drain_owed'])    # owed while the drain nudge is pending
        self.assertIsNone(self.gate('tool'))
        self.assertTrue(self.state()['drain_owed'])
        self.at(52, self.delivered('toolu_A'))
        self.assertIsNone(self.gate('tool'))
        state = self.state()
        self.assertEqual((state['drain_owed'], state['nudged'], state['pending']), (False, [50], None))

    def test_an_unsafe_stop_owes_no_drain_for_the_pending_band_and_a_delivered_nudge_prints_nothing(self):
        # The lead obeys the nudge and ends its turn before the next tool call confirms it: the band is pending,
        # not yet in nudged, and counts as nudged for Stop, so it is not printed twice.
        self.at(52)
        self.assertNudge(self.gate('tool', tool_use_id='toolu_A'), 52)
        self.assertIsNone(self.gate(tasks=[{'id': 'a1', 'type': 'subagent', 'status': 'running'}]))
        self.assertFalse(self.state()['drain_owed'])
        self.at(52, self.delivered('toolu_A'))
        self.assertIsNone(self.gate('tool', tool_use_id='toolu_B'))
        state = self.state()
        self.assertEqual((state['nudged'], state['drain_owed'], state['pending']), ([50], False, None))

    def test_an_unsafe_stop_owes_no_drain_for_the_pending_band_and_a_cancelled_nudge_prints_again(self):
        self.at(52)
        self.assertNudge(self.gate('tool', tool_use_id='toolu_A'), 52)
        self.assertIsNone(self.gate(tasks=[{'id': 'a1', 'type': 'subagent', 'status': 'running'}]))
        self.assertFalse(self.state()['drain_owed'])
        self.at(52, hook_cancelled('toolu_A'))
        self.assertNudge(self.gate('tool', tool_use_id='toolu_B'), 52)
        state = self.state()
        self.assertEqual((state['nudged'], state['pending']['band'], state['pending']['tool_use_id']),
                         ([], 50, 'toolu_B'))

    def test_a_delivered_nudge_pays_only_its_own_drain(self):
        # Band 50's nudge is pending when an unsafe Stop at 61% (below a cap of 70) owes a drain for band 60. The
        # fill falls back to band 50: confirming the band-50 nudge, which was no drain nudge, leaves that drain owed.
        self.at(52)
        self.assertNudge(self.gate('tool', tool_use_id='toolu_A'), 52)
        self.at(61)
        self.assertIsNone(self.gate(tasks=[{'id': 'a1', 'type': 'subagent', 'status': 'running'}],
                                    env={'RELAY_GATE_CAP': '70'}))
        self.assertTrue(self.state()['drain_owed'])
        self.at(55, self.delivered('toolu_A'))
        self.assertNudge(self.gate('tool', tool_use_id='toolu_B'), 55)
        state = self.state()
        self.assertEqual((state['nudged'], state['drain_owed'], state['pending']['drain']), ([50], True, True))

    def test_a_cancelled_drain_nudge_stays_owed_and_is_printed_again(self):
        # Band 50 is already nudged: only drain_owed prints this nudge, so a lost one must keep it owed.
        self.at(52)
        state_path = self.project / 'relay' / 'gate' / (SID + '.json')
        state_path.parent.mkdir(parents=True)
        state_path.write_text(json.dumps(dict(load_gate().fresh(), nudged=[50], drain_owed=True)))
        self.assertNudge(self.gate('tool', tool_use_id='toolu_A'), 52)
        self.assertEqual((self.state()['drain_owed'], self.state()['pending']['drain']), (True, True))
        self.at(52, hook_cancelled('toolu_A'))
        self.assertNudge(self.gate('tool', tool_use_id='toolu_B'), 52)
        state = self.state()
        self.assertEqual((state['drain_owed'], state['pending']['tool_use_id'], state['pending']['drain']),
                         (True, 'toolu_B', True))

    def test_another_hooks_context_for_the_call_does_not_confirm_the_nudge(self):
        self.at(52)
        self.assertNudge(self.gate('tool', tool_use_id='toolu_A'), 52)
        self.at(52, hook_context('toolu_A', ['lint: 3 warnings']), hook_cancelled('toolu_A'))
        self.assertNudge(self.gate('tool', tool_use_id='toolu_B'), 52)
        state = self.state()
        self.assertEqual((state['nudged'], state['pending']['tool_use_id']), ([], 'toolu_B'))

    def test_an_input_without_a_tool_use_id_counts_the_nudge_at_once(self):
        self.at(52)
        self.assertIsNone(self.gate(tasks=[{'id': 'a1', 'type': 'subagent', 'status': 'running'}]))
        self.assertTrue(self.state()['drain_owed'])
        self.assertNudge(self.gate('tool', tool_use_id=None), 52)
        state = self.state()
        self.assertEqual((state['nudged'], state['drain_owed'], state['pending']), ([50], False, None))
        self.assertIsNone(self.gate('tool', tool_use_id=None))

    def backdate_ask(self, seconds):
        state = self.state()
        state['asked']['at'] = iso(seconds)
        (self.project / 'relay' / 'gate' / (SID + '.json')).write_text(json.dumps(state))

    def test_no_nudge_while_the_lead_runs_the_relay_stop_asked_for(self):
        # Until checklist writes the relay dir, the lead's /relay shows nowhere but in the ask: a nudge then would
        # tell it to end its turn mid-relay (live run: nudges at 54/61/70% within seconds of the ask).
        self.at(52)
        self.assertAsk(self.gate())
        self.assertIsNone(self.gate('tool'))
        self.at(61)    # a band crossed while /relay saves
        self.assertIsNone(self.gate('tool'))
        self.assertEqual(self.state()['nudged'], [])

    def test_an_ask_holds_the_nudge_for_15_minutes(self):
        self.at(52)
        self.assertAsk(self.gate())
        self.backdate_ask(14 * 60)
        self.assertIsNone(self.gate('tool'))
        self.backdate_ask(16 * 60)
        self.assertNudge(self.gate('tool'), 52)

    def test_an_ask_holds_the_nudge_for_its_own_attempt_only(self):
        self.at(52)
        self.assertAsk(self.gate())
        make_relay(self.project, 'R1', SID, files=[('failed.json', {'stage': 'receipt'})], age=31 * 60)
        self.at(61)    # attempt 2 is due (the back-off is over) and Stop has not asked it yet
        self.assertNudge(self.gate('tool'), 61)

    def test_the_throttle_skips_the_meter(self):
        self.at(52)
        state_path = self.project / 'relay' / 'gate' / (SID + '.json')
        state_path.parent.mkdir(parents=True)
        state_path.write_text(json.dumps(dict(load_gate().fresh(), meter={'pct': 40.0, 'read_at': iso(10)})))
        self.assertIsNone(self.gate('tool', env={'RELAY_GATE_THROTTLE_S': '60'}))
        state_path.write_text(json.dumps(dict(load_gate().fresh(), meter={'pct': 40.0, 'read_at': iso(120)})))
        self.assertNudge(self.gate('tool', env={'RELAY_GATE_THROTTLE_S': '60'}), 52)

    def test_silent_while_relaying_frozen_backing_off_or_given_up(self):
        self.at(52)
        cases = {'in progress': [('R1', ['launch.json'], 0)],
                 'frozen': [('R1', ['handover.md'], 0)],
                 'back-off': [('R1', [('failed.json', {'stage': 'receipt'})], 60)],
                 'given up': [('R1', [('failed.json', {'stage': 'receipt'})], 7200),
                              ('R2', [('failed.json', {'stage': 'launch'})], 3600)]}
        for label, relays in cases.items():
            with self.subTest(label):
                relay_dir = self.project / 'relay'
                for child in list(relay_dir.iterdir()):
                    if child.is_dir():
                        for path in sorted(child.rglob('*'), reverse=True):
                            path.rmdir() if path.is_dir() else path.unlink()
                        child.rmdir()
                for rid, files, age in relays:
                    make_relay(self.project, rid, SID, files=files, age=age)
                self.assertIsNone(self.gate('tool'))

    def test_parallel_tool_calls_leave_a_valid_state(self):
        self.at(52)
        path = write_transcript(self.projects, SID, self.recs)
        ids = ['toolu_P%d' % n for n in range(6)]
        env = dict(self.env, RELAY_GATE_THROTTLE_S='0.001')
        procs = [subprocess.Popen(['python3', '-I', str(GATE), 'tool'], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True, env=env) for _ in ids]
        outs = [p.communicate(json.dumps({'session_id': SID, 'transcript_path': str(path), 'cwd': str(self.repo),
                                          'tool_name': 'Bash', 'tool_use_id': tid}), timeout=30)
                for p, tid in zip(procs, ids)]
        self.assertEqual([p.returncode for p in procs], [0] * 6, [e for _, e in outs])
        self.assertGreaterEqual(sum(1 for out, _ in outs if out.strip()), 1)
        state = self.state()
        self.assertEqual((state['nudged'], state['pending']['band']), ([], 50))
        self.assertIn(state['pending']['tool_use_id'], ids)

    def test_a_subagent_tool_call_is_ignored(self):
        self.at(52)
        self.assertIsNone(self.gate('tool', agent_id='a962fa2df48cd277c'))

    def test_a_non_lead_writes_nothing(self):
        (self.project / 'relay' / 'lead.json').unlink()
        self.at(52)
        self.assertIsNone(self.gate('tool'))
        self.assertIsNone(self.state())

    def test_a_former_lead_with_a_state_file_is_not_nudged(self):
        self.at(52)
        self.assertNudge(self.gate('tool', tool_use_id='toolu_A'), 52)
        self.at(52, self.delivered('toolu_A'))
        self.assertIsNone(self.gate('tool'))    # confirms the nudge
        (self.project / 'relay' / 'lead.json').write_text(json.dumps({'session_id': 'another', 'name': 'lead-repo'}))
        before = self.state()
        self.at(62, self.delivered('toolu_A'))    # a new band; the pane's herdr name is worker-high
        self.assertIsNone(self.gate('tool'))
        self.assertEqual(self.state(), before)


if __name__ == '__main__':
    unittest.main()

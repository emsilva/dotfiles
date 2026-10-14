import datetime
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
import unittest

from handoff_fixtures import (NOT_FOUND, SCRIPTS, agent_json, herdr_calls, herdr_stub, prompt, ts,
                              write_transcript)

CLOSE = SCRIPTS / 'relay-close.sh'
PRED = '44444444-4444-4444-8444-444444444444'


def dead_pid():
    proc = subprocess.Popen(['true'])
    proc.wait()
    return proc.pid


def fake_claude():
    """A live process whose argv[0] is `claude`, as `ps -o command=` shows a real Claude Code session."""
    return subprocess.Popen(['claude', '60'], executable='/bin/sleep')


class CloseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.dir = self.root / 'relay' / 'R1'
        self.dir.mkdir(parents=True)
        self.sleeper = None

    def tearDown(self):
        if self.sleeper:
            self.sleeper.kill()
            self.sleeper.wait()
        self.tmp.cleanup()

    def prepare(self, responses, prompts=(10,), handover_at=30, pid=None, herdr_session='S0', wait='1'):
        path = write_transcript(self.root / 'projects', PRED, [prompt('p%d' % s, s) for s in prompts])
        (self.dir / 'checklist.json').write_text(json.dumps({
            'relay_id': 'R1', 'repo': '/x/repo',
            'predecessor': {'pane_id': 'wT:p0', 'herdr_session': herdr_session, 'session_id': PRED,
                            'pid': pid if pid is not None else dead_pid(), 'transcript': str(path)}}))
        if handover_at is not None:
            (self.dir / 'handover.md').write_text('# Hand-over R1\n')
            when = datetime.datetime.fromisoformat(ts(handover_at).replace('Z', '+00:00')).timestamp()
            os.utime(self.dir / 'handover.md', (when, when))
        env, self.log = herdr_stub(self.tmp.name, responses)
        env.update(CLAUDE_CODE_SESSION_ID='N1', RELAY_CLOSE_WAIT=wait)
        return env

    def close(self, responses, prompts=(10,), handover_at=30, pid=None, herdr_session='S0', args=(), env=None):
        env = env or self.prepare(responses, prompts, handover_at, pid, herdr_session)
        return subprocess.run(['bash', str(CLOSE), str(self.dir), *args], capture_output=True, text=True, env=env)

    def close_ending_the_predecessor(self, responses, herdr_session=None):
        """Run the close and end the fake claude (self.sleeper) once herdr is asked to close its pane.

        Real herdr ends the pane's process when it closes the pane. The fake herdr cannot, so the test does it
        while the fake's `pane close` is in flight (that response sleeps). The process is reaped as well as
        killed: `kill -0` still succeeds on a zombie."""
        env = self.prepare(responses, pid=self.sleeper.pid, herdr_session=herdr_session, wait='5')
        proc = subprocess.Popen(['bash', str(CLOSE), str(self.dir)], stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, text=True, env=env)
        try:
            deadline = time.monotonic() + 10
            while not self.closes() and proc.poll() is None and time.monotonic() < deadline:
                time.sleep(0.02)
            self.sleeper.kill()
            self.sleeper.wait()
            out, err = proc.communicate(timeout=30)
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait()
        return subprocess.CompletedProcess(proc.args, proc.returncode, out, err)

    def closes(self):
        return [c for c in herdr_calls(self.log) if c[:2] == ['pane', 'close']]

    def test_closes_renames_and_records(self):
        r = self.close({'agent get': [{'out': agent_json('idle', session='S0')}, NOT_FOUND]})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.closes(), [['pane', 'close', 'wT:p0']])
        self.assertIn(['agent', 'rename', 'wT:p1', 'lead-repo'], herdr_calls(self.log))
        closed = json.loads((self.dir / 'closed.json').read_text())
        self.assertEqual(closed['successor'], {'pane_id': 'wT:p1', 'session_id': 'N1', 'name': 'lead-repo'})
        lead = json.loads((self.dir.parent / 'lead.json').read_text())
        self.assertEqual((lead['session_id'], lead['name'], lead['relay_id']), ('N1', 'lead-repo', 'R1'))

    def test_refuses_while_the_predecessor_works(self):
        r = self.close({'agent get': [{'out': agent_json('working', session='S0')}]})
        self.assertEqual(r.returncode, 1)
        self.assertIn("is 'working', not idle or done", r.stderr)
        self.assertEqual(self.closes(), [])

    def test_refuses_when_the_pane_hosts_another_session(self):
        r = self.close({'agent get': [{'out': agent_json('idle', session='OTHER')}]})
        self.assertEqual(r.returncode, 1)
        self.assertIn("hosts session 'OTHER'", r.stderr)
        self.assertEqual(self.closes(), [])

    def test_refuses_after_a_prompt_reached_the_old_pane(self):
        r = self.close({'agent get': [{'out': agent_json('idle', session='S0')}]}, prompts=(10, 40))
        self.assertEqual(r.returncode, 1)
        self.assertIn('a prompt reached the predecessor after the hand-over', r.stderr)
        self.assertEqual(self.closes(), [])

    def test_refuses_without_a_handover(self):
        r = self.close({'agent get': [{'out': agent_json('idle', session='S0')}]}, handover_at=None)
        self.assertEqual(r.returncode, 1)
        self.assertIn('no handover.md', r.stderr)
        self.assertEqual(self.closes(), [])

    def test_reports_a_predecessor_pid_that_survives_the_close(self):
        self.sleeper = subprocess.Popen(['sleep', '60'])
        r = self.close({'agent get': [{'out': agent_json('idle', session='S0')}, NOT_FOUND]}, pid=self.sleeper.pid)
        self.assertEqual(r.returncode, 1)
        self.assertIn('is still alive', r.stderr)
        self.assertFalse((self.dir / 'closed.json').exists())

    # A lead started by hand has no agent_session in herdr: the checklist's herdr_session is null, and
    # two blanks compare equal. The recorded pid must then be a live claude process before the close.

    def test_without_a_herdr_session_closes_a_live_claude_predecessor(self):
        self.sleeper = fake_claude()
        r = self.close_ending_the_predecessor({'agent get': [{'out': agent_json('idle')}, NOT_FOUND],
                                               'pane close': [{'out': '{"result": {}}', 'sleep': 0.5}]})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.closes(), [['pane', 'close', 'wT:p0']])
        closed = json.loads((self.dir / 'closed.json').read_text())
        self.assertEqual(closed['predecessor'], {'pane_id': 'wT:p0', 'session_id': PRED})

    def test_without_a_herdr_session_refuses_a_dead_pid(self):
        pid = dead_pid()
        r = self.close({'agent get': [{'out': agent_json('idle')}]}, pid=pid, herdr_session=None)
        self.assertEqual(r.returncode, 1)
        self.assertIn('records no herdr session', r.stderr)
        self.assertIn('predecessor pid %d is not alive' % pid, r.stderr)
        self.assertEqual(self.closes(), [])

    def test_without_a_herdr_session_refuses_a_live_process_that_is_not_claude(self):
        self.sleeper = subprocess.Popen(['sleep', '60'])
        r = self.close({'agent get': [{'out': agent_json('idle')}]}, pid=self.sleeper.pid, herdr_session=None)
        self.assertEqual(r.returncode, 1)
        self.assertIn("predecessor pid %d runs 'sleep', not claude" % self.sleeper.pid, r.stderr)
        self.assertEqual(self.closes(), [])

    def test_without_a_herdr_session_refuses_a_pane_that_now_hosts_one(self):
        self.sleeper = fake_claude()
        r = self.close({'agent get': [{'out': agent_json('idle', session='S9')}]}, pid=self.sleeper.pid,
                       herdr_session=None)
        self.assertEqual(r.returncode, 1)
        self.assertIn("hosts session 'S9', not 'none'", r.stderr)
        self.assertEqual(self.closes(), [])

    def test_refuses_when_herdr_cannot_read_the_pane(self):
        r = self.close({'agent get': [{'out': '{"error": {"code": "server_unavailable"}}', 'code': 1}]})
        self.assertEqual(r.returncode, 1)
        self.assertIn('could not read predecessor pane wT:p0', r.stderr)
        self.assertIn('server_unavailable', r.stderr)
        self.assertEqual(self.closes(), [])

    def test_reports_a_pane_that_still_answers_after_the_close(self):
        r = self.close({'agent get': [{'out': agent_json('idle', session='S0')}]})
        self.assertEqual(r.returncode, 1)
        self.assertIn('pane wT:p0 still answers after the close', r.stderr)
        self.assertEqual(self.closes(), [['pane', 'close', 'wT:p0']])
        self.assertFalse((self.dir / 'closed.json').exists())

    def test_records_the_name_this_agent_kept_when_the_rename_fails(self):
        taken = {'out': json.dumps({'error': {'code': 'agent_name_taken'}}), 'code': 1}
        me = {'out': agent_json('working', session='N1', pane='wT:p1', name='lead-repo-next')}
        r = self.close({'agent get': [{'out': agent_json('idle', session='S0')}, NOT_FOUND, me],
                        'agent rename': [taken]})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('could not rename this agent to lead-repo', r.stderr)
        self.assertIn('agent_name_taken', r.stderr)
        closed = json.loads((self.dir / 'closed.json').read_text())
        self.assertEqual(closed['successor']['name'], 'lead-repo-next')
        self.assertEqual(json.loads((self.dir.parent / 'lead.json').read_text())['name'], 'lead-repo-next')

    def test_slug_names_the_lead(self):
        r = self.close({'agent get': [{'out': agent_json('idle', session='S0')}, NOT_FOUND]}, args=('--slug', 'Sample'))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(['agent', 'rename', 'wT:p1', 'lead-sample'], herdr_calls(self.log))

    def test_refuses_to_close_its_own_pane(self):
        env = self.prepare({'agent get': [{'out': agent_json('idle', session='S0')}, NOT_FOUND]})
        env['HERDR_PANE_ID'] = 'wT:p0'
        r = self.close(None, env=env)
        self.assertEqual(r.returncode, 1)
        self.assertIn("the predecessor pane wT:p0 is this agent's own pane", r.stderr)
        self.assertEqual(self.closes(), [])

    # Usage errors surface before the close: after it, a bad name could only be recorded, not refused.

    def test_a_bad_name_argument_exits_2_before_the_close(self):
        for args in (('--slug',), ('--bogus',)):
            r = self.close({'agent get': [{'out': agent_json('idle', session='S0')}, NOT_FOUND]}, args=args)
            self.assertEqual(r.returncode, 2, args)
            self.assertIn('could not settle the lead name', r.stderr)
            self.assertEqual(self.closes(), [], args)
            self.assertFalse((self.dir / 'closed.json').exists(), args)

    def test_a_checklist_without_a_repo_exits_2_before_the_close(self):
        env = self.prepare({'agent get': [{'out': agent_json('idle', session='S0')}, NOT_FOUND]})
        chk = json.loads((self.dir / 'checklist.json').read_text())
        del chk['repo']
        (self.dir / 'checklist.json').write_text(json.dumps(chk))
        r = self.close(None, env=env)
        self.assertEqual(r.returncode, 2)
        self.assertIn('the checklist names no repo', r.stderr)
        self.assertEqual(self.closes(), [])

    def test_without_a_claude_session_id_exits_2_before_the_close(self):
        env = self.prepare({'agent get': [{'out': agent_json('idle', session='S0')}, NOT_FOUND]})
        env.pop('CLAUDE_CODE_SESSION_ID')
        r = self.close(None, env=env)
        self.assertEqual(r.returncode, 2)
        self.assertIn('CLAUDE_CODE_SESSION_ID is not set', r.stderr)
        self.assertEqual(herdr_calls(self.log), [])

    def test_a_failed_record_write_exits_1(self):
        (self.dir.parent / 'lead.json').mkdir()
        r = self.close({'agent get': [{'out': agent_json('idle', session='S0')}, NOT_FOUND]})
        self.assertEqual(r.returncode, 1)
        self.assertIn('relay-close: closed wT:p0 but could not write the records', r.stderr)
        self.assertEqual(self.closes(), [['pane', 'close', 'wT:p0']])

    def test_outside_herdr_exits_2(self):
        for var in ('HERDR_ENV', 'HERDR_PANE_ID'):
            env = self.prepare({'agent get': [{'out': agent_json('idle', session='S0')}, NOT_FOUND]})
            env.pop(var)
            r = self.close(None, env=env)
            self.assertEqual(r.returncode, 2, var)
            self.assertIn('not inside herdr', r.stderr)
            self.assertEqual(herdr_calls(self.log), [], var)


if __name__ == '__main__':
    unittest.main()

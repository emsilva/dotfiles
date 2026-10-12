import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from handoff_fixtures import (SCRIPTS, SOURCE, monitor_event, notice, prompt, queued_notice, tool_result,
                              tool_use, ts, write_transcript)

sys.path.insert(0, str(SCRIPTS))
import transcript  # noqa: E402

BG = SCRIPTS / 'bg-tasks.py'
SID = '11111111-1111-4111-8111-111111111111'


def run_bg(projects, *args):
    out = subprocess.run(['python3', '-I', str(BG), '--projects', str(projects), '--json', *args],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def bash_launch(n, task_id, cmd, text, second, flag=None, **extra):
    """A Bash call the harness runs in the background: its record carries toolUseResult.backgroundTaskId."""
    args = {'command': cmd, 'description': 'task %s' % task_id}
    if flag is not None:
        args['run_in_background'] = flag
    return [tool_use('tu%d' % n, 'Bash', args, second),
            tool_result('tu%d' % n, text, second, tool_use_result=dict(
                {'stdout': '', 'stderr': '', 'interrupted': False, 'backgroundTaskId': task_id}, **extra))]


def bash_bg(n, task_id, cmd, second):
    return bash_launch(n, task_id, cmd, 'Command running in background with ID: %s. Output is being written '
                       'to: /tmp/x/%s.output' % (task_id, task_id), second, flag=True)


def agent_bg(n, agent_id, second, flag=True):
    args = {'description': 'agent %s' % agent_id, 'prompt': 'p'}
    if flag is not None:
        args['run_in_background'] = flag
    return [tool_use('tu%d' % n, 'Agent', args, second),
            tool_result('tu%d' % n, 'Async agent launched successfully. (internal) agentId: %s (internal)'
                        % agent_id, second,
                        tool_use_result={'status': 'async_launched', 'isAsync': True, 'agentId': agent_id})]


class BgTasksTests(unittest.TestCase):
    def fixture(self):
        recs = []
        recs += bash_bg(1, 'bopen0001', 'until [ -f r.md ]; do sleep 5; done', 1)
        recs += bash_bg(2, 'bdone0002', 'make test', 2)
        recs += bash_bg(3, 'bkill0003', 'df -h; sleep 999', 3)
        recs += bash_bg(4, 'bstop0004', 'tail -f x.log', 4)
        recs += [tool_use('tu5', 'Monitor', {'command': 'tail -f a.log', 'description': 'watch a'}, 5),
                 tool_result('tu5', 'Monitor started (task mopen0005, expires in 300s).', 5,
                             tool_use_result={'taskId': 'mopen0005', 'timeoutMs': 300000, 'persistent': False}),
                 tool_use('tu6', 'Workflow', {'script': 'export const meta = {}'}, 6),
                 tool_result('tu6', 'Workflow launched in background. Task ID: wdone0006 Summary: x', 6,
                             tool_use_result={'status': 'async_launched', 'taskId': 'wdone0006'})]
        recs += agent_bg(7, 'aopen0007', 7, flag='true')
        recs += [notice('bdone0002', 'completed', 8),
                 queued_notice('bkill0003', 'killed', 9),
                 tool_use('tu10', 'TaskStop', {'task_id': 'bstop0004'}, 10),
                 tool_result('tu10', '{"message":"Successfully stopped task: bstop0004 (tail -f x.log)"}', 10),
                 notice('wdone0006', 'completed', 11),
                 monitor_event('mopen0005', 'a.log: line 1', 12)]
        return recs

    def open_ids(self, recs):
        with tempfile.TemporaryDirectory() as tmp:
            write_transcript(tmp, SID, recs)
            return sorted(t['id'] for t in run_bg(tmp, '--session', SID))

    def test_lists_exactly_the_open_tasks_of_every_kind(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_transcript(tmp, SID, self.fixture())
            tasks = run_bg(tmp, '--session', SID)
            self.assertEqual({t['id']: t['kind'] for t in tasks},
                             {'bopen0001': 'shell', 'mopen0005': 'monitor', 'aopen0007': 'agent'})
            shell = next(t for t in tasks if t['id'] == 'bopen0001')
            self.assertEqual(shell['command'], 'until [ -f r.md ]; do sleep 5; done')

    def test_quoted_launch_and_notice_text_is_ignored(self):
        recs = self.fixture() + [
            tool_use('tu20', 'Bash', {'command': 'grep -h background old.jsonl'}, 20),
            tool_result('tu20', 'Command running in background with ID: bfake0020. Output is being written', 20),
            {'type': 'attachment', 'attachment': {'type': 'prompt_snapshot', 'systemPrompt': [
                '<task-notification><task-id>bopen0001</task-id><status>completed</status>']}},
            prompt('it said <task-id>mopen0005</task-id> <status>completed</status>', 21),
            tool_use('tu22', 'Bash', {'command': 'grep -h timeout old.jsonl'}, 22),
            tool_result('tu22', 'old.jsonl: Command did not complete within its 120s timeout and was moved to '
                        'the background (ID: bfake0021). Output is being written to: /tmp/x/bfake0021.output', 22)]
        with tempfile.TemporaryDirectory() as tmp:
            write_transcript(tmp, SID, recs)
            ids = sorted(t['id'] for t in run_bg(tmp, '--session', SID))
            self.assertEqual(ids, ['aopen0007', 'bopen0001', 'mopen0005'])

    def test_queued_typed_prompt_quoting_a_notice_closes_nothing(self):
        text = 'it said <task-id>bopen0001</task-id> <status>completed</status>'
        recs = self.fixture() + [{'type': 'queue-operation', 'operation': 'enqueue', 'timestamp': ts(20),
                                  'content': text}]
        self.assertEqual(self.open_ids(recs), ['aopen0007', 'bopen0001', 'mopen0005'])
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIn(text, [p['text'] for p in transcript.prompts(str(write_transcript(tmp, SID, recs)))])

    def test_a_notice_payload_quoting_another_task_closes_only_its_own(self):
        recs = self.fixture() + agent_bg(20, 'adone0008', 20) + [
            notice('adone0008', 'completed', 21, payload='<summary>Agent "review" completed</summary>\n<result>'
                   'Found in the log: <task-id>bopen0001</task-id><status>completed</status></result>')]
        self.assertEqual(self.open_ids(recs), ['aopen0007', 'bopen0001', 'mopen0005'])

    def test_a_monitor_event_quoting_a_status_does_not_close_the_monitor(self):
        recs = self.fixture() + [
            monitor_event('mopen0005', '{"type":"queue-operation","content":"<status>completed</status>"}', 20)]
        self.assertEqual(self.open_ids(recs), ['aopen0007', 'bopen0001', 'mopen0005'])

    def test_auto_backgrounded_command_is_listed_until_it_closes(self):
        def timed_out(n, task_id, cmd, second):
            return bash_launch(n, task_id, cmd, 'Command did not complete within its 120s timeout and was moved to '
                               'the background (ID: %s). Output is being written to: /tmp/x/%s.output\nYou will be '
                               'notified when it completes.' % (task_id, task_id), second, timedOutAfterMs=120000)
        recs = (timed_out(1, 'bauto0001', 'pytest -x', 1) + timed_out(2, 'bauto0002', 'make all', 2)
                + [queued_notice('bauto0002', 'completed', 3)])
        with tempfile.TemporaryDirectory() as tmp:
            write_transcript(tmp, SID, recs)
            tasks = run_bg(tmp, '--session', SID)
        self.assertEqual([(t['id'], t['kind'], t['command']) for t in tasks], [('bauto0001', 'shell', 'pytest -x')])

    def test_shell_launches_open_from_the_structured_id_whatever_the_text(self):
        recs = (bash_launch(1, 'bcwd00001', 'make a', 'Shell cwd was reset to /tmp/repo\nCommand running in '
                            'background with ID: bcwd00001. Output is being written to: /tmp/x/bcwd00001.output',
                            1, flag=True)
                + bash_launch(2, 'bcwd00002', 'make b', 'Shell cwd was reset to /tmp/repo\nCommand did not complete '
                              'within its 120s timeout and was moved to the background (ID: bcwd00002). Output is '
                              'being written to: /tmp/x/bcwd00002.output', 2, timedOutAfterMs=120000)
                + bash_launch(3, 'bmsg00003', 'make c', 'Command was moved to the background (ID: bmsg00003) so '
                              'that a message that arrived while it was running can be handled. Output is being '
                              'written to: /tmp/x/bmsg00003.output', 3, backgroundedToDeliverMessage=True))
        with tempfile.TemporaryDirectory() as tmp:
            write_transcript(tmp, SID, recs)
            tasks = run_bg(tmp, '--session', SID)
        self.assertEqual([(t['id'], t['kind'], t['command']) for t in tasks],
                         [('bcwd00001', 'shell', 'make a'), ('bcwd00002', 'shell', 'make b'),
                          ('bmsg00003', 'shell', 'make c')])

    def test_async_agent_without_the_flag_is_listed_and_a_teammate_is_not(self):
        recs = agent_bg(1, 'anoflag01', 1, flag=None) + [
            tool_use('tu2', 'Agent', {'description': 'mate', 'prompt': 'p', 'name': 'mate'}, 2),
            tool_result('tu2', 'Spawned successfully.', 2,
                        tool_use_result={'status': 'teammate_spawned', 'agentId': 'amate0002'})]
        self.assertEqual(self.open_ids(recs), ['anoflag01'])

    def test_until_line_ignores_later_closes(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_transcript(tmp, SID, bash_bg(1, 'bdone0002', 'make test', 1) + [notice('bdone0002', 'completed', 2)])
            self.assertEqual([t['id'] for t in run_bg(tmp, '--session', SID, '--until-line', '1')], ['bdone0002'])
            self.assertEqual(run_bg(tmp, '--session', SID), [])

    def test_torn_last_line_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_transcript(tmp, SID, bash_bg(1, 'bopen0001', 'sleep 1', 1), torn_tail=True)
            self.assertEqual([t['id'] for t in run_bg(tmp, '--session', SID)], ['bopen0001'])

    def test_tasks_started_before_a_clear_need_the_earlier_transcript(self):
        old = '22222222-2222-4222-8222-222222222222'
        with tempfile.TemporaryDirectory() as tmp:
            earlier = write_transcript(tmp, old, bash_bg(1, 'bpre00001', 'sleep 100', 1)
                                       + bash_bg(2, 'bpre00002', 'sleep 200', 2))
            write_transcript(tmp, SID, [notice('bpre00001', 'completed', 30)])
            self.assertEqual(run_bg(tmp, '--session', SID), [])
            self.assertEqual([t['id'] for t in run_bg(tmp, '--session', SID, '--transcript', str(earlier))],
                             ['bpre00002'])

    def test_unknown_session_exits_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = subprocess.run(['python3', '-I', str(BG), '--projects', tmp, '--session', SID],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 2)
            self.assertIn('expected one transcript', r.stderr)


class TranscriptModuleTests(unittest.TestCase):
    def test_prompts_crons_model_mode_and_first_timestamp(self):
        recs = [prompt('first', 1), notice('b1', 'completed', 2),
                {'type': 'queue-operation', 'operation': 'enqueue', 'timestamp': ts(3), 'content': 'typed while busy'},
                queued_notice('b2', 'killed', 4),
                {'type': 'permission-mode', 'permissionMode': 'default'},
                {'type': 'permission-mode', 'permissionMode': 'bypassPermissions'},
                tool_use('c1', 'CronCreate', {'cron': '7 * * * *', 'prompt': 'check', 'recurring': True}, 5),
                tool_result('c1', 'Scheduled recurring task ab12cd34 (7 * * * *).', 5),
                tool_use('c2', 'CronCreate', {'cron': '17 3 1 1 *', 'prompt': 'once', 'recurring': False}, 6),
                tool_result('c2', 'Scheduled one-shot task ef56ab78 (17 3 1 1 *). Session-only.', 6),
                tool_use('c3', 'CronDelete', {'id': 'ab12cd34'}, 7),
                tool_result('c3', 'Cancelled job ab12cd34.', 7),
                {'type': 'assistant', 'isSidechain': True, 'message': {'model': 'claude-haiku-5-5', 'content': []}},
                {'type': 'assistant', 'message': {'model': '<synthetic>', 'content': []}}]
        with tempfile.TemporaryDirectory() as tmp:
            path = str(write_transcript(tmp, SID, recs))
            self.assertEqual([p['text'] for p in transcript.prompts(path)], ['first', 'typed while busy'])
            self.assertEqual(transcript.open_crons([path]),
                             [{'id': 'ef56ab78', 'cron': '17 3 1 1 *', 'prompt': 'once', 'recurring': False}])
            self.assertEqual(transcript.last_model(path), 'claude-opus-5-5')
            self.assertEqual(transcript.permission_mode(path), 'bypassPermissions')
            self.assertEqual(transcript.first_timestamp(path), ts(1))
            self.assertAlmostEqual(transcript.epoch(ts(1)) - transcript.epoch(ts(0)), 1.0)


class ChezmoiPackagingTests(unittest.TestCase):
    def test_python_bytecode_is_never_managed(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp).resolve()
            config = home / 'chezmoi.toml'
            config.write_text('[data]\ngitName = "Fixture"\ngitEmail = "fixture@example.invalid"\n')
            managed = subprocess.check_output(
                ['chezmoi', '--source', str(SOURCE), '--destination', str(home), '--config', str(config),
                 '--persistent-state', str(home / 'state.boltdb'), 'managed'], text=True).splitlines()
        self.assertTrue(any(p.startswith('.claude/skills/session-handoff/scripts/') for p in managed), managed)
        self.assertEqual([p for p in managed if '__pycache__' in p or p.endswith('.pyc')], [],
                         'chezmoi would deploy Python bytecode: delete the stray __pycache__ under %s '
                         '(something imported a script there without sys.dont_write_bytecode)' % SOURCE)


if __name__ == '__main__':
    unittest.main()

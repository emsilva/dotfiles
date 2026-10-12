import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from handoff_fixtures import (SCRIPTS, SOURCE, notice, prompt, queued_notice, tool_result, tool_use, ts,
                              write_transcript)

sys.path.insert(0, str(SCRIPTS))
import transcript  # noqa: E402

BG = SCRIPTS / 'bg-tasks.py'
SID = '11111111-1111-4111-8111-111111111111'


def run_bg(projects, *args):
    out = subprocess.run(['python3', '-I', '-B', str(BG), '--projects', str(projects), '--json', *args],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def bash_bg(n, task_id, cmd, second):
    return [tool_use('tu%d' % n, 'Bash', {'command': cmd, 'description': 'task %s' % task_id,
                                          'run_in_background': True}, second),
            tool_result('tu%d' % n, 'Command running in background with ID: %s. Output is being written '
                        'to: /tmp/x/%s.output' % (task_id, task_id), second)]


class BgTasksTests(unittest.TestCase):
    def fixture(self):
        recs = []
        recs += bash_bg(1, 'bopen0001', 'until [ -f r.md ]; do sleep 5; done', 1)
        recs += bash_bg(2, 'bdone0002', 'make test', 2)
        recs += bash_bg(3, 'bkill0003', 'df -h; sleep 999', 3)
        recs += bash_bg(4, 'bstop0004', 'tail -f x.log', 4)
        recs += [tool_use('tu5', 'Monitor', {'command': 'tail -f a.log', 'description': 'watch a'}, 5),
                 tool_result('tu5', 'Monitor started (task mopen0005, expires in 300s).', 5),
                 tool_use('tu6', 'Workflow', {'script': 'export const meta = {}'}, 6),
                 tool_result('tu6', 'Workflow launched in background. Task ID: wdone0006 Summary: x', 6),
                 tool_use('tu7', 'Agent', {'description': 'draft', 'prompt': 'p', 'run_in_background': 'true'}, 7),
                 tool_result('tu7', 'Async agent launched successfully. (internal) agentId: aopen0007 (internal)', 7),
                 notice('bdone0002', 'completed', 8),
                 queued_notice('bkill0003', 'killed', 9),
                 tool_use('tu10', 'TaskStop', {'task_id': 'bstop0004'}, 10),
                 tool_result('tu10', '{"message":"Successfully stopped task: bstop0004 (tail -f x.log)"}', 10),
                 notice('wdone0006', 'completed', 11),
                 notice('mopen0005', 'running', 12)]
        return recs

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
            prompt('it said <task-id>mopen0005</task-id> <status>completed</status>', 21)]
        with tempfile.TemporaryDirectory() as tmp:
            write_transcript(tmp, SID, recs)
            ids = sorted(t['id'] for t in run_bg(tmp, '--session', SID))
            self.assertEqual(ids, ['aopen0007', 'bopen0001', 'mopen0005'])

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
            r = subprocess.run(['python3', '-I', '-B', str(BG), '--projects', tmp, '--session', SID],
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
                         '(a script was run from the source dir without -B)' % SOURCE)


if __name__ == '__main__':
    unittest.main()

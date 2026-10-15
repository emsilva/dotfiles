"""Regression coverage for transcript facts used by the relay safe-point check."""
import sys
import tempfile
import unittest

from handoff_fixtures import SCRIPTS, notice, tool_result, tool_use, write_transcript

sys.path.insert(0, str(SCRIPTS))
import relaylib  # noqa: E402
import transcript  # noqa: E402


class TeammateTests(unittest.TestCase):
    def test_a_structured_teammate_blocks_until_a_terminal_notice(self):
        # Real Agent results use snake-case ids, unlike async_launched's agentId.
        recs = [tool_use('spawn1', 'Agent', {'name': 'reviewer', 'description': 'review'}),
                tool_result('spawn1', 'Spawned successfully.', tool_use_result={
                    'status': 'teammate_spawned', 'agent_id': 'mate1', 'teammate_id': 'mate1',
                    'name': 'reviewer', 'is_splitpane': True})]
        with tempfile.TemporaryDirectory() as tmp:
            path = write_transcript(tmp, 'session', recs)
            tasks = transcript.open_tasks([str(path)])
            self.assertEqual([(t['kind'], t['id']) for t in tasks], [('teammate', 'mate1')])
            self.assertEqual(relaylib.blockers(tmp, tasks),
                             ['teammate mate1 is running inside this session (review)'])
            path = write_transcript(tmp, 'session', recs + [notice('mate1', 'completed')])
            self.assertEqual(transcript.open_tasks([str(path)]), [])

    def test_a_teammate_task_record_is_a_blocker(self):
        with tempfile.TemporaryDirectory() as tmp:
            tasks = [{'kind': 'teammate', 'id': 'mate1', 'description': 'review', 'command': ''}]
            self.assertEqual(relaylib.blockers(tmp, tasks),
                             ['teammate mate1 is running inside this session (review)'])


if __name__ == '__main__':
    unittest.main()

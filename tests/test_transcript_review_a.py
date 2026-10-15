"""Regression coverage for transcript facts used by the relay safe-point check."""
import sys
import tempfile
import unittest

from handoff_fixtures import (SCRIPTS, agents_killed, cron_create, cron_fire, notice, prompt, teammate_spawn,
                              tool_result, tool_use, usage, write_transcript)

sys.path.insert(0, str(SCRIPTS))
import relaylib  # noqa: E402
import transcript  # noqa: E402


class TeammateTests(unittest.TestCase):
    def read(self, recs, until_line=None):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_transcript(tmp, 'session', recs)
            return transcript.open_tasks([str(path)], until_line)

    def test_all_teammates_ended_by_agents_killed_are_not_blockers(self):
        recs = [*teammate_spawn('mate1'), *teammate_spawn('mate2'), agents_killed()]
        with tempfile.TemporaryDirectory() as tmp:
            path = write_transcript(tmp, 'session', recs)
            tasks = transcript.open_tasks([str(path)])
            self.assertEqual(relaylib.blockers(tmp, tasks), [])
            self.assertEqual(tasks, [])

    def test_agents_killed_does_not_close_a_later_teammate_even_with_the_same_id(self):
        recs = [*teammate_spawn(), agents_killed(), *teammate_spawn()]
        self.assertEqual([t['id'] for t in self.read(recs)], ['mate1'])

    def test_a_running_teammate_without_agents_killed_remains_open(self):
        self.assertEqual([t['id'] for t in self.read(teammate_spawn())], ['mate1'])

    def test_agents_killed_closes_agents_but_preserves_other_background_kinds(self):
        recs = [*teammate_spawn()]
        for name, result in [('Agent', {'agentId': 'agent1', 'status': 'async_launched'}),
                             ('Workflow', {'taskId': 'flow1', 'status': 'async_launched'}),
                             ('Bash', {'backgroundTaskId': 'shell1'}), ('Monitor', {'taskId': 'monitor1'})]:
            recs += [tool_use(name, name, {}), tool_result(name, 'started', tool_use_result=result)]
        self.assertEqual([t['kind'] for t in self.read([*recs, agents_killed()])],
                         ['workflow', 'shell', 'monitor'])

    def test_agents_killed_only_takes_effect_at_its_record(self):
        recs = [*teammate_spawn(), agents_killed()]
        self.assertEqual([t['id'] for t in self.read(recs, until_line=1)], ['mate1'])
        self.assertEqual(self.read(recs, until_line=2), [])

    def test_a_quoted_or_sidechain_agents_killed_record_does_not_close_teammates(self):
        for rec in [prompt('agents_killed'),
                    {'type': 'attachment', 'attachment': agents_killed()},
                    dict(agents_killed(), isSidechain=True)]:
            with self.subTest(rec=rec):
                self.assertEqual([t['id'] for t in self.read([*teammate_spawn(), rec])], ['mate1'])

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


class PromptTests(unittest.TestCase):
    def test_empty_queued_and_human_entries_are_not_prompts(self):
        recs = [{'type': 'queue-operation', 'operation': 'enqueue', **extra}
                for extra in ({}, {'content': ''}, {'content': ' \t\n'}, {'content': None})]
        recs += [prompt(''), prompt(' \n'), prompt('owner text'),
                 {'type': 'queue-operation', 'operation': 'enqueue', 'content': 'queued owner text'}]
        with tempfile.TemporaryDirectory() as tmp:
            path = write_transcript(tmp, 'session', recs)
            self.assertEqual([p['text'] for p in transcript.prompts(str(path))],
                             ['owner text', 'queued owner text'])


class CronPromptTests(unittest.TestCase):
    def read(self, recs):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_transcript(tmp, 'session', recs)
            return transcript.prompts(str(path))

    def test_a_cron_enqueue_with_an_equal_fire_prompt_is_not_an_owner_prompt(self):
        recs = cron_fire('cron1', 'check the work')
        self.assertEqual(self.read(recs), [])

    def test_a_cron_enqueue_matches_a_200_character_head_before_delivery_is_written(self):
        text = 'check the work and report progress; ' * 17
        enqueue, dequeue, fire, _ = cron_fire('cron1', text, head=200, origin_null=True)
        self.assertGreater(len(text), 200)
        self.assertLess(fire['timestamp'], enqueue['timestamp'])
        self.assertEqual(self.read([enqueue, dequeue, fire]), [])

    def test_a_scheduled_delivery_identifies_its_enqueue_without_a_fire_record(self):
        enqueue, dequeue, _, delivered = cron_fire('cron1', 'check the work', origin_null=True)
        self.assertEqual(self.read([enqueue, dequeue, delivered]), [])

    def test_a_mid_turn_fire_with_empty_queue_entries_preserves_the_owner_prompt(self):
        _, _, fire, delivered = cron_fire('cron1', 'check the work', head=200, origin_null=True)
        recs = [prompt('owner request'), fire, usage(520_000),
                {'type': 'queue-operation', 'operation': 'enqueue'},
                {'type': 'queue-operation', 'operation': 'dequeue'}, delivered]
        self.assertEqual([p['text'] for p in self.read(recs)], ['owner request'])

    def test_a_queued_owner_can_type_a_cron_prompt_away_from_its_fire(self):
        text = 'check the work'
        enqueue, dequeue, fire, delivered = cron_fire('cron1', text)
        recs = [*cron_create('create1', 'cron1', '*/20 * * * *', text), fire, delivered, usage(520_000),
                enqueue, dequeue, prompt(text)]
        self.assertEqual([p['text'] for p in self.read(recs)], [text, text])

    def test_a_nonadjacent_fire_does_not_reclassify_an_owner_enqueue(self):
        enqueue, dequeue, fire, _ = cron_fire('cron1', 'check the work')
        self.assertEqual([p['text'] for p in self.read([enqueue, dequeue, usage(520_000), fire])],
                         ['check the work'])

    def test_an_adjacent_fire_with_different_text_keeps_the_owner_enqueue(self):
        enqueue, dequeue, _, _ = cron_fire('cron1', 'owner request')
        _, _, fire, _ = cron_fire('cron2', 'different cron prompt')
        self.assertEqual([p['text'] for p in self.read([enqueue, dequeue, fire])], ['owner request'])


if __name__ == '__main__':
    unittest.main()

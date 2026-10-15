"""Regression coverage for transcript facts used by the relay safe-point check."""
import sys
import tempfile
import unittest

from handoff_fixtures import (SCRIPTS, agents_killed, cron_create, cron_fire, cron_fire_with_bookkeeping, hook_context,
                              prompt, teammate_spawn, tool_result, tool_use, usage, write_transcript)

sys.path.insert(0, str(SCRIPTS))
import relaylib  # noqa: E402
import transcript  # noqa: E402


class TeammateTests(unittest.TestCase):
    def read(self, recs, until_line=None):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_transcript(tmp, 'session', recs)
            return transcript.open_tasks([str(path)], until_line)

    def test_a_snake_case_teammate_spawn_is_not_a_transcript_task(self):
        recs = teammate_spawn()
        self.assertIsNone(transcript._launch('Agent', recs[-1]))
        self.assertEqual(self.read(recs), [])

    def test_transcript_teammates_are_not_safe_point_blockers(self):
        recs = [*teammate_spawn('mate1'), *teammate_spawn('mate2')]
        with tempfile.TemporaryDirectory() as tmp:
            path = write_transcript(tmp, 'session', recs)
            tasks = transcript.open_tasks([str(path)])
            self.assertEqual(relaylib.blockers(tmp, tasks), [])
            self.assertEqual(tasks, [])

    def test_an_obsolete_transcript_teammate_kind_is_not_a_blocker(self):
        with tempfile.TemporaryDirectory() as tmp:
            tasks = [{'kind': 'teammate', 'id': 'mate1', 'description': 'review', 'command': ''}]
            self.assertEqual(relaylib.blockers(tmp, tasks), [])


class AgentStopTests(unittest.TestCase):
    def read(self, recs, until_line=None):
        with tempfile.TemporaryDirectory() as tmp:
            path = write_transcript(tmp, 'session', recs)
            return transcript.open_tasks([str(path)], until_line)

    def agent(self, task_id='agent1'):
        tid = 'launch-' + task_id
        return [tool_use(tid, 'Agent', {'description': 'review'}),
                tool_result(tid, 'started', tool_use_result={'agentId': task_id, 'status': 'async_launched'})]

    def test_agents_ended_by_agents_killed_are_not_blockers(self):
        recs = [*self.agent('agent1'), *self.agent('agent2'), agents_killed()]
        with tempfile.TemporaryDirectory() as tmp:
            path = write_transcript(tmp, 'session', recs)
            self.assertEqual(relaylib.blockers(tmp, transcript.open_tasks([str(path)])), [])
            self.assertEqual(transcript.open_tasks([str(path)]), [])

    def test_agents_killed_does_not_close_a_later_agent_even_with_the_same_id(self):
        recs = [*self.agent(), agents_killed(), *self.agent()]
        self.assertEqual([t['id'] for t in self.read(recs)], ['agent1'])

    def test_a_running_agent_without_agents_killed_remains_open(self):
        self.assertEqual([t['id'] for t in self.read(self.agent())], ['agent1'])

    def test_agents_killed_closes_agents_but_preserves_other_background_kinds(self):
        recs = []
        for name, result in [('Agent', {'agentId': 'agent1', 'status': 'async_launched'}),
                             ('Workflow', {'taskId': 'flow1', 'status': 'async_launched'}),
                             ('Bash', {'backgroundTaskId': 'shell1'}), ('Monitor', {'taskId': 'monitor1'})]:
            recs += [tool_use(name, name, {}), tool_result(name, 'started', tool_use_result=result)]
        self.assertEqual([t['kind'] for t in self.read([*recs, agents_killed()])],
                         ['workflow', 'shell', 'monitor'])

    def test_agents_killed_only_takes_effect_at_its_record(self):
        recs = [*self.agent(), agents_killed()]
        self.assertEqual([t['id'] for t in self.read(recs, until_line=1)], ['agent1'])
        self.assertEqual(self.read(recs, until_line=2), [])

    def test_a_quoted_or_sidechain_agents_killed_record_does_not_close_agents(self):
        for rec in [prompt('agents_killed'),
                    {'type': 'attachment', 'attachment': agents_killed()},
                    dict(agents_killed(), isSidechain=True)]:
            with self.subTest(rec=rec):
                self.assertEqual([t['id'] for t in self.read([*self.agent(), rec])], ['agent1'])


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

    def test_a_fire_across_an_assistant_record_identifies_its_enqueue(self):
        enqueue, dequeue, fire, _ = cron_fire('cron1', 'check the work')
        self.assertEqual(self.read([enqueue, dequeue, usage(520_000), fire]), [])

    def test_a_stop_hook_cron_fire_identifies_its_enqueue_across_bookkeeping(self):
        self.assertEqual(self.read(cron_fire_with_bookkeeping('cron1', 'check the work')), [])

    def test_a_busy_turn_cron_fire_identifies_its_enqueue_across_an_assistant(self):
        self.assertEqual(self.read(cron_fire_with_bookkeeping('cron1', 'check the work', order='busy')), [])

    def test_a_fire_head_crosses_nonprompt_records_before_delivery_is_written(self):
        text = 'check the work and report progress; ' * 17
        for order in ('stop', 'busy'):
            with self.subTest(order=order):
                recs = cron_fire_with_bookkeeping('cron1', text, order=order, head=200)
                self.assertEqual(self.read(recs[:-1]), [])

    def test_a_scheduled_delivery_crosses_nonprompt_records_without_a_fire(self):
        enqueue, dequeue, _, delivered = cron_fire('cron1', 'check the work', origin_null=True)
        bookkeeping = [{'type': 'system', 'subtype': 'stop_hook_summary'}, usage(520_000),
                       hook_context('tool1', ['synthetic hook context']), tool_result('tool1', 'done')]
        self.assertEqual(self.read([enqueue, dequeue, *bookkeeping, delivered]), [])

    def test_a_fire_checks_all_pending_enqueues_and_keeps_a_different_owner_text(self):
        enqueue, dequeue, fire, delivered = cron_fire('cron1', 'check the work')
        owner = {'type': 'queue-operation', 'operation': 'enqueue', 'content': 'owner request'}
        self.assertEqual([p['text'] for p in self.read([enqueue, owner, dequeue, usage(520_000), fire, delivered])],
                         ['owner request'])

    def test_a_delivery_checks_all_pending_enqueues_without_a_fire(self):
        enqueue, dequeue, _, delivered = cron_fire('cron1', 'check the work')
        owner = {'type': 'queue-operation', 'operation': 'enqueue', 'content': 'owner request'}
        self.assertEqual([p['text'] for p in self.read([enqueue, owner, dequeue, usage(520_000), delivered])],
                         ['owner request'])

    def test_the_next_human_prompt_ends_the_pending_association(self):
        enqueue, dequeue, fire, delivered = cron_fire('cron1', 'check the work')
        recs = [enqueue, dequeue, usage(520_000), prompt('owner request'), fire, delivered]
        self.assertEqual([p['text'] for p in self.read(recs)], ['check the work', 'owner request'])

    def test_a_human_record_with_scheduled_fields_is_always_preserved(self):
        enqueue, dequeue, fire, delivered = cron_fire('cron1', 'check the work')
        delivered['origin'] = {'kind': 'human'}
        self.assertEqual([p['text'] for p in self.read([enqueue, dequeue, fire, delivered])], ['check the work'])

    def test_a_scheduled_delivery_requires_equal_text_and_ends_the_association(self):
        enqueue, dequeue, fire, _ = cron_fire('cron1', 'check the work plus more')
        _, _, _, delivered = cron_fire('cron1', 'check the work')
        self.assertEqual([p['text'] for p in self.read([enqueue, dequeue, usage(520_000), delivered, fire])],
                         ['check the work plus more'])

    def test_empty_records_are_not_a_prompt_boundary(self):
        enqueue, dequeue, fire, _ = cron_fire('cron1', 'check the work')
        self.assertEqual(self.read([enqueue, dequeue, prompt(''),
                                   {'type': 'queue-operation', 'operation': 'enqueue'}, fire]), [])

    def test_an_adjacent_fire_with_different_text_keeps_the_owner_enqueue(self):
        enqueue, dequeue, _, _ = cron_fire('cron1', 'owner request')
        _, _, fire, _ = cron_fire('cron2', 'different cron prompt')
        self.assertEqual([p['text'] for p in self.read([enqueue, dequeue, fire])], ['owner request'])


if __name__ == '__main__':
    unittest.main()

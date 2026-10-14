import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

from handoff_fixtures import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import relaylib  # noqa: E402

SID = '44444444-4444-4444-8444-444444444444'


def make_relay(project, rid, session=SID, files=(), age=0):
    """A relay dir whose checklist names `session`; every file in it gets an mtime `age` seconds ago.

    files: names (e.g. 'launch.json', 'fired/relay-x-w1') or (name, json-able content) pairs."""
    rdir = Path(project) / 'relay' / rid
    rdir.mkdir(parents=True)
    (rdir / 'checklist.json').write_text(json.dumps({'relay_id': rid, 'predecessor': {'session_id': session}}))
    for f in files:
        name, content = f if isinstance(f, tuple) else (f, {})
        path = rdir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(content) if not isinstance(content, str) else content)
    when = time.time() - age
    for path in rdir.rglob('*'):
        os.utime(path, (when, when))
    return rdir


def slow_git(tmp):
    """A dir holding a `git` that never answers in time (it sleeps 10 s); put it first on PATH."""
    bindir = Path(tmp) / 'slow-git'
    bindir.mkdir()
    exe = bindir / 'git'
    exe.write_text('#!/bin/sh\nexec sleep 10\n')
    exe.chmod(0o755)
    return bindir


class BlockersTests(unittest.TestCase):
    def test_agents_and_workflows_block_shells_and_monitors_do_not(self):
        tasks = [{'kind': 'agent', 'id': 'a1', 'description': 'review', 'command': ''},
                 {'kind': 'workflow', 'id': 'w1', 'description': '', 'command': 'export const meta'},
                 {'kind': 'shell', 'id': 'b1', 'description': 'wait', 'command': 'sleep 9'},
                 {'kind': 'monitor', 'id': 'm1', 'description': 'tail', 'command': 'tail -f x'}]
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(relaylib.blockers(tmp, tasks),
                             ['agent a1 is running inside this session (review)',
                              'workflow w1 is running inside this session (export const meta)'])

    def test_git_mid_merge_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(['git', 'init', '-q', tmp], check=True)
            self.assertEqual(relaylib.blockers(tmp, []), [])
            (Path(tmp) / '.git' / 'MERGE_HEAD').write_text('0' * 40 + '\n')
            self.assertEqual(relaylib.blockers(tmp, []), ['git is mid-operation (MERGE_HEAD present)'])

    def test_a_git_that_does_not_answer_cannot_tell_within_the_bound(self):
        # The gate calls this on the Stop path: a hung git counts as a git that fails (no git line) after its
        # 2 s bound, for the gate and checklist alike, instead of holding the hook past its budget.
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(['git', 'init', '-q', tmp], check=True)
            path = '%s:%s' % (slow_git(tmp), os.environ['PATH'])
            started = time.time()
            with mock.patch.dict(os.environ, {'PATH': path}):
                self.assertEqual(relaylib.blockers(tmp, []), [])
            self.assertLess(time.time() - started, 3.5)


class RelaysOfTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name) / 'proj'

    def tearDown(self):
        self.tmp.cleanup()

    def states(self):
        return {r['id']: r['state'] for r in relaylib.relays_of(str(self.project), SID)}

    def test_each_dir_is_classified_by_fact(self):
        make_relay(self.project, 'R1', files=['launch.json', ('failed.json', {'stage': 'receipt'}), 'closed.json'])
        make_relay(self.project, 'R2', files=['launch.json', ('failed.json', {'stage': 'launch', 'reason': 'x'})])
        make_relay(self.project, 'R3', files=['launch.json', 'receipt.json', 'handover.md'])
        make_relay(self.project, 'R4', files=['launch.json'], age=24 * 60)
        make_relay(self.project, 'R5', files=['launch.json'], age=26 * 60)
        self.assertEqual(self.states(), {'R1': 'closed', 'R2': 'failed', 'R3': 'frozen', 'R4': 'in_progress',
                                         'R5': 'abandoned'})

    def test_fresh_fix_and_fired_files_keep_an_old_relay_in_progress(self):
        old = make_relay(self.project, 'R1', files=['launch.json', 'receipt.json'], age=40 * 60)
        (old / 'fix-1').write_text('')
        make_relay(self.project, 'R2', files=['launch.json'], age=40 * 60)
        fired = self.project / 'relay' / 'R2' / 'fired'
        fired.mkdir()
        (fired / 'relay-R2-w1').write_text('')
        self.assertEqual(self.states(), {'R1': 'in_progress', 'R2': 'in_progress'})

    def test_failure_time_is_the_failed_json_mtime_and_its_fields_are_read(self):
        make_relay(self.project, 'R1', files=[('failed.json', {'stage': 'check', 'reason': 'FAIL identity: x',
                                                                'at': '2026-10-13T10:15:27'})], age=600)
        [entry] = relaylib.relays_of(str(self.project), SID)
        self.assertAlmostEqual(entry['failed_at'], time.time() - 600, delta=5)
        self.assertEqual((entry['stage'], entry['reason']), ('check', 'FAIL identity: x'))

    def test_an_abandoned_dir_failed_at_its_last_activity(self):
        make_relay(self.project, 'R1', files=['launch.json'], age=30 * 60)
        [entry] = relaylib.relays_of(str(self.project), SID)
        self.assertEqual(entry['state'], 'abandoned')
        self.assertAlmostEqual(entry['failed_at'], time.time() - 30 * 60, delta=5)

    def test_other_sessions_gate_state_and_unreadable_checklists_are_ignored(self):
        make_relay(self.project, 'R1', session='someone-else', files=['launch.json'])
        gate = self.project / 'relay' / 'gate'
        gate.mkdir(parents=True)
        (gate / (SID + '.json')).write_text('{}')
        (self.project / 'relay' / 'lead.json').write_text(json.dumps({'session_id': SID}))
        bad = self.project / 'relay' / 'R2'
        bad.mkdir()
        (bad / 'checklist.json').write_text('{torn')
        self.assertEqual(relaylib.relays_of(str(self.project), SID), [])

    def test_a_torn_failed_json_is_still_a_failure(self):
        make_relay(self.project, 'R1', files=[('failed.json', '{"stage": "rec')])
        [entry] = relaylib.relays_of(str(self.project), SID)
        self.assertEqual((entry['state'], entry['stage'], entry['reason']), ('failed', None, None))

    def test_a_failure_after_handover_md_is_a_hand_over_failure_whatever_stage_it_names(self):
        make_relay(self.project, 'R1', files=['handover.md', ('failed.json', {'stage': 'check', 'reason': 'send'})])
        make_relay(self.project, 'R2', files=['handover.md', ('failed.json', {'reason': 'x'})])
        make_relay(self.project, 'R3', files=['handover.md', ('failed.json', '{"stage": "rec')])
        make_relay(self.project, 'R4', files=['handover.md', ('failed.json', {'stage': 'check'}), 'closed.json'])
        got = {r['id']: (r['state'], r['stage'], r['reason']) for r in relaylib.relays_of(str(self.project), SID)}
        self.assertEqual(got, {'R1': ('failed', 'handover', 'send'), 'R2': ('failed', 'handover', 'x'),
                               'R3': ('failed', 'handover', None), 'R4': ('closed', None, None)})

    def test_no_relay_dir_at_all(self):
        self.assertEqual(relaylib.relays_of(str(self.project), SID), [])


class WillRepeatTests(unittest.TestCase):
    def test_identity_at_the_check_and_a_taken_name_repeat(self):
        self.assertTrue(relaylib.will_repeat({'stage': 'check', 'reason': "FAIL identity: successor "
                                                                          "permission_mode 'default'"}))
        self.assertTrue(relaylib.will_repeat({'stage': 'launch', 'reason': 'agent start: agent_name_taken'}))

    def test_other_failures_do_not(self):
        self.assertFalse(relaylib.will_repeat({'stage': 'receipt', 'reason': 'successor=gone receipt=none'}))
        self.assertFalse(relaylib.will_repeat({'stage': 'launch', 'reason': 'identity: x'}))
        self.assertFalse(relaylib.will_repeat({'stage': None, 'reason': None}))


if __name__ == '__main__':
    unittest.main()

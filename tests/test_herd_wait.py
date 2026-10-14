"""herd.py wait: each event, the report row, the marker and fired file, and what never fires."""
import os
import subprocess
import time
import unittest

from herd_fixtures import HerdCase, listing

FAST = ('--interval', '0.1')
PAST = '2026-10-14T10:05:00Z'


class WaitCase(HerdCase):
    def setUp(self):
        super().setUp()
        self.out = self.root / 'out'
        self.out.mkdir()
        self.report = self.out / 'REPORT.md'
        self.blocked = self.out / 'BLOCKED.md'
        self.one = self.launch_row('one-xhigh-aaaa', 'wT:p2')
        self.record(self.one, self.dispatch_row(self.one['launch_id'], deliverable=self.report,
                                                blocked=self.blocked, sent_at=PAST))

    def entry(self, status, pane='wT:p2', name='one-xhigh-aaaa'):
        return {'pane_id': pane, 'tab_id': 'wT:t1', 'cwd': str(self.repo), 'agent': 'codex', 'agent_status': status,
                'name': name}

    def herd_with(self, *polls):
        """One pane list (and agent list) per poll; the last repeats."""
        answers = [listing(*poll) for poll in polls]
        return {'pane list': [p for p, _ in answers], 'agent list': [a for _, a in answers]}

    def wait(self, answers, *extra, timeout=30):
        return self.herd(answers, 'wait', *FAST, *extra, timeout=timeout)

    def first_poll(self):
        """Block until the started waiter has polled herdr once (it has read the record by then)."""
        deadline = time.monotonic() + 15
        while not self.calls(['pane', 'list']) and time.monotonic() < deadline:
            time.sleep(0.05)

    def reported(self):
        return [(r['launch_id'], r['seq'], r['event']) for r in self.rows() if r['type'] == 'reported']


class EventTests(WaitCase):
    def test_a_deliverable_with_an_idle_worker_on_two_polls(self):
        self.report.write_text('done\n')
        r = self.wait(self.herd_with([self.entry('working')], [self.entry('idle')], [self.entry('done')]))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), 'one-xhigh-aaaa deliverable %s' % self.report)
        self.assertEqual(len(self.calls(['pane', 'list'])), 3)
        self.assertEqual(self.reported(), [(self.one['launch_id'], 1, 'deliverable')])

    def test_a_deliverable_older_than_its_dispatch_never_fires(self):
        self.report.write_text('old\n')
        old = time.time() - 10 ** 7
        os.utime(self.report, (old, old))
        r = self.wait(self.herd_with([self.entry('idle')], [self.entry('idle')], [self.entry('idle')], []))
        self.assertEqual(r.stdout.strip(), 'one-xhigh-aaaa status=gone wT:p2')

    def test_a_blocked_file_written_after_the_dispatch(self):
        self.blocked.write_text('which base?\n')
        r = self.wait(self.herd_with([self.entry('idle')]))
        self.assertEqual(r.stdout.strip(), 'one-xhigh-aaaa blocked %s' % self.blocked)

    def test_a_worker_blocked_for_four_polls(self):
        r = self.wait(self.herd_with(*[[self.entry('blocked')]] * 4))
        self.assertEqual(r.stdout.strip(), 'one-xhigh-aaaa status=blocked wT:p2')
        self.assertEqual(len(self.calls(['pane', 'list'])), 4)

    def test_a_brief_block_does_not_fire(self):
        r = self.wait(self.herd_with(*[[self.entry('blocked')]] * 3, [self.entry('working')], []))
        self.assertEqual(r.stdout.strip(), 'one-xhigh-aaaa status=gone wT:p2')

    def test_a_failed_herdr_read_is_not_a_gone_worker(self):
        self.report.write_text('done\n')
        panes, agents = listing(self.entry('idle'))
        r = self.wait({'pane list': [{'out': 'boom', 'code': 1}, panes], 'agent list': [agents]})
        self.assertEqual(r.stdout.strip(), 'one-xhigh-aaaa deliverable %s' % self.report)
        self.assertIn('herdr pane list exited 1', r.stderr)

    def test_names_limit_the_watch(self):
        two = self.launch_row('two-xhigh-bbbb', 'wT:p3')
        self.record(two, self.dispatch_row(two['launch_id'], sent_at=PAST))
        r = self.wait(self.herd_with([self.entry('idle')]), '--names', 'two-xhigh-bbbb')
        self.assertEqual(r.stdout.strip(), 'two-xhigh-bbbb status=gone wT:p3')


class ReportTests(WaitCase):
    def test_a_reported_dispatch_is_not_watched_again(self):
        self.record({'type': 'reported', 'launch_id': self.one['launch_id'], 'seq': 1, 'event': 'deliverable'})
        r = self.wait(self.herd_with([self.entry('idle')]))
        self.assertEqual(r.returncode, 1)
        self.assertIn('nothing to wait on', r.stderr)

    def test_an_event_another_waiter_recorded_fires_here_too(self):
        # A relay runs two waiters on one worker: the first to see the event records it, the other still fires.
        proc = self.start(self.herd_with([self.entry('working')]), 'wait', *FAST)
        self.first_poll()
        self.record({'type': 'reported', 'launch_id': self.one['launch_id'], 'seq': 1, 'event': 'deliverable'})
        out, err = proc.communicate(timeout=20)
        self.assertEqual(proc.returncode, 0, err)
        self.assertEqual(out.strip(), 'one-xhigh-aaaa deliverable %s' % self.report)
        self.assertEqual(len(self.reported()), 1)

    def test_the_marker_is_in_the_process_list_and_the_fired_file_is_left(self):
        fired = self.root / 'relay' / 'fired'
        proc = self.start(self.herd_with([self.entry('working')]), 'wait', *FAST, '--marker', 'relay-R1-w1',
                          '--fired-dir', str(fired))
        self.first_poll()
        ps = subprocess.run(['ps', '-ww', '-o', 'command=', '-p', str(proc.pid)], capture_output=True, text=True)
        self.assertIn('--marker relay-R1-w1 ', ps.stdout)
        self.blocked.write_text('?\n')
        out, err = proc.communicate(timeout=20)
        self.assertEqual(proc.returncode, 0, err)
        self.assertEqual(out.strip(), 'one-xhigh-aaaa blocked %s' % self.blocked)
        self.assertTrue((fired / 'relay-R1-w1').is_file())

    def test_a_worker_the_lead_closes_is_not_reported_gone(self):
        proc = self.start(self.herd_with([self.entry('working')], []), 'wait', '--interval', '1')
        self.first_poll()
        self.record({'type': 'close', 'launch_id': self.one['launch_id'], 'reason': 'not needed'})
        out, err = proc.communicate(timeout=20)
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(out, '')
        self.assertIn('nothing left to wait on', err)

    def test_a_fired_dir_needs_a_marker(self):
        r = self.wait(self.herd_with([self.entry('idle')]), '--fired-dir', str(self.root / 'fired'))
        self.assertEqual(r.returncode, 1)
        self.assertIn('--fired-dir needs --marker', r.stderr)



if __name__ == '__main__':
    unittest.main()

"""herd.py status and the herd-snapshot.sh shim: workers, unclassified panes, lost and closed launches."""
import subprocess
import unittest

from handoff_fixtures import SCRIPTS
from herd_fixtures import LEAD, HerdCase, listing, ok


class StatusTests(HerdCase):
    def herd_of(self, *entries):
        panes, agents = listing(*entries)
        return {'pane list': [panes], 'agent list': [agents], 'pane read': [ok()]}

    def section(self, out, title):
        start = out.index('## ' + title)
        end = out.find('\n## ', start + 1)
        return out[start:end if end != -1 else len(out)]

    def test_each_section(self):
        report = self.root / 'r.md'
        one = self.launch_row('one-xhigh-aaaa', 'wT:p2', session='C1')
        two = self.launch_row('two-xhigh-bbbb', 'wT:p5')
        old = self.launch_row('old-xhigh-cccc', 'wT:p7')
        self.record(one, two, old, self.dispatch_row(one['launch_id'], deliverable=report),
                    {'type': 'close', 'launch_id': old['launch_id'], 'reason': 'done with it'})
        report.write_text('x')   # written after its dispatch (2026-10-14): new
        out = self.herd(self.herd_of(
            {'pane_id': LEAD, 'tab_id': 'wT:t1', 'cwd': str(self.repo), 'agent': 'claude', 'agent_status': 'working'},
            {'pane_id': 'wT:p2', 'tab_id': 'wT:t1', 'cwd': str(self.repo), 'agent': 'codex', 'agent_status': 'idle',
             'agent_session': {'value': 'C1'}, 'name': 'one-xhigh-aaaa'},
            {'pane_id': 'wT:p3', 'tab_id': 'wT:t1', 'cwd': str(self.repo / 'sub'), 'agent': 'claude',
             'agent_status': 'idle', 'name': 'scan-high'},
            {'pane_id': 'wT:p4', 'tab_id': 'wT:t1', 'cwd': str(self.repo), 'agent': 'claude', 'agent_status': 'idle',
             'name': 'notes'},
            {'pane_id': 'wT:p8', 'tab_id': 'wT:t9', 'cwd': '/elsewhere', 'agent': 'claude', 'agent_status': 'idle'}),
            'status').stdout
        workers = self.section(out, 'workers')
        self.assertIn('## workers (1)', workers)
        self.assertIn('| one-xhigh-aaaa | codex · gpt-6.1-sol · xhigh | wT:p2 | idle | C1 | %s | new |' % ('ab' * 8),
                      workers)
        self.assertIn('dispatch 1 sent 2026-10-14T10:05', workers)
        unclassified = self.section(out, 'unclassified')
        self.assertIn('## unclassified (2)', unclassified)
        self.assertIn('| wT:p3 | claude | scan-high | idle | unknown | %s | looks like a worker |'
                      % (self.repo / 'sub'), unclassified)
        self.assertIn('| wT:p4 | claude | notes | idle | unknown | %s | - |' % self.repo, unclassified)
        self.assertNotIn(LEAD, unclassified)
        self.assertNotIn('wT:p8', out)
        lost = self.section(out, 'lost')
        self.assertIn('## lost (1)', lost)
        self.assertIn('| two-xhigh-bbbb | wT:p5 | unknown |', lost)
        self.assertNotIn('## closed', out)
        out = self.herd(self.herd_of(), 'status', '--all').stdout
        self.assertIn('| old-xhigh-cccc | wT:p7 | done with it |', self.section(out, 'closed'))

    def test_deliverable_states(self):
        one = self.launch_row('one-xhigh-aaaa', 'wT:p2')
        report = self.root / 'r.md'
        self.record(one, self.dispatch_row(one['launch_id'], deliverable=report, sent_at='2099-01-01T00:00:00Z'))
        entry = {'pane_id': 'wT:p2', 'tab_id': 'wT:t1', 'cwd': str(self.repo), 'agent': 'codex',
                 'agent_status': 'working', 'name': 'one-xhigh-aaaa'}
        self.assertIn('| missing |', self.herd(self.herd_of(entry), 'status').stdout)
        report.write_text('x')
        self.assertIn('| stale |', self.herd(self.herd_of(entry), 'status').stdout)

    def test_a_shell_pane_shows_its_last_lines(self):
        panes, agents = listing({'pane_id': 'wT:p3', 'tab_id': 'wT:t1', 'cwd': str(self.repo)})
        out = self.herd({'pane list': [panes], 'agent list': [agents],
                         'pane read': [{'out': '$ task test\nRan 12 tests\nOK\n'}]}, 'status').stdout
        self.assertIn('| wT:p3 | shell | - | - | unknown | %s | shell: Ran 12 tests / OK |' % self.repo, out)

    def test_extra_roots_widen_the_scope(self):
        entry = {'pane_id': 'wT:p8', 'tab_id': 'wT:t9', 'cwd': '/elsewhere/grading', 'agent': 'claude',
                 'agent_status': 'idle'}
        for args in (['/elsewhere'], ['--extra-root', '/elsewhere']):
            with self.subTest(args=args):
                self.assertIn('| wT:p8 |', self.herd(self.herd_of(entry), 'status', *args).stdout)

    def test_outside_herdr_there_is_nothing_to_record(self):
        r = self.herd({}, 'status', drop=('HERDR_ENV',))
        self.assertEqual((r.returncode, r.stdout.strip()), (0, 'herd: not inside herdr (HERDR_ENV unset), nothing to record'))
        self.assertEqual(self.calls(['pane']), [])

    def test_without_a_session_every_pane_is_unclassified(self):
        entry = {'pane_id': 'wT:p2', 'tab_id': 'wT:t1', 'cwd': str(self.repo), 'agent': 'codex',
                 'agent_status': 'idle', 'name': 'one-xhigh-aaaa'}
        self.record(self.launch_row('one-xhigh-aaaa', 'wT:p2'))
        r = self.herd(self.herd_of(entry), 'status', drop=('CLAUDE_CODE_SESSION_ID',))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('record: none: CLAUDE_CODE_SESSION_ID is not set', r.stdout)
        self.assertIn('| wT:p2 | codex | one-xhigh-aaaa | idle | unknown | %s | looks like a worker |' % self.repo,
                      r.stdout)

    def test_a_damaged_record_or_a_failed_herdr_read_is_an_error_not_an_empty_herd(self):
        r = self.herd({'pane list': [{'out': 'boom', 'code': 1}], 'agent list': [ok({'result': {'agents': []}})]},
                      'status')
        self.assertEqual(r.returncode, 2)
        self.assertIn('herdr pane list exited 1', r.stderr)
        self.pdir.mkdir(parents=True, exist_ok=True)
        (self.pdir / 'herd.jsonl').write_text('{torn\n')
        r = self.herd(self.herd_of(), 'status')
        self.assertEqual(r.returncode, 2)
        self.assertIn('line 1 does not parse', r.stderr)


class ShimTests(HerdCase):
    def test_herd_snapshot_sh_is_status_with_extra_roots(self):
        panes, agents = listing({'pane_id': 'wT:p8', 'tab_id': 'wT:t9', 'cwd': '/elsewhere/grading',
                                 'agent': 'claude', 'agent_status': 'idle'})
        r = subprocess.run(['bash', str(SCRIPTS / 'herd-snapshot.sh'), '/elsewhere', '--projects', str(self.projects)],
                           capture_output=True, text=True,
                           env=self.env({'pane list': [panes], 'agent list': [agents]}), cwd=str(self.repo))
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn('# herd status', r.stdout)
        self.assertIn('record: %s' % (self.pdir / 'herd.jsonl'), r.stdout)
        self.assertIn('| wT:p8 |', r.stdout)


if __name__ == '__main__':
    unittest.main()

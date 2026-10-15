"""herd.py adopt (a worker launched by hand) and close (an idle worker whose work is safe)."""
import json
import subprocess
import unittest

from herd_fixtures import NOT_FOUND, HerdCase, agent, listing, ok


def agent_at(pane, cwd, name=None, session=None, kind='codex', status='idle'):
    answer = json.loads(agent(status, pane, session=session, name=name, kind=kind)['out'])
    answer['result']['agent']['cwd'] = str(cwd)
    return ok(answer)


class AdoptTests(HerdCase):
    def test_failed_agent_reads_are_errors_except_agent_not_found(self):
        for answer in ({'out': 'transport failed', 'code': 1},
                       ok({'result': 'malformed'})):
            with self.subTest(answer=answer):
                r = self.herd({'agent get': [answer]}, 'adopt', 'wT:p4', '--role', 'scan')
                self.assertEqual(r.returncode, 2, r.stderr)
                self.assertNotIn('hosts no agent', r.stderr)
                self.assertNotIn('Traceback', r.stderr)
                self.assertEqual(self.rows(), [])

    def test_a_named_worker_keeps_its_name(self):
        r = self.herd({'agent get': [agent_at('wT:p4', self.repo, name='r6-size-xhigh', session='C4')]},
                      'adopt', 'wT:p4', '--role', 'size', '--model', 'gpt-6.1-sol', '--effort', 'xhigh')
        self.assertEqual(r.returncode, 0, r.stderr)
        launch = json.loads(r.stdout)['launch']
        self.assertEqual({k: launch[k] for k in ('name', 'pane_id', 'kind', 'mode', 'cwd', 'session_id', 'adopted',
                                                 'started_at', 'model', 'effort')},
                         {'name': 'r6-size-xhigh', 'pane_id': 'wT:p4', 'kind': 'codex', 'mode': 'readonly',
                          'cwd': str(self.repo), 'session_id': 'C4', 'adopted': True, 'started_at': None,
                          'model': 'gpt-6.1-sol', 'effort': 'xhigh'})
        self.assertEqual(self.calls(['agent', 'rename']), [])
        self.assertEqual([r['type'] for r in self.rows()], ['launch'])

    def test_an_unnamed_worker_gets_a_generated_name(self):
        r = self.herd({'agent get': [agent_at('wT:p4', self.repo)], 'agent list': [ok({'result': {'agents': []}})]},
                      'adopt', 'wT:p4', '--role', 'scan', '--effort', 'high')
        name = json.loads(r.stdout)['launch']['name']
        self.assertRegex(name, r'^scan-high-[0-9a-f]{4}$')
        self.assertEqual(self.calls(['agent', 'rename']), [['agent', 'rename', 'wT:p4', name]])
        r = self.herd({'agent get': [agent_at('wT:p6', self.repo)]}, 'adopt', 'wT:p6', '--role', 'scan')
        self.assertEqual(r.returncode, 1)
        self.assertIn('pass --effort', r.stderr)

    def test_a_worker_in_a_worktree_is_a_builder_and_its_brief_is_recorded(self):
        wt = self.repo / '.claude' / 'worktrees' / 'x'
        subprocess.run(['git', '-C', str(self.repo), 'worktree', 'add', '-q', str(wt), '-b', 'feat/x'], check=True)
        brief = self.root / 'BRIEF.md'
        brief.write_text('b\n')
        r = self.herd({'agent get': [agent_at('wT:p4', wt, name='x-xhigh', session='C4')]}, 'adopt', 'wT:p4',
                      '--role', 'x', '--brief', str(brief), '--deliverable', str(self.root / 'R.md'))
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)
        self.assertEqual((out['launch']['mode'], out['launch']['worktree'], out['launch']['branch']),
                         ('builder', str(wt), 'feat/x'))
        self.assertEqual((out['dispatch']['seq'], out['dispatch']['blocked'], out['dispatch']['session_id']),
                         (1, str(self.root / 'BLOCKED.md'), 'C4'))

    def test_a_claude_worker_is_a_builder_never_read_only(self):
        r = self.herd({'agent get': [agent_at('wT:p4', self.repo, name='notes-high', session='W4', kind='claude')]},
                      'adopt', 'wT:p4', '--role', 'notes')
        self.assertEqual(r.returncode, 0, r.stderr)
        launch = json.loads(r.stdout)['launch']
        self.assertEqual((launch['mode'], launch['worktree']), ('builder', None))
        r = self.herd({'agent get': [agent_at('wT:p6', self.repo, name='more-high', kind='claude')]},
                      'adopt', 'wT:p6', '--role', 'more', '--mode', 'readonly')
        self.assertEqual(r.returncode, 1)
        self.assertIn('cannot be recorded read-only', r.stderr)

    def test_what_cannot_be_adopted(self):
        self.record(self.launch_row('one-xhigh-aaaa', 'wT:p2', session='C1'))
        for answer, needle in ((agent_at('wT:p2', self.repo, session='C1'), 'already recorded as one-xhigh-aaaa'),
                               # its name is a live launch's, its session is not: another agent, same name
                               (agent_at('wT:p5', self.repo, name='one-xhigh-aaaa', session='C5'),
                                'adopt with --rename'),
                               (NOT_FOUND, 'hosts no agent')):
            with self.subTest(needle=needle):
                r = self.herd({'agent get': [answer]}, 'adopt', 'wT:p5', '--role', 'x')
                self.assertEqual(r.returncode, 1)
                self.assertIn(needle, r.stderr)
                self.assertEqual(len(self.rows()), 1)
        r = self.herd({}, 'adopt', 'wT:p5', '--role', 'x', '--brief', str(self.root / 'none.md'), '--deliverable', 'r')
        self.assertIn('no brief at', r.stderr)


class CloseTests(HerdCase):
    def herd_of(self, status='idle', pane='wT:p2', **extra):
        panes, agents = listing({'pane_id': pane, 'tab_id': 'wT:t1', 'cwd': str(self.repo), 'agent': 'codex',
                                 'agent_status': status, 'name': 'one-xhigh-aaaa'})
        return dict({'pane list': [panes], 'agent list': [agents], 'agent get': [NOT_FOUND]}, **extra)

    def closes(self):
        return [r['reason'] for r in self.rows() if r['type'] == 'close']

    def test_an_idle_worker_is_closed_and_recorded(self):
        self.record(self.launch_row('one-xhigh-aaaa', 'wT:p2'))
        r = self.herd(self.herd_of(), 'close', 'one-xhigh-aaaa', '--reason', 'delivered')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.calls(['pane', 'close']), [['pane', 'close', 'wT:p2']])
        self.assertEqual(self.closes(), ['delivered'])

    def test_a_working_worker_is_not_closed(self):
        self.record(self.launch_row('one-xhigh-aaaa', 'wT:p2'))
        r = self.herd(self.herd_of('working'), 'close', 'one-xhigh-aaaa')
        self.assertEqual(r.returncode, 1)
        self.assertIn('close only an idle worker', r.stderr)
        self.assertEqual(self.calls(['pane', 'close']), [])

    def test_a_dirty_worktree_keeps_the_builder_open_and_a_clean_one_is_kept(self):
        wt = self.repo / '.claude' / 'worktrees' / 'one'
        subprocess.run(['git', '-C', str(self.repo), 'worktree', 'add', '-q', str(wt), '-b', 'feat/one'], check=True)
        self.record(self.launch_row('one-xhigh-aaaa', 'wT:p2', mode='builder', cwd=wt, worktree=str(wt)))
        (wt / 'wip.txt').write_text('w\n')
        r = self.herd(self.herd_of(), 'close', 'one-xhigh-aaaa')
        self.assertEqual(r.returncode, 1)
        self.assertIn('?? wip.txt', r.stderr)
        self.assertEqual(self.calls(['pane', 'close']), [])
        (wt / 'wip.txt').unlink()
        r = self.herd(self.herd_of(), 'close', 'one-xhigh-aaaa')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(wt.is_dir())

    def test_a_lost_worker_is_only_recorded_closed(self):
        self.record(self.launch_row('one-xhigh-aaaa', 'wT:p2'))
        panes, agents = listing()
        r = self.herd({'pane list': [panes], 'agent list': [agents]}, 'close', 'one-xhigh-aaaa')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.calls(['pane', 'close']), [])
        self.assertEqual(self.closes(), ['lost: no live pane'])

    def test_a_pane_that_does_not_close_is_not_recorded_closed(self):
        self.record(self.launch_row('one-xhigh-aaaa', 'wT:p2'))
        r = self.herd(self.herd_of(**{'agent get': [agent('idle', 'wT:p2')]}), 'close', 'one-xhigh-aaaa',
                      env={'HERD_CLOSE_SECONDS': '1'})
        self.assertEqual(r.returncode, 1)
        self.assertIn('still hosts an agent 1 s after the close', r.stderr)
        self.assertEqual(self.closes(), [])


if __name__ == '__main__':
    unittest.main()

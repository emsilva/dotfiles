"""herd.py launch: placement, the worker's arguments, worktrees, startup dialogs, banner check and clean-up."""
import datetime
import json
import os
import re
import subprocess
import sys
import unittest

from handoff_fixtures import SCRIPTS
from herd_fixtures import (CODEX_BANNER, LEAD, NOT_READY, SID, TAKEN, HerdCase, agent, layout, listing, ok,
                           pane_entry, split)

sys.path.insert(0, str(SCRIPTS))
import herd_launch  # noqa: E402

NAME = re.compile(r'^review-xhigh-[0-9a-f]{4}$')


class PlacementTests(unittest.TestCase):
    def place(self, *panes):
        return herd_launch.placement(json.loads(layout(*panes)['out']), LEAD)

    def test_a_lead_alone_splits_right(self):
        self.assertEqual(self.place((LEAD, 0, 0, 159, 51)), (LEAD, 'right'))

    def test_workers_stack_down_from_the_bottom_of_the_right_column(self):
        self.assertEqual(self.place((LEAD, 0, 0, 80, 51), ('wT:p2', 80, 0, 79, 26), ('wT:p3', 80, 26, 79, 25)),
                         ('wT:p3', 'down'))

    def test_never_a_third_column(self):
        self.assertEqual(self.place((LEAD, 0, 0, 53, 51), ('wT:p2', 53, 0, 53, 51), ('wT:p3', 106, 0, 53, 51)),
                         ('wT:p2', 'down'))


class LaunchTests(HerdCase):
    def answers(self, **extra):
        base = {'agent list': [ok({'result': {'agents': []}})], 'pane layout': [layout((LEAD, 0, 0, 159, 51))],
                'pane split': [split('wT:p9')], 'agent start': [ok()], 'pane read': [CODEX_BANNER],
                'agent get': [agent('idle', 'wT:p9')]}
        base.update(extra)
        return base

    def start_tail(self):
        start = self.calls(['agent', 'start'])[-1]
        return start[start.index('--') + 1:]

    def test_a_read_only_codex_worker_by_default(self):
        r = self.herd(self.answers(), 'launch', 'review')
        self.assertEqual(r.returncode, 0, r.stderr)
        row = json.loads(r.stdout)
        self.assertRegex(row['name'], NAME)
        self.assertEqual(row['name'][-4:], row['launch_id'][:4])
        self.assertEqual({k: row[k] for k in ('pane_id', 'kind', 'model', 'effort', 'mode', 'cwd', 'worktree',
                                              'session_id', 'lead_session', 'adopted')},
                         {'pane_id': 'wT:p9', 'kind': 'codex', 'model': 'gpt-6.1-sol', 'effort': 'xhigh',
                          'mode': 'readonly', 'cwd': str(self.repo), 'worktree': None, 'session_id': None,
                          'lead_session': SID, 'adopted': False})
        self.assertEqual(self.calls(['pane', 'split']),
                         [['pane', 'split', LEAD, '--direction', 'right', '--cwd', str(self.repo), '--no-focus']])
        self.assertEqual(self.calls(['agent', 'start'])[0][2:9],
                         [row['name'], '--kind', 'codex', '--pane', 'wT:p9', '--timeout', '90000'])
        self.assertEqual(self.start_tail(), ['-m', 'gpt-6.1-sol', '-c', 'model_reasoning_effort="xhigh"',
                                             '-c', 'projects={"%s"={trust_level="trusted"}}' % self.repo,
                                             '-s', 'workspace-write', '-a', 'never'])
        self.assertLessEqual(row['started_at'], row['at'])
        self.assertEqual(self.rows(), [row])

    def test_a_builder_gets_its_own_worktree_and_branch(self):
        r = self.herd(self.answers(), 'launch', 'build', '--builder', '--base', 'HEAD')
        self.assertEqual(r.returncode, 0, r.stderr)
        row = json.loads(r.stdout)
        worktree = self.repo / '.claude' / 'worktrees' / row['name']
        branch = 'feat/%s-%s' % (row['name'], datetime.date.today().strftime('%Y%m%d'))
        self.assertEqual((row['mode'], row['cwd'], row['worktree'], row['branch']),
                         ('builder', str(worktree), str(worktree), branch))
        self.assertTrue(worktree.is_dir())
        head = subprocess.run(['git', '-C', str(worktree), 'branch', '--show-current'], capture_output=True,
                              text=True).stdout.strip()
        self.assertEqual(head, branch)
        self.assertEqual(self.start_tail()[-1], '--dangerously-bypass-approvals-and-sandbox')
        self.assertIn('projects={"%s"={trust_level="trusted"}}' % worktree, self.start_tail())
        self.assertEqual(self.calls(['pane', 'split'])[0][5:7], ['--cwd', str(worktree)])

    def test_a_builder_needs_a_base(self):
        r = self.herd(self.answers(), 'launch', 'build', '--builder')
        self.assertEqual(r.returncode, 1)
        self.assertIn('--base', r.stderr)

    def test_a_banner_without_the_effort_undoes_the_launch(self):
        r = self.herd(self.answers(**{'pane read': [{'out': '  GPT-6.1-Sol high · ~/x/repo\n'}]}),
                      'launch', 'build', '--builder', '--base', 'HEAD', env={'RELAYLIB_BANNER_SECONDS': '0'})
        self.assertEqual(r.returncode, 1)
        self.assertIn("banner does not show effort 'xhigh'", r.stderr)
        self.assertEqual(self.calls(['pane', 'close']), [['pane', 'close', 'wT:p9']])
        self.assertEqual(self.rows(), [])
        self.assertEqual(os.listdir(self.repo / '.claude' / 'worktrees'), [])
        branches = subprocess.run(['git', '-C', str(self.repo), 'branch', '--list', 'feat/*'], capture_output=True,
                                  text=True).stdout
        self.assertEqual(branches, '')

    def test_a_claude_worker_gets_the_leads_model_and_an_assigned_session(self):
        r = self.herd(self.answers(**{'pane read': [{'out': ' Opus 5.5 with high effort · Claude Max\n'}],
                                      'agent get': [agent('idle', 'wT:p9', kind='claude')]}),
                      'launch', 'review', '--kind', 'claude', '--builder', '--base', 'HEAD')
        self.assertEqual(r.returncode, 0, r.stderr)
        row = json.loads(r.stdout)
        tail = self.start_tail()
        self.assertEqual(tail[:5], ['--model', 'claude-opus-5-5', '--effort', 'high', '--dangerously-skip-permissions'])
        self.assertEqual(row['session_id'], tail[tail.index('--session-id') + 1])
        self.assertEqual((row['model'], row['effort']), ('claude-opus-5-5', 'high'))
        self.assertTrue(row['name'].startswith('review-high-'))

    def test_claudes_trust_dialog_for_the_workers_folder_is_answered_yes(self):
        # A short pane: the bottom buffer holds only the options, not the header or the folder.
        dialog = ' ❯ 1. No, exit\n   2. Yes, I trust this folder\n Enter to confirm · Esc to cancel\n'
        chosen = '   1. No, exit\n ❯ 2. Yes, I trust this folder\n Enter to confirm · Esc to cancel\n'
        r = self.herd(self.answers(**{
            'agent start': [NOT_READY], 'pane read': [{'out': ''}, {'out': dialog}, {'out': ''}, {'out': chosen},
                                                      {'out': ' Opus 5.5 with high effort\n'}],
            'agent get': [agent('blocked', 'wT:p9', kind='claude'), agent('blocked', 'wT:p9', kind='claude'),
                          agent('idle', 'wT:p9', kind='claude')]}),
            'launch', 'review', '--kind', 'claude', '--builder', '--base', 'HEAD')
        self.assertEqual(r.returncode, 0, r.stderr)
        name = json.loads(r.stdout)['name']
        self.assertEqual(len(self.calls(['agent', 'start'])), 1)
        self.assertEqual([c[3] for c in self.calls(['agent', 'send-keys'])], ['down', 'enter'])
        self.assertEqual(self.calls(['agent', 'rename']), [['agent', 'rename', 'wT:p9', name]])
        self.assertEqual(self.calls(['agent', 'wait']), [])

    def test_a_banner_drawn_late_is_read_again(self):
        r = self.herd(self.answers(**{'pane read': [{'out': '\n\n'}, {'out': ''}, CODEX_BANNER]}), 'launch', 'review')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(self.calls(['pane', 'read'])), 3)

    def test_a_dialog_that_does_not_clear_fails_within_the_bound(self):
        dialog = ' Quick safety check\n %s\n ❯ 1. No, exit\n   2. Yes, I trust this folder\n' % self.repo
        chosen = ' Quick safety check\n %s\n   1. No, exit\n ❯ 2. Yes, I trust this folder\n' % self.repo
        r = self.herd(self.answers(**{'agent start': [NOT_READY], 'pane read': [{'out': dialog}, {'out': ''},
                                                                                 {'out': chosen}, {'out': ''}],
                                      'agent get': [agent('blocked', 'wT:p9', kind='claude')]}),
                      'launch', 'review', '--kind', 'claude', '--builder', '--base', 'HEAD', env={'HERD_SETTLE_SECONDS': '2'})
        self.assertEqual(r.returncode, 1)
        self.assertIn('still blocked 2 s after its startup dialog', r.stderr)
        self.assertEqual(self.calls(['pane', 'close']), [['pane', 'close', 'wT:p9']])

    def test_another_startup_block_fails_without_answering_it(self):
        r = self.herd(self.answers(**{'agent start': [NOT_READY],
                                      'pane read': [{'out': ' Allow tool use? (y/n)\n'}, {'out': ''}]}),
                      'launch', 'review', '--kind', 'claude', '--builder', '--base', 'HEAD')
        self.assertEqual(r.returncode, 1)
        self.assertIn('other than the trust dialog', r.stderr)
        self.assertEqual(self.calls(['agent', 'send-keys']), [])
        self.assertEqual(self.calls(['pane', 'close']), [['pane', 'close', 'wT:p9']])

    def test_a_claude_worker_cannot_be_read_only(self):
        # Claude runs with --dangerously-skip-permissions: "read-only" would be a label nothing enforces.
        for extra in ([], ['--readonly']):
            with self.subTest(extra=extra):
                r = self.herd(self.answers(), 'launch', 'review', '--kind', 'claude', *extra)
                self.assertEqual(r.returncode, 1)
                self.assertIn('a Claude worker has no sandbox, so it cannot be read-only', r.stderr)
                self.assertEqual(self.calls(['pane', 'split']), [])
                self.assertEqual(self.rows(), [])

    def test_a_name_taken_meanwhile_is_drawn_again(self):
        r = self.herd(self.answers(**{'agent start': [TAKEN, ok()]}), 'launch', 'review')
        self.assertEqual(r.returncode, 0, r.stderr)
        first, second = [c[2] for c in self.calls(['agent', 'start'])]
        self.assertNotEqual(first, second)
        self.assertEqual(json.loads(r.stdout)['name'], second)

    def test_an_existing_pane_must_be_a_shell_in_the_workers_folder(self):
        for entry, code, needle in ((pane_entry('wT:p5', self.repo, kind=None), 0, ''),
                                    (pane_entry('wT:p5', self.repo), 1, 'hosts codex'),
                                    (pane_entry('wT:p5', self.root, kind=None), 1, 'cd there first')):
            with self.subTest(entry=entry):
                panes, _ = listing(entry)
                r = self.herd(self.answers(**{'pane list': [panes]}), 'launch', 'review', '--pane', 'wT:p5')
                self.assertEqual(r.returncode, code, r.stderr)
                self.assertIn(needle, r.stderr)
                self.assertEqual(self.calls(['pane', 'split']), [])
                self.assertEqual(self.calls(['pane', 'close']), [])   # never close a pane it did not create

    def test_a_role_herdr_cannot_carry_starts_nothing(self):
        r = self.herd(self.answers(), 'launch', 'Review')
        self.assertEqual(r.returncode, 1)
        self.assertIn('must match', r.stderr)
        self.assertEqual(self.calls(['agent', 'start']), [])

    def test_outside_herdr_starts_nothing(self):
        r = self.herd(self.answers(), 'launch', 'review', drop=('HERDR_ENV',))
        self.assertEqual(r.returncode, 1)
        self.assertIn('not inside herdr', r.stderr)

    def test_a_damaged_record_starts_nothing(self):
        self.pdir.mkdir(parents=True, exist_ok=True)
        (self.pdir / 'herd.jsonl').write_text('{torn\n')
        r = self.herd(self.answers(), 'launch', 'review')
        self.assertEqual(r.returncode, 2)
        self.assertIn('line 1 does not parse', r.stderr)
        self.assertEqual(self.calls(['pane', 'split']), [])


if __name__ == '__main__':
    unittest.main()

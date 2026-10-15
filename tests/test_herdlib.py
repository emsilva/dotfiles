"""The herd record: append and read under a lock, refusal of a damaged record, replay, names and matching."""
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest

from handoff_fixtures import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import herdlib  # noqa: E402


def launch_row(lid, name, pane, session=None, kind='codex', cwd='/x/repo', at='2026-10-14T10:00:00Z'):
    return {'at': at, 'type': 'launch', 'launch_id': lid, 'name': name, 'pane_id': pane, 'kind': kind,
            'model': 'gpt-6.1-sol', 'effort': 'xhigh', 'mode': 'readonly', 'cwd': cwd, 'worktree': None,
            'branch': None, 'session_id': session, 'lead_session': 'L1', 'adopted': False, 'started_at': at}


def dispatch_row(lid, seq, session=None, reset=None, sent_at='2026-10-14T10:05:00Z'):
    return {'at': sent_at, 'type': 'dispatch', 'launch_id': lid, 'seq': seq, 'brief': '/x/b.md',
            'brief_sha256': 'ab' * 32, 'deliverable': '/x/r.md', 'blocked': '/x/BLOCKED.md', 'reset': reset,
            'sent_at': sent_at, 'session_id': session}


def pane(pid, session=None, name=None, cwd='/x/repo', agent='codex', status='idle'):
    p = {'pane_id': pid, 'tab_id': 'wT:t1', 'cwd': cwd, 'name': name}
    if agent:
        p.update(agent=agent, agent_status=status)
    if session:
        p['agent_session'] = {'value': session}
    return p


class RecordTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.pdir = Path(self.tmp.name) / 'proj'

    def tearDown(self):
        self.tmp.cleanup()

    def test_rows_round_trip_and_the_record_is_private(self):
        herdlib.append(self.pdir, launch_row('a' * 32, 'w-xhigh-aaaa', 'wT:p2'))
        herdlib.append(self.pdir, dispatch_row('a' * 32, 1))
        rows = herdlib.read(self.pdir)
        self.assertEqual([r['type'] for r in rows], ['launch', 'dispatch'])
        self.assertEqual(stat.S_IMODE(os.stat(self.pdir / 'herd.jsonl').st_mode), 0o600)

    def test_no_record_is_an_empty_herd(self):
        self.assertEqual(herdlib.read(self.pdir), [])

    def test_a_row_missing_a_field_is_never_written(self):
        row = launch_row('a' * 32, 'n', 'wT:p2')
        del row['cwd']
        with self.assertRaisesRegex(herdlib.RecordError, 'lacks cwd'):
            herdlib.append(self.pdir, row)
        self.assertFalse((self.pdir / 'herd.jsonl').exists())

    def test_a_damaged_line_stops_the_reader_with_its_number(self):
        herdlib.append(self.pdir, launch_row('a' * 32, 'n', 'wT:p2'))
        with open(self.pdir / 'herd.jsonl', 'a') as fh:
            fh.write('{"at": "x", "type": "dispa\n')
        with self.assertRaisesRegex(herdlib.RecordError, 'line 2 does not parse'):
            herdlib.read(self.pdir)

    def test_a_row_of_unknown_type_or_without_a_launch_is_refused(self):
        self.pdir.mkdir()
        (self.pdir / 'herd.jsonl').write_text(json.dumps({'at': 'x', 'type': 'wave', 'launch_id': 'l'}) + '\n')
        with self.assertRaisesRegex(herdlib.RecordError, "line 1 has unknown type 'wave'"):
            herdlib.read(self.pdir)
        with self.assertRaisesRegex(herdlib.RecordError, 'has no launch row'):
            herdlib.replay([dispatch_row('b' * 32, 1)])

    def test_concurrent_appends_stay_whole_lines(self):
        code = ('import sys; sys.path.insert(0, %r); import herdlib\n'
                'for i in range(40):\n'
                '    herdlib.append(%r, {"type": "launch", "launch_id": "%%s%%04d" %% (sys.argv[1], i), "name": "n",'
                ' "pane_id": "p", "kind": "codex", "model": "m", "effort": "e", "mode": "readonly",'
                ' "cwd": "/" + "x" * 3000, "worktree": None, "branch": None, "session_id": None,'
                ' "lead_session": "L", "adopted": False, "started_at": None})\n') % (str(SCRIPTS), str(self.pdir))
        procs = [subprocess.Popen([sys.executable, '-I', '-B', '-c', code, 'w%d' % i]) for i in range(4)]
        for p in procs:
            self.assertEqual(p.wait(timeout=60), 0)
        self.assertEqual(len(herdlib.read(self.pdir)), 160)


class ReplayTests(unittest.TestCase):
    def test_sessions_follow_read_backs_and_resets(self):
        a = 'a' * 32
        rows = [launch_row(a, 'w-xhigh-aaaa', 'wT:p2'), dispatch_row(a, 1, session='S1'),
                dispatch_row(a, 2), {'at': 'x', 'type': 'reported', 'launch_id': a, 'seq': 1, 'event': 'deliverable'}]
        launch = herdlib.replay(rows)[a]
        self.assertEqual((launch['session_id'], len(launch['dispatches']), launch['reported']),
                         ('S1', 2, {1: 'deliverable'}))
        launch = herdlib.replay(rows + [dispatch_row(a, 3, reset='new')])[a]
        self.assertIsNone(launch['session_id'])
        self.assertEqual(herdlib.latest(launch)['seq'], 3)

    def test_a_new_launch_on_a_held_pane_closes_the_old_one(self):
        a, b = 'a' * 32, 'b' * 32
        launches = herdlib.replay([launch_row(a, 'one-xhigh-aaaa', 'wT:p2'), launch_row(b, 'two-xhigh-bbbb', 'wT:p2')])
        self.assertEqual(launches[a]['closed'], 'pane wT:p2 reused by two-xhigh-bbbb')
        self.assertIsNone(launches[b]['closed'])
        self.assertEqual([x['name'] for x in herdlib.open_launches(launches)], ['two-xhigh-bbbb'])

    def test_a_close_row_closes(self):
        a = 'a' * 32
        launches = herdlib.replay([launch_row(a, 'n', 'wT:p2'),
                                   {'at': 'x', 'type': 'close', 'launch_id': a, 'reason': ''}])
        self.assertEqual(launches[a]['closed'], 'closed')
        with self.assertRaisesRegex(herdlib.RecordError, "no open launch is called 'n'"):
            herdlib.by_name(launches, 'n')


class NameTests(unittest.TestCase):
    def test_names_are_role_effort_and_four_unused_hex(self):
        draws = iter(['aaaa' + '0' * 28, 'bbbb' + '0' * 28])
        rows = [launch_row('aaaa' + '1' * 28, 'x', 'p')]
        lid, name = herdlib.new_name('review', 'xhigh', rows, draw=lambda: next(draws))
        self.assertEqual((lid[:4], name), ('bbbb', 'review-xhigh-bbbb'))

    def test_a_taken_name_draws_again(self):
        draws = iter(['aaaa' + '0' * 28, 'cccc' + '0' * 28])
        _, name = herdlib.new_name('r', 'high', [], taken={'r-high-aaaa'}, draw=lambda: next(draws))
        self.assertEqual(name, 'r-high-cccc')

    def test_a_role_herdr_cannot_carry_is_refused_not_cut(self):
        with self.assertRaisesRegex(ValueError, 'shorter role'):
            herdlib.new_name('a' * 22, 'xhigh', [])
        self.assertEqual(len(herdlib.new_name('a' * 21, 'xhigh', [])[1]), 32)
        for role in ('Review', '9x', 'a_b', ''):
            with self.assertRaisesRegex(ValueError, 'must match'):
                herdlib.new_name(role, 'xhigh', [])

    def test_worker_looking_names(self):
        for name in ('r6-size-xhigh', 'review-xhigh-ab12', 'scan-high', 'x-max-0f0f'):
            self.assertTrue(herdlib.looks_like_worker(name), name)
        for name in ('lead-claude', 'lead-claude-next', 'xhigh', None, 'review-xhigh-AB12', 'thigh'):
            self.assertFalse(herdlib.looks_like_worker(name), name)


class MatchTests(unittest.TestCase):
    def setUp(self):
        self.a, self.b = 'a' * 32, 'b' * 32
        self.rows = [launch_row(self.a, 'one-xhigh-aaaa', 'wT:p2', session='S1'),
                     launch_row(self.b, 'two-xhigh-bbbb', 'wT:p3')]

    def match(self, panes, rows=None):
        pairs, free, lost = herdlib.match(herdlib.replay(rows or self.rows), panes)
        return {l['name']: p['pane_id'] for l, p in pairs}, [p['pane_id'] for p in free], [l['name'] for l in lost]

    def test_session_beats_pane_beats_name(self):
        # After a restore: pane ids renumbered; one's session moved to wT:p7, wT:p2 now hosts another agent.
        got = self.match([pane('wT:p2', session='OTHER'), pane('wT:p7', session='S1'), pane('wT:p3')])
        self.assertEqual(got, ({'one-xhigh-aaaa': 'wT:p7', 'two-xhigh-bbbb': 'wT:p3'}, ['wT:p2'], []))
        got = self.match([pane('wT:p9', name='two-xhigh-bbbb'), pane('wT:p2', session='S1')])
        self.assertEqual(got, ({'one-xhigh-aaaa': 'wT:p2', 'two-xhigh-bbbb': 'wT:p9'}, [], []))

    def test_a_different_known_session_never_matches_by_pane_or_name(self):
        got = self.match([pane('wT:p2', session='S9', name='one-xhigh-aaaa'), pane('wT:p3')])
        self.assertEqual(got, ({'two-xhigh-bbbb': 'wT:p3'}, ['wT:p2'], ['one-xhigh-aaaa']))

    def test_a_shell_pane_matches_nothing(self):
        got = self.match([pane('wT:p2', agent=None), pane('wT:p3')])
        self.assertEqual(got, ({'two-xhigh-bbbb': 'wT:p3'}, ['wT:p2'], ['one-xhigh-aaaa']))


class HerdTests(unittest.TestCase):
    def test_root_scope_includes_root_and_descendants(self):
        for cwd in ('/', '/x', '/x/repo'):
            with self.subTest(cwd=cwd):
                self.assertTrue(herdlib.in_scope(cwd, ['/']))
        self.assertFalse(herdlib.in_scope('/other', ['/x']))

    def test_scope_self_and_lost(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(os.path.realpath(tmp)) / 'repo'
            subprocess.run(['git', 'init', '-q', str(repo)], check=True)
            pdir = Path(tmp) / 'proj'
            herdlib.append(pdir, launch_row('a' * 32, 'one-xhigh-aaaa', 'wT:p2', cwd='/elsewhere/wt'))
            herdlib.append(pdir, launch_row('b' * 32, 'two-xhigh-bbbb', 'wT:p5', cwd=str(repo)))
            panes = [pane('wT:p1', cwd=str(repo), agent='claude'),            # the lead itself
                     pane('wT:p2', cwd='/elsewhere/wt'),                       # a worker outside the repo
                     pane('wT:p3', cwd=str(repo / 'sub'), name='scan-high'),    # launched by hand
                     pane('wT:p4', cwd='/elsewhere/wt/deeper', agent=None),    # a shell under a worker's cwd
                     pane('wT:p6', cwd='/unrelated')]
            got = herdlib.herd(pdir, str(repo), extra_roots=(), self_pane='wT:p1', panes=panes)
            self.assertEqual([(l['name'], p['pane_id']) for l, p in got['workers']], [('one-xhigh-aaaa', 'wT:p2')])
            self.assertEqual([p['pane_id'] for p in got['unclassified']], ['wT:p3', 'wT:p4'])
            self.assertEqual([l['name'] for l in got['lost']], ['two-xhigh-bbbb'])
            got = herdlib.herd(pdir, str(repo), extra_roots=('/unrelated',), self_pane='wT:p1', panes=panes)
            self.assertEqual([p['pane_id'] for p in got['unclassified']], ['wT:p3', 'wT:p6', 'wT:p4'])


if __name__ == '__main__':
    unittest.main()

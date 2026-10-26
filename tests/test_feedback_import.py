"""feedback-import.py: merge a project's scratch rows into the Mac store, idempotently."""
import datetime
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from handoff_fixtures import SCRIPTS, SOURCE

SCRIPT = SCRIPTS / 'feedback-import.py'
FEEDBACK = SOURCE / 'private_dot_claude/skills/session-handoff/references/feedback.md'


def gap(successor, missing, **extra):
    row = {'successor_session': successor, 'missing': missing, 'date': '2026-10-26', 'project': 'innovate',
           'fixed_by': None}
    row.update(extra)
    return json.dumps(row, ensure_ascii=False)


def run(project, dest, home):
    env = dict(os.environ, HOME=str(home))
    return subprocess.run(['python3', '-I', '-B', str(SCRIPT), str(project), '--dest', str(dest)],
                          capture_output=True, text=True, env=env)


class FeedbackImportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.project = self.root / 'proj'
        self.src = self.project / '.scratch' / 'handoff-feedback'
        self.proposals = self.src / 'proposals'
        self.proposals.mkdir(parents=True)
        self.dest = self.root / 'mac'
        self.home = self.root / 'home'
        self.home.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def write_gaps(self, *rows, dest=False):
        path = (self.dest if dest else self.src) / 'gaps.jsonl'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(''.join(row + '\n' for row in rows))
        return path

    def test_feedback_md_names_the_import_before_the_fire_step(self):
        text = FEEDBACK.read_text()
        before, _, _ = text.partition('## Fire')
        self.assertIn('scripts/feedback-import.py', before)
        self.assertIn('On the Mac, before the Fire step', before)
        self.assertIn('.scratch/handoff-feedback/', before)

    def test_gaps_are_deduped_on_successor_and_missing_and_a_rerun_is_a_no_op(self):
        kept = gap('s-old', 'already here', cost='1')
        # Same key, different key order and a different other field: still a duplicate.
        dup = json.dumps({'missing': 'already here', 'cost': '9', 'successor_session': 's-old'})
        new = gap('s-new', 'a codespace row')
        nulls = gap(None, 'no successor')
        self.write_gaps(kept, dest=True)
        self.write_gaps(dup, new, nulls, gap(None, 'no successor'))
        r = run(self.project, self.dest, self.home)
        self.assertEqual(r.returncode, 0, r.stderr)
        lines = (self.dest / 'gaps.jsonl').read_text().splitlines()
        self.assertEqual(lines[0], kept)
        self.assertEqual(json.loads(lines[1])['missing'], 'a codespace row')
        self.assertEqual(json.loads(lines[2])['successor_session'], None)
        self.assertEqual(len(lines), 3)
        again = run(self.project, self.dest, self.home)
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertEqual((self.dest / 'gaps.jsonl').read_text().splitlines(), lines)
        self.assertEqual(again.stdout, '')

    def test_a_new_proposal_is_copied_and_printed_as_a_todo_line_a_differing_one_is_not(self):
        name = '2026-10-26-next-step.md'
        body = '# Proposal: quote the checker\n\nbody\n'
        (self.proposals / name).write_text(body)
        other = '2026-10-25-old.md'
        (self.proposals / other).write_text('# Proposal: an old one\n')
        (self.dest / 'proposals').mkdir(parents=True)
        (self.dest / 'proposals' / other).write_text('# Proposal: an old one, edited on the Mac\n')
        same = '2026-10-24-same.md'
        (self.proposals / same).write_text('# already\n')
        (self.dest / 'proposals' / same).write_text('# already\n')
        r = run(self.project, self.dest, self.home)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.dest / 'proposals' / name).read_text(), body)
        self.assertEqual((self.dest / 'proposals' / other).read_text(),
                         '# Proposal: an old one, edited on the Mac\n')
        self.assertIn(other, r.stderr)
        self.assertNotIn('not overwritten', r.stdout)
        lines = r.stdout.splitlines()
        self.assertEqual(len(lines), 1)
        line = lines[0]
        self.assertTrue(line.startswith('- [ ] Review session-handoff proposal: quote the checker (`'), line)
        self.assertIn(name, line)
        self.assertIn('#session-handoff %s' % datetime.date.today().isoformat(), line)
        self.assertTrue(line.endswith('  '), repr(line))
        self.assertNotIn(other, line)
        self.assertNotIn(same, line)
        self.assertFalse((self.home / 'TODO.md').exists())
        again = run(self.project, self.dest, self.home)
        self.assertEqual(again.stdout, '')
        self.assertEqual((self.dest / 'proposals' / name).read_text(), body)

    def test_a_bad_gap_line_writes_nothing(self):
        self.write_gaps('{"missing": "ok", "successor_session": "s"}', '{torn')
        before = list(self.dest.rglob('*'))
        r = run(self.project, self.dest, self.home)
        self.assertEqual(r.returncode, 1)
        self.assertIn('gaps.jsonl', r.stderr)
        self.assertEqual(list(self.dest.rglob('*')), before)
        self.assertEqual(r.stdout, '')

    def test_a_missing_scratch_dir_is_a_no_op(self):
        empty = self.root / 'empty-project'
        empty.mkdir()
        r = run(empty, self.dest, self.home)
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, '', ''))
        self.assertFalse(self.dest.exists())


if __name__ == '__main__':
    unittest.main()

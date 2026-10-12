import json
import mmap
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import unittest

from handoff_fixtures import SCRIPTS

MC = SCRIPTS / 'memory-check.py'


def run_mc(mem, *args):
    r = subprocess.run(['python3', '-I', str(MC), str(mem), '--json', *args], capture_output=True, text=True)
    return r.returncode, json.loads(r.stdout)


def memory(mem, name, desc='a fact', mtime=None):
    path = Path(mem) / (name + '.md')
    path.write_text('---\nname: %s\ndescription: %s\nmetadata:\n  type: project\n---\n\nbody\n' % (name, desc))
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


class MemoryCheckTests(unittest.TestCase):
    def test_line_cap_loses_the_tail(self):
        with tempfile.TemporaryDirectory() as mem:
            Path(mem, 'MEMORY.md').write_text(''.join('- line %d\n' % n for n in range(210)))
            code, rep = run_mc(mem)
            self.assertEqual(rep['index']['lost_lines'], 10)
            self.assertEqual(code, 1)

    def test_unit_cap_counts_utf16_and_cuts_whole_lines(self):
        with tempfile.TemporaryDirectory() as mem:
            # 24 lines of 999 'x' + one line of 999 emoji (2 UTF-16 units each): 25,998 units,
            # but only 24,999 code points, so a code-point count would wrongly keep every line.
            lines = ['x' * 999 for _ in range(24)] + ['\U0001F600' * 999]
            Path(mem, 'MEMORY.md').write_text('\n'.join(lines) + '\n')
            code, rep = run_mc(mem)
            self.assertEqual(rep['index']['units'], 25998)
            self.assertEqual(rep['index']['lost_lines'], 1)
            self.assertEqual(code, 1)

    def test_fix_indexes_recent_orphans_and_drops_only_fully_dead_lines(self):
        with tempfile.TemporaryDirectory() as mem:
            old = time.time() - 86400
            memory(mem, 'kept', mtime=old)
            memory(mem, 'old-orphan', mtime=old)
            memory(mem, 'new-orphan', desc='written this session')
            Path(mem, 'MEMORY.md').write_text('- [Kept](kept.md) — stays\n- [Gone](gone.md) — deleted file\n'
                                              '- [Mixed](kept.md) and [x](missing.md)\n')
            since = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(time.time() - 3600))
            code, rep = run_mc(mem, '--since', since, '--fix')
            index = Path(mem, 'MEMORY.md').read_text()
            self.assertIn('- [new-orphan](new-orphan.md) — written this session', index)
            self.assertNotIn('gone.md', index)
            self.assertIn('missing.md', index)
            self.assertEqual(rep['fixed']['removed'], ['- [Gone](gone.md) — deleted file'])
            self.assertEqual(rep['unindexed_older'], ['old-orphan.md'])
            self.assertEqual(rep['unindexed_recent'], [])
            self.assertEqual(code, 1)

    def test_clean_dir_exits_zero(self):
        with tempfile.TemporaryDirectory() as mem:
            memory(mem, 'kept')
            Path(mem, 'MEMORY.md').write_text('- [kept](kept.md) — x\n')
            code, rep = run_mc(mem, '--since', '2026-01-01T00:00:00Z')
            self.assertEqual((code, rep['debt']), (0, False))

    def test_fix_creates_a_missing_index(self):
        with tempfile.TemporaryDirectory() as mem:
            memory(mem, 'fresh')
            code, rep = run_mc(mem, '--since', '2026-01-01T00:00:00Z', '--fix')
            self.assertTrue(rep['index_exists'])
            self.assertIn('(fresh.md)', Path(mem, 'MEMORY.md').read_text())
            self.assertEqual(code, 0)

    def test_not_a_directory_exits_2(self):
        r = subprocess.run(['python3', '-I', str(MC), '/nonexistent/memory'], capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)

    def test_loader_constants_match_the_installed_claude_code(self):
        exe = shutil.which('claude')
        self.assertIsNotNone(exe, 'claude is not on PATH: the loader caps cannot be checked')
        with open(os.path.realpath(exe), 'rb') as fh, mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ) as data:
            m = re.search(rb'var [\w$]+="MEMORY\.md",[\w$]+=(\d+),[\w$]+=(\d+)', data)
            # The match borrows the map's buffer: read its groups before the map closes.
            caps = m and (m.group(1).decode(), m.group(2).decode())
        self.assertIsNotNone(m, 'MEMORY.md loader constants not found in %s: re-derive the caps' % exe)
        self.assertIn('CAP_LINES, CAP_UNITS = %s, %s' % caps, MC.read_text())


if __name__ == '__main__':
    unittest.main()

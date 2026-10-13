import contextlib
import importlib.util
import io
import json
import mmap
import os
from pathlib import Path
import re
import resource
import shutil
import signal
import subprocess
import tempfile
import time
import unittest

from handoff_fixtures import SCRIPTS

MC = SCRIPTS / 'memory-check.py'
# Without --since the CLI looks up $CLAUDE_CODE_SESSION_ID's transcript under --projects
# (default ~/.claude/projects): tests give it no session and a projects dir with no transcripts.
ENV = {k: v for k, v in os.environ.items() if k != 'CLAUDE_CODE_SESSION_ID'}
SINCE = '2026-01-01T00:00:00Z'


def mc(mem, *args, **kwargs):
    return subprocess.run(['python3', '-I', str(MC), str(mem), '--projects', str(Path(mem, 'no-projects')), *args],
                          capture_output=True, text=True, env=ENV, **kwargs)


def run_mc(mem, *args):
    r = mc(mem, '--json', *args)
    return r.returncode, json.loads(r.stdout)


def index_text(mem):
    path = Path(mem, 'MEMORY.md')
    return path.read_text() if path.exists() else ''


def load_mc():
    """memory-check.py as a module (its name has a dash), for tests that patch its internals."""
    spec = importlib.util.spec_from_file_location('memory_check', MC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


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
        r = mc('/nonexistent/memory')
        self.assertEqual(r.returncode, 2)

    def test_invalid_since_exits_2_with_one_line(self):
        with tempfile.TemporaryDirectory() as mem:
            r = mc(mem, '--since', 'yesterday')
            self.assertEqual((r.returncode, r.stdout), (2, ''))
            self.assertTrue(r.stderr.startswith('memory-check: invalid --since '), r.stderr)
            self.assertEqual(len(r.stderr.splitlines()), 1, r.stderr)

    def test_url_only_lines_are_kept_and_not_reported(self):
        with tempfile.TemporaryDirectory() as mem:
            memory(mem, 'kept')
            index = '- [kept](kept.md) — x\n- [Docs](https://example.com/x) — external\n- [Mail](mailto:a@example.com)\n'
            Path(mem, 'MEMORY.md').write_text(index)
            code, rep = run_mc(mem, '--since', '2026-01-01T00:00:00Z')
            self.assertEqual((code, rep['dead_links']), (0, []))
            code, rep = run_mc(mem, '--since', '2026-01-01T00:00:00Z', '--fix')
            self.assertEqual(rep['fixed']['removed'], [])
            self.assertEqual(Path(mem, 'MEMORY.md').read_text(), index)
            self.assertEqual(code, 0)

    def test_anchor_links_count_for_the_file_they_name(self):
        with tempfile.TemporaryDirectory() as mem:
            memory(mem, 'kept')
            Path(mem, 'MEMORY.md').write_text('- [x](kept.md#section) — x\n- [y](missing.md#part) — y\n')
            code, rep = run_mc(mem, '--since', '2026-01-01T00:00:00Z')
            self.assertEqual((rep['unindexed_recent'], rep['unindexed_older']), ([], []))
            self.assertEqual(rep['dead_links'], [{'line': 2, 'targets': ['missing.md'], 'removable': True}])
            self.assertEqual(code, 1)

    def test_a_dead_file_link_beside_a_url_is_removable(self):
        # Only links to memory files are checkable; a URL neither keeps a line alive nor makes it dead.
        with tempfile.TemporaryDirectory() as mem:
            memory(mem, 'kept')
            line = '- [Gone](gone.md) — see [docs](https://example.com/x)'
            Path(mem, 'MEMORY.md').write_text('- [kept](kept.md) — x\n%s\n' % line)
            code, rep = run_mc(mem, '--since', '2026-01-01T00:00:00Z')
            self.assertEqual(rep['dead_links'], [{'line': 2, 'targets': ['gone.md'], 'removable': True}])
            code, rep = run_mc(mem, '--since', '2026-01-01T00:00:00Z', '--fix')
            self.assertEqual(rep['fixed']['removed'], [line])
            self.assertEqual(code, 0)

    def test_only_real_memory_pointers_are_checked(self):
        # Each line below is live: --fix must keep it, and none of it is a dead link.
        with tempfile.TemporaryDirectory() as mem:
            memory(mem, 'kept')
            memory(mem, 'my note')
            index = ('- [Global rules](~/.claude/CLAUDE.md) - live note\n'
                     '- Link syntax: write `[text](path)` in notes\n'
                     '- [K2](<kept.md>) - an angle-bracket pointer\n'
                     '- [Sp](my%20note.md) - an escaped space\n'
                     '- [Abs](/etc/notes.md) - an absolute path\n'
                     '- [Up](../other/notes.md) - outside the memory dir\n'
                     '- Pointer example: `[x](gone.md)` in a code span\n'
                     '- [Log](build.log) - not a memory file\n')
            Path(mem, 'MEMORY.md').write_text(index)
            code, rep = run_mc(mem, '--since', SINCE)
            self.assertEqual((rep['dead_links'], rep['unindexed_recent'], rep['unindexed_older']), ([], [], []))
            self.assertEqual(code, 0)
            code, rep = run_mc(mem, '--since', SINCE, '--fix')
            self.assertEqual(rep['fixed'], {'added': [], 'removed': []})
            self.assertEqual((index_text(mem), code), (index, 0))

    def test_a_relative_memory_dir_reads_its_pointers(self):
        with tempfile.TemporaryDirectory() as mem:
            memory(mem, 'kept')
            Path(mem, 'MEMORY.md').write_text('- [kept](kept.md) — x\n')
            r = subprocess.run(['python3', '-I', str(MC), '.', '--json', '--since', SINCE], cwd=mem,
                               capture_output=True, text=True, env=ENV)
            self.assertEqual((r.returncode, json.loads(r.stdout)['unindexed_recent']), (0, []))

    def test_fix_twice_on_a_name_with_a_space_leaves_one_pointer(self):
        with tempfile.TemporaryDirectory() as mem:
            memory(mem, 'my note')
            codes = [run_mc(mem, '--since', SINCE, '--fix')[0] for _ in range(2)]
            self.assertEqual(index_text(mem), '- [my note](my note.md) — a fact\n')
            self.assertEqual(codes, [0, 0])

    def test_fix_never_writes_a_pointer_it_cannot_read_back(self):
        # A pointer the check cannot parse back would be added again on every run.
        with tempfile.TemporaryDirectory() as mem:
            memory(mem, 'x(1)')
            memory(mem, 'a#b')
            for _ in range(2):
                code, rep = run_mc(mem, '--since', SINCE, '--fix')
            self.assertEqual(index_text(mem), '')
            self.assertEqual((rep['fixed']['added'], rep['unindexed_recent'], code), ([], ['a#b.md', 'x(1).md'], 1))

    def test_fix_edits_the_text_it_checked(self):
        # Herd workers share the memory dir: a line written after the check's read must not
        # shift which line the fix drops.
        with tempfile.TemporaryDirectory() as mem:
            memory(mem, 'kept')
            Path(mem, 'MEMORY.md').write_text('- [Kept](kept.md) — stays\n- [Gone](gone.md) — deleted file\n')
            mod = load_mc()
            real, reads = mod.read_index, []

            def read_then_race(path):
                out = real(path)
                if not reads:  # another worker prepends a line right after the first read
                    Path(mem, 'MEMORY.md').write_text('- [Kept](kept.md) — another worker\n' + out[0])
                reads.append(path)
                return out

            mod.read_index = read_then_race
            with contextlib.redirect_stdout(io.StringIO()) as out:
                mod.main([mem, '--json', '--since', SINCE, '--fix', '--projects', str(Path(mem, 'no-projects'))])
            self.assertEqual(json.loads(out.getvalue())['fixed']['removed'], ['- [Gone](gone.md) — deleted file'])
            self.assertIn('- [Kept](kept.md) — stays\n', index_text(mem))

    def test_a_failed_index_write_leaves_the_old_index(self):
        with tempfile.TemporaryDirectory() as mem:
            memory(mem, 'kept')
            memory(mem, 'new')
            index = '- [kept](kept.md) — x\n- [Gone](gone.md) — deleted file\n'
            Path(mem, 'MEMORY.md').write_text(index)

            def small_files():  # a write past 16 bytes fails (EFBIG), like a full disk mid-write
                signal.signal(signal.SIGXFSZ, signal.SIG_IGN)
                resource.setrlimit(resource.RLIMIT_FSIZE, (16, 16))

            r = mc(mem, '--since', SINCE, '--fix', preexec_fn=small_files)
            self.assertNotEqual(r.returncode, 0)
            self.assertEqual(index_text(mem), index)
            self.assertEqual(sorted(os.listdir(mem)), ['MEMORY.md', 'kept.md', 'new.md'])

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

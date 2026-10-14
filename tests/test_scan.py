"""Prove the publication scan fails on deny-listed content and never on author headers."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1]
SCAN = SOURCE / 'scripts/scan.py'
HOOKS = SOURCE / 'scripts/hooks'
GITLEAKS_STUB = '#!/bin/sh\necho "$@" >> "$GITLEAKS_ARGS"\nexit "${GITLEAKS_RC:-0}"\n'


class ScanTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        (self.bin / 'git').symlink_to(shutil.which('git'))
        (self.bin / 'python3').symlink_to(sys.executable)
        self.denylist = self.root / 'denylist'
        self.denylist.write_text('# fixture\nfixture-codename==>neutral-name\nfixture-host\n')
        self.args = self.root / 'gitleaks-args'
        self.env = {**{k: v for k, v in os.environ.items() if not k.startswith(('DOTFILES_', 'GIT_'))},
                    'PATH': str(self.bin), 'HOME': str(self.root), 'GIT_CONFIG_GLOBAL': os.devnull,
                    'GIT_CONFIG_NOSYSTEM': '1', 'DOTFILES_DENYLIST': str(self.denylist),
                    'GITLEAKS_ARGS': str(self.args)}
        self.repo = self.root / 'repo'
        self.git('init', '-q', '-b', 'main', str(self.repo), cwd=self.root)
        self.gitleaks(0)

    def gitleaks(self, rc):
        stub = self.bin / 'gitleaks'
        stub.write_text(GITLEAKS_STUB)
        stub.chmod(0o755)
        self.env['GITLEAKS_RC'] = str(rc)

    def git(self, *args, cwd=None, email='dev@example.invalid'):
        return subprocess.run(['git', '-c', 'user.name=Dev', '-c', f'user.email={email}', *args],
                              cwd=cwd or self.repo, env=self.env, check=True, capture_output=True, text=True).stdout

    def commit(self, name, text, message='Fixture change', email='dev@example.invalid'):
        (self.repo / name).write_text(text)
        self.git('add', name)
        self.git('commit', '-qm', message, email=email)
        return self.git('rev-parse', 'HEAD').strip()

    def scan(self, *args):
        return subprocess.run([sys.executable, '-I', str(SCAN), '--repo', str(self.repo), *args],
                              env=self.env, capture_output=True, text=True)

    def test_a_term_in_added_content_fails_with_its_location(self):
        sha = self.commit('notes.txt', 'clean line\nmeet the Fixture-Codename team\n')
        r = self.scan('history')
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn(f'{sha[:12]}:notes.txt:2: fixture-codename', r.stdout)

    def test_a_term_in_a_commit_message_fails(self):
        sha = self.commit('notes.txt', 'clean\n', message='Subject\n\nBody naming FIXTURE-HOST')
        r = self.scan('history')
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn(f'{sha[:12]}:<message>:3: fixture-host', r.stdout)

    def test_a_term_only_in_the_author_email_passes(self):
        self.commit('notes.txt', 'clean\n', email='dev@fixture-codename.invalid')
        self.assertIn('fixture-codename', self.git('log', '--format=%ae %ce'))
        r = self.scan('history')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_only_the_left_side_of_a_replacement_is_matched(self):
        self.commit('notes.txt', 'the neutral-name is fine\n')
        r = self.scan('history')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_a_commit_that_removes_a_term_does_not_block_its_own_push(self):
        leaked = self.commit('notes.txt', 'fixture-codename\n')
        scrub = self.commit('notes.txt', 'neutral-name\n', message='Scrub the name')
        self.assertEqual(self.scan('range', f'{leaked}..{scrub}').returncode, 0)
        self.assertEqual(self.scan('range', scrub).returncode, 1)

    def test_a_missing_deny_list_fails(self):
        self.commit('notes.txt', 'clean\n')
        self.denylist.unlink()
        r = self.scan('history')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('Deny-list not found', r.stderr)

    def test_an_empty_deny_list_fails(self):
        self.commit('notes.txt', 'clean\n')
        self.denylist.write_text('# only comments\n\n')
        r = self.scan('history')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('Deny-list is empty', r.stderr)

    def test_missing_gitleaks_fails_unless_explicitly_allowed(self):
        self.commit('notes.txt', 'clean\n')
        (self.bin / 'gitleaks').unlink()
        r = self.scan('history')
        self.assertNotEqual(r.returncode, 0)
        self.assertIn('brew install gitleaks', r.stderr)
        self.env['DOTFILES_SCAN_ALLOW_NO_GITLEAKS'] = '1'
        r = self.scan('history')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('WARNING: gitleaks is not installed', r.stderr)

    def test_gitleaks_runs_on_the_scanned_range_and_its_failure_fails(self):
        first = self.commit('notes.txt', 'clean\n')
        second = self.commit('notes.txt', 'still clean\n')
        self.assertEqual(self.scan('range', f'{first}..{second}').returncode, 0)
        self.assertIn(f'git --no-banner --redact --log-opts={first}..{second} {self.repo}', self.args.read_text())
        self.gitleaks(1)
        r = self.scan('history')
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn('gitleaks reported findings', r.stderr)

    def test_the_tree_scan_reads_tracked_files(self):
        self.commit('clean.txt', 'clean\n')
        self.assertEqual(self.scan('tree').returncode, 0)
        (self.repo / 'clean.txt').write_text('clean\nlocal fixture-host edit\n')
        r = self.scan('tree')
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn('clean.txt:2: fixture-host', r.stdout)
        self.assertEqual(self.scan('tree', 'HEAD').returncode, 0)

    def test_the_pre_push_hook_blocks_a_hit_and_passes_clean_ranges(self):
        remote = self.root / 'remote.git'
        self.git('init', '-q', '--bare', str(remote), cwd=self.root)
        self.git('remote', 'add', 'origin', str(remote))
        push = ['-c', f'core.hooksPath={HOOKS}', 'push', '-q', 'origin']
        self.commit('notes.txt', 'clean\n')
        self.git(*push, 'main')
        clean = self.commit('notes.txt', 'still clean\n')
        self.git(*push, 'main')
        self.commit('notes.txt', 'fixture-codename\n')
        with self.assertRaises(subprocess.CalledProcessError) as refused:
            self.git(*push, 'main')
        self.assertIn('notes.txt:1: fixture-codename', refused.exception.stdout + refused.exception.stderr)
        self.assertIn('push refused', refused.exception.stderr)
        self.assertEqual(self.git('--git-dir', str(remote), 'rev-parse', 'main').strip(), clean)
        self.git('switch', '-q', '-c', 'side', clean)
        with self.assertRaises(subprocess.CalledProcessError):
            self.git(*push, 'main:leaky')
        self.git(*push, 'side')
        self.git(*push, ':side')


if __name__ == '__main__':
    unittest.main()

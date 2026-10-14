"""Prove the publication scan fails on deny-listed content, paths, refs, tags and author headers."""
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

    def commit(self, name, text, message='Fixture change', email='dev@example.invalid', author=None):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(text if isinstance(text, bytes) else text.encode())
        self.git('add', name)
        self.git('commit', '-qm', message, *(['--author', author] if author else []), email=email)
        return self.git('rev-parse', 'HEAD').strip()

    def remote(self, name):
        bare = self.root / f'{name}.git'
        self.git('init', '-q', '--bare', str(bare), cwd=self.root)
        self.git('remote', 'add', name, str(bare))
        return bare

    def hooked_push(self, remote='origin'):
        return ['-c', f'core.hooksPath={HOOKS}', 'push', '-q', remote]

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

    def test_a_term_in_the_author_or_committer_fails(self):
        # a commit made under a private identity (a work email, say) must not reach a public remote
        authored = self.commit('notes.txt', 'clean\n', author='Fixture-Host Dev <dev@example.invalid>')
        committed = self.commit('notes.txt', 'still clean\n', email='dev@fixture-codename.invalid',
                                author='Dev <dev@example.invalid>')
        r = self.scan('history')
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn(f'{authored[:12]}:<author>: fixture-host', r.stdout)
        self.assertIn(f'{committed[:12]}:<committer>: fixture-codename', r.stdout)
        self.assertEqual(r.stdout.count('<author>') + r.stdout.count('<committer>'), 2, r.stdout)

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
        (self.repo / 'clean.txt').write_text('clean\nlocal Fixture-Host edit\n')
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


    def test_a_term_in_an_added_or_renamed_path_fails_in_history_and_tree(self):
        base = self.commit('clean.txt', 'clean\n')
        empty = self.commit('docs/Fixture-Codename notes.md', '')  # no hunk: only the diff header names it
        quoted = self.commit('say "fixture-host".txt', 'clean\n')  # git C-quotes this path
        self.git('mv', 'clean.txt', 'renamed-fixture-host.txt')
        self.git('commit', '-qm', 'Rename')
        renamed = self.git('rev-parse', 'HEAD').strip()
        r = self.scan('range', f'{base}..{renamed}')
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn(f'{empty[:12]}:docs/Fixture-Codename notes.md: fixture-codename', r.stdout)
        self.assertIn(f'{quoted[:12]}:say "fixture-host".txt: fixture-host', r.stdout)
        self.assertIn(f'{renamed[:12]}:renamed-fixture-host.txt: fixture-host', r.stdout)
        edited = self.commit('renamed-fixture-host.txt', 'edited\n')  # the name was published with its add
        self.assertEqual(self.scan('range', f'{renamed}..{edited}').returncode, 0)
        r = self.scan('tree')
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn('docs/Fixture-Codename notes.md: fixture-codename', r.stdout)
        self.assertIn('renamed-fixture-host.txt: fixture-host', r.stdout)
        self.assertEqual(self.scan('tree', base).returncode, 0)
        self.assertIn('HEAD:renamed-fixture-host.txt: fixture-host', self.scan('tree', 'HEAD').stdout)

    def test_non_ascii_terms_match_any_case_in_every_mode(self):
        self.denylist.write_text('ümlaut-term\nstraße\n', encoding='utf-8')
        sha = self.commit('notes.txt', 'see the ÜMLAUT-TERM\nin the GROSSE STRASSE\n')
        r = self.scan('history')
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn(f'{sha[:12]}:notes.txt:1: ümlaut-term', r.stdout)
        self.assertIn(f'{sha[:12]}:notes.txt:2: straße', r.stdout)
        r = self.scan('tree')
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn('notes.txt:1: ümlaut-term', r.stdout)
        self.assertIn('notes.txt:2: straße', r.stdout)

    def test_a_byte_order_mark_does_not_hide_the_first_term(self):
        self.denylist.write_bytes('﻿bom-term\nother-term\n'.encode())
        sha = self.commit('notes.txt', 'BOM-TERM\n')
        r = self.scan('history')
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn(f'{sha[:12]}:notes.txt:1: bom-term', r.stdout)

    def test_a_textconv_driver_cannot_hide_content(self):
        conv = self.bin / 'conv'
        conv.write_text('#!/bin/sh\necho clean\n')
        conv.chmod(0o755)
        self.git('config', 'diff.conv.textconv', 'conv')
        self.commit('.gitattributes', '*.txt diff=conv\n')
        sha = self.commit('notes.txt', 'fixture-host\n')
        self.assertIn('+clean', self.git('log', '-1', '-p', '--format=', sha))  # the driver is live
        r = self.scan('history')
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn(f'{sha[:12]}:notes.txt:1: fixture-host', r.stdout)
        self.assertIn('notes.txt:1: fixture-host', self.scan('tree').stdout)

    def test_history_reads_ref_names_and_annotated_tags(self):
        self.commit('notes.txt', 'clean\n')
        self.assertEqual(self.scan('history').returncode, 0)
        self.git('branch', 'Fixture-Host-wip')
        r = self.scan('history')
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn('<ref>:refs/heads/Fixture-Host-wip: fixture-host', r.stdout)
        self.git('branch', '-D', 'Fixture-Host-wip')
        self.git('tag', '-a', 'v1', '-m', 'Release for Fixture-Codename')
        tag = self.git('rev-parse', 'v1').strip()
        r = self.scan('history')
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn(f'{tag[:12]}:<tag>:6: fixture-codename', r.stdout)

    def test_replacements_drive_filter_repo_and_comments_never_become_rules(self):
        self.denylist.write_text('# fixture\n# note: keep==>gone\nfixture-codename==>neutral-name\n\n'
                                 'fixture-host\nFixture-Host==>\n')
        r = self.scan('replacements')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, 'fixture-codename==>neutral-name\nfixture-host\nFixture-Host==>\n')
        filter_repo = shutil.which('git-filter-repo')
        if not filter_repo:
            self.skipTest('git-filter-repo is not installed')
        (self.bin / 'git-filter-repo').symlink_to(filter_repo)
        self.commit('notes.txt', 'fixture-codename\nfixture-host and Fixture-Host.\n# fixture\n# note: keep\n')
        self.assertEqual(self.scan('history').returncode, 1)
        rules = self.root / 'replacements'
        rules.write_text(r.stdout)
        self.git('filter-repo', '--force', '--quiet', '--replace-text', str(rules))
        self.assertEqual(self.git('show', 'HEAD:notes.txt'),
                         'neutral-name\n***REMOVED*** and .\n# fixture\n# note: keep\n')
        r = self.scan('history')
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_a_line_filter_repo_would_read_differently_is_refused(self):
        self.commit('notes.txt', 'clean\n')
        for line in (' leading', 'trailing ', 'spaced ==>x', 'spaced==> x', 'regex:fixture.*', 'glob:fixture*',
                     'literal:fixture', 'a==>b==>c', '==>x'):
            self.denylist.write_text(f'# fixture\nfixture-host\n{line}\n')
            for mode in ('history', 'replacements'):
                r = self.scan(mode)
                self.assertNotEqual(r.returncode, 0, (line, mode))
                self.assertIn(f'{self.denylist}:3: ', r.stderr, (line, mode))

    def test_binary_content_is_scanned_as_text(self):
        sha = self.commit('blob.bin', b'bin\0ary Fixture-Codename \0\n')
        r = self.scan('history')
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn(f'{sha[:12]}:blob.bin:1: fixture-codename', r.stdout)
        r = self.scan('tree')
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn('blob.bin:1: fixture-codename', r.stdout)

    def test_a_term_only_in_an_evil_merge_resolution_fails(self):
        base = self.commit('notes.txt', 'clean\n')
        self.git('switch', '-q', '-c', 'side')
        self.commit('side.txt', 'side\n')
        self.git('switch', '-q', 'main')
        self.commit('main.txt', 'main\n')
        self.git('merge', '-q', '--no-commit', 'side')
        (self.repo / 'evil.txt').write_text('fixture-codename\n')
        self.git('add', 'evil.txt')
        self.git('commit', '-qm', 'Merge side')
        merge = self.git('rev-parse', 'HEAD').strip()
        r = self.scan('range', f'{base}..{merge}')
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn(f'{merge[:12]}:evil.txt:1: fixture-codename', r.stdout)

    def test_the_hook_scans_a_new_branch_against_the_pushed_remote_only(self):
        origin = self.remote('origin')
        self.remote('mirror')
        self.commit('notes.txt', 'clean\n')
        self.git(*self.hooked_push(), 'main')
        self.commit('leak.txt', 'fixture-codename\n')
        self.git('push', '-q', 'mirror', 'main')  # unhooked: a private mirror already holds the leak
        with self.assertRaises(subprocess.CalledProcessError) as refused:
            self.git(*self.hooked_push(), 'main:refs/heads/feature')
        self.assertIn('leak.txt:1: fixture-codename', refused.exception.stdout + refused.exception.stderr)
        self.assertNotIn('refs/heads/feature', self.git('--git-dir', str(origin), 'for-each-ref'))

    def test_the_hook_refuses_a_ref_name_or_an_annotated_tag_carrying_a_term(self):
        origin = self.remote('origin')
        self.commit('notes.txt', 'clean\n')
        self.git(*self.hooked_push(), 'main')
        with self.assertRaises(subprocess.CalledProcessError) as refused:
            self.git(*self.hooked_push(), 'main:refs/heads/fixture-codename-wip')
        self.assertIn('<ref>:refs/heads/fixture-codename-wip: fixture-codename', refused.exception.stdout)
        self.git('branch', 'Fixture-Host-local')
        with self.assertRaises(subprocess.CalledProcessError) as refused:
            self.git(*self.hooked_push(), 'Fixture-Host-local:refs/heads/neutral')
        self.assertIn('<ref>:refs/heads/Fixture-Host-local: fixture-host', refused.exception.stdout)
        self.git('tag', '-a', 'v1', '-m', 'Release for Fixture-Host')
        with self.assertRaises(subprocess.CalledProcessError) as refused:
            self.git(*self.hooked_push(), 'v1')
        self.assertIn(':<tag>:6: fixture-host', refused.exception.stdout)
        self.git('tag', '-a', 'v2', '-m', 'Clean release', email='dev@fixture-codename.invalid')
        with self.assertRaises(subprocess.CalledProcessError) as refused:
            self.git(*self.hooked_push(), 'v2')
        self.assertIn(':<tag>:4: fixture-codename', refused.exception.stdout)
        self.git('tag', '-a', 'v3', '-m', 'Clean release')
        self.git(*self.hooked_push(), 'v3', 'main:refs/heads/clean-wip')
        self.assertEqual(self.git('--git-dir', str(origin), 'for-each-ref', '--format=%(refname)').split(),
                         ['refs/heads/clean-wip', 'refs/heads/main', 'refs/tags/v3'])

    def test_the_hook_refuses_a_hit_in_any_of_several_pushed_refs(self):
        origin = self.remote('origin')
        base = self.commit('notes.txt', 'clean\n')
        self.git(*self.hooked_push(), 'main')
        for branch, text in (('a-clean', 'a\n'), ('b-leaky', 'fixture-host\n'), ('c-clean', 'c\n')):
            self.git('switch', '-q', '-c', branch, base)
            self.commit(f'{branch}.txt', text)
        with self.assertRaises(subprocess.CalledProcessError) as refused:
            self.git(*self.hooked_push(), 'a-clean', 'b-leaky', 'c-clean')
        self.assertIn('b-leaky.txt:1: fixture-host', refused.exception.stdout)
        self.assertEqual(self.git('--git-dir', str(origin), 'for-each-ref', '--format=%(refname)').split(),
                         ['refs/heads/main'])

    def test_the_hook_scans_a_new_branch_below_its_clean_tip(self):
        origin = self.remote('origin')
        self.commit('notes.txt', 'clean\n')
        self.git(*self.hooked_push(), 'main')
        self.commit('leak.txt', 'fixture-codename\n')
        self.commit('notes.txt', 'clean tip\n')
        with self.assertRaises(subprocess.CalledProcessError) as refused:
            self.git(*self.hooked_push(), 'main:refs/heads/feature')
        self.assertIn('leak.txt:1: fixture-codename', refused.exception.stdout)
        self.assertNotIn('refs/heads/feature', self.git('--git-dir', str(origin), 'for-each-ref'))

if __name__ == '__main__':
    unittest.main()

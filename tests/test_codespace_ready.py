"""The codespace-ready inventory is read-only and reports what Git does not hold."""
import importlib.util
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1]
SCRIPT = SOURCE / 'private_dot_claude/skills/codespace-ready/scripts/inventory.py'
CANARY = 'canary-not-a-real-key-' + '7f3a'


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.home = self.root / 'home'
        self.home.mkdir()
        self.env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
        self.env.update({
            'HOME': str(self.home), 'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': os.devnull,
            'GIT_AUTHOR_NAME': 'Owner', 'GIT_AUTHOR_EMAIL': 'owner@example.com',
            'GIT_COMMITTER_NAME': 'Owner', 'GIT_COMMITTER_EMAIL': 'owner@example.com',
            'GIT_OPTIONAL_LOCKS': '0'})
        self.repo = self.home / 'acme-docs'
        self.grading = self.home / 'acme-grading'
        self.linked = self.repo / '.claude' / 'worktrees' / 'fix-headings'
        self.codex = self.home / '.codex' / 'worktrees' / 'sess' / 'acme-docs'
        self.decoy = self.home / '.codex' / 'worktrees' / 'other' / 'acme-docs'
        self.build_fixture()

    def git(self, *args, cwd):
        return subprocess.run(
            ['git', '--no-optional-locks', '-c', 'user.name=Owner', '-c', 'user.email=owner@example.com', *args],
            cwd=cwd, env=self.env, check=True, capture_output=True, text=True).stdout

    def build_fixture(self):
        remote = self.root / 'remote.git'
        self.git('init', '-q', '--bare', '-b', 'main', str(remote), cwd=self.root)
        self.git('clone', '-q', str(remote), str(self.repo), cwd=self.root)
        checkout = subprocess.run(['git', 'checkout', '-q', '-b', 'main'], cwd=self.repo, env=self.env,
                                  capture_output=True, text=True)
        if checkout.returncode != 0:
            self.git('checkout', '-q', 'main', cwd=self.repo)
        (self.repo / 'tests').mkdir()
        (self.repo / 'scripts').mkdir()
        (self.repo / '.gitignore').write_text('/tmp/\n/data/\n.env\nnode_modules/\n')
        (self.repo / 'Taskfile.yml').write_text('version: "3"\ntasks:\n  test:\n    cmds:\n      - python3 -m unittest\n')
        (self.repo / 'README.md').write_text('# acme-docs\n')
        self.grading.mkdir()
        (self.grading / 'private').mkdir()
        (self.grading / 'private' / 'rung3.json').write_text('grade 4/4/5\n')
        (self.repo / 'scripts' / 'grade.sh').write_text(
            '#!/bin/bash\ncd %s\nGRADING_HOME=%s\n' % (self.repo, self.grading))
        self.git('add', '-A', cwd=self.repo)
        self.git('commit', '-qm', 'Start the document pipeline', cwd=self.repo)
        self.git('push', '-q', 'origin', 'main', cwd=self.repo)

        self.git('checkout', '-q', '-b', 'feat/ports', cwd=self.repo)
        (self.repo / 'Taskfile.yml').write_text(
            'version: "3"\ntasks:\n  test:\n    cmds:\n      - python3 -m unittest\n'
            '  cs:ports:up:\n    desc: forward\n    cmds:\n      - echo forwarding\n')
        self.git('commit', '-qam', 'Add cs:ports:up', cwd=self.repo)
        self.git('push', '-q', 'origin', 'feat/ports', cwd=self.repo)
        self.git('checkout', '-q', 'main', cwd=self.repo)

        (self.repo / 'README.md').write_text('# acme-docs\nRun task test before pushing.\n')
        self.git('commit', '-qam', 'Document the test rule', cwd=self.repo)
        self.git('checkout', '-q', '-b', 'wip/parser', cwd=self.repo)
        (self.repo / 'parser.py').write_text('def parse(x): return x\n')
        self.git('add', 'parser.py', cwd=self.repo)
        self.git('commit', '-qm', 'Parser skeleton', cwd=self.repo)
        (self.repo / 'parser.py').write_text('def parse(x): return x\ndef tokens(x): return x.split()\n')
        self.git('commit', '-qam', 'Tokenizer', cwd=self.repo)
        self.git('checkout', '-q', 'main', cwd=self.repo)

        self.git('worktree', 'add', '-q', '-b', 'fix/headings', str(self.linked), 'main', cwd=self.repo)
        with (self.linked / 'README.md').open('a') as handle:
            handle.write('Headings are sentence case.\n')
        (self.linked / 'NOTES-draft.md').write_text('draft notes\n')

        (self.repo / 'README.md').write_text('# acme-docs\nRun task test before pushing.\n# stashed idea\n')
        self.git('stash', 'push', '-q', '-m', 'half-done README idea', cwd=self.repo)

        fixtures = self.repo / 'tmp' / 'fixtures'
        fixtures.mkdir(parents=True)
        (fixtures / 'corpus.json').write_text('{"programs": ["ZAPP1"]}\n')
        outside = self.home / 'big.bin'
        outside.write_bytes(b'x' * 2_000_000)
        (self.repo / 'tmp' / 'escape').symlink_to(outside)
        modules = self.repo / 'node_modules' / 'pkg'
        modules.mkdir(parents=True)
        (modules / 'index.js').write_text('module.exports = {}\n')
        (self.repo / 'reference').mkdir()
        (self.repo / 'reference' / 'honda-brief.pdf').write_text('%PDF-1.4 owner brief\n')
        (self.repo / '.env').write_text('GEMINI_API_KEY=%s\n' % CANARY)
        memory = self.repo / '.scratch' / 'memory' / 'claude'
        memory.mkdir(parents=True)
        (memory / 'viewing-the-app.md').write_text(
            'To view the app from the Mac, run `task cs:ports:up` and open http://localhost:13570.\n')
        (memory / 'MEMORY.md').write_text('- run task cs:ports:up on the Mac\n')
        (self.repo / 'CLAUDE.md').write_text('Ports: task cs:ports:up\n')

        self.git('worktree', 'add', '-q', '-b', 'codex/fix', str(self.codex), 'main', cwd=self.repo)
        (self.codex / 'NOTES.md').write_text('codex dirty\n')
        self.decoy.mkdir(parents=True)
        self.git('init', '-q', '-b', 'main', str(self.decoy), cwd=self.root)

    def run_inventory(self, repo=None, cwd=None, extra=()):
        cmd = [sys.executable, '-I', str(SCRIPT)]
        if repo is not None:
            cmd.extend(['--repo', str(repo)])
        return subprocess.run(cmd, cwd=cwd or repo or self.repo, env=self.env,
                              capture_output=True, text=True, timeout=90)

    def inventory(self, repo=None):
        result = self.run_inventory(repo if repo is not None else self.repo)
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
        self.assertNotIn('Traceback', result.stdout)
        self.assertNotIn('Traceback', result.stderr)
        return result.stdout

    def section(self, text, title):
        marker = '## ' + title
        start = text.find(marker)
        self.assertNotEqual(start, -1, text)
        rest = text[start + len(marker):]
        nxt = rest.find('\n## ')
        return rest if nxt < 0 else rest[:nxt]

    def test_unpushed_commit_on_main_is_listed(self):
        body = self.section(self.inventory(), 'branches')
        self.assertRegex(body, r'`main` \| 1 \|')
        self.assertIn('ahead 1', body)
        self.assertIn('Document the test rule', body)

    def test_local_only_branch_is_listed(self):
        body = self.section(self.inventory(), 'branches')
        row = next(line for line in body.splitlines() if line.startswith('| `wip/parser`'))
        self.assertIn('| none |', row)
        self.assertIn('| no |', row)
        self.assertIn('Parser skeleton', body)
        self.assertIn('Tokenizer', body)

    def test_unmerged_pushed_branch_and_its_task_are_listed(self):
        text = self.inventory()
        branches = self.section(text, 'branches')
        self.assertIn('`origin/feat/ports`', branches)
        self.assertIn('Unmerged branches pushed to a remote:', branches)
        tasks = self.section(text, 'branch-only tasks')
        self.assertIn('`cs:ports:up`', tasks)
        self.assertIn('feat/ports', tasks)
        self.assertIn('.scratch/memory/claude/viewing-the-app.md:1', tasks)
        self.assertIn('CLAUDE.md:1', tasks)
        self.assertNotIn('`test`', tasks)

    def test_dirty_linked_worktree_is_listed(self):
        body = self.section(self.inventory(), 'worktrees')
        row = next(line for line in body.splitlines() if str(self.linked.resolve()) in line)
        self.assertIn('1 modified', row)
        self.assertIn('1 untracked', row)
        self.assertIn('`fix/headings`', row)

    def test_codex_worktree_sharing_the_common_dir_is_listed_once(self):
        body = self.section(self.inventory(), 'worktrees')
        path = str(self.codex.resolve())
        self.assertEqual(body.count(path), 1)
        row = next(line for line in body.splitlines() if path in line)
        self.assertIn('1 untracked', row)
        self.assertNotIn(str(self.decoy.resolve()), body)

    def test_stash_is_listed(self):
        self.assertIn('half-done README idea', self.section(self.inventory(), 'stashes'))

    def test_ignored_fixtures_and_rebuildable_bulk_are_listed(self):
        body = self.section(self.inventory(), 'untracked and ignored files')
        self.assertIn('`tmp/`', body)
        self.assertIn('reference/', body)
        row = next(line for line in body.splitlines() if 'node_modules' in line)
        self.assertIn('rebuildable', row)
        tmp_row = next(line for line in body.splitlines() if '`tmp/`' in line)
        self.assertNotIn('MB', tmp_row)
        self.assertNotIn('GB', tmp_row)
        self.assertRegex(body, r'`\.scratch/` is \d+(\.\d+)? (B|KB|MB)')

    def test_outside_repo_path_in_a_script_is_listed(self):
        body = self.section(self.inventory(), 'paths outside the repo')
        self.assertIn(str(self.grading.resolve()), body)
        self.assertIn('scripts/grade.sh', body)
        self.assertNotIn(str(self.repo.resolve()), body)

    def test_env_canary_never_appears(self):
        result = self.run_inventory(self.repo)
        blob = result.stdout + result.stderr
        self.assertNotIn(CANARY, blob)
        env = self.section(result.stdout, 'env files')
        self.assertIn('`.env`', env)
        self.assertIn('task work:cs', env)
        self.assertNotIn(CANARY, env)

    def test_default_repo_is_the_cwd_top_level(self):
        result = self.run_inventory(repo=None, cwd=self.repo / 'scripts')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Repo: `%s`' % self.repo.resolve(), result.stdout)
        self.assertNotIn('Repo: `%s`' % (self.repo / 'scripts').resolve(), result.stdout)

    def test_script_writes_nothing(self):
        status_before = self.git('status', '--porcelain', cwd=self.repo)
        linked_before = self.git('status', '--porcelain', cwd=self.linked)
        tree_before = tree_listing(self.repo)
        codex_before = tree_listing(self.codex)
        result = self.run_inventory(self.repo)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(tree_listing(self.repo), tree_before)
        self.assertEqual(tree_listing(self.codex), codex_before)
        self.assertEqual(self.git('status', '--porcelain', cwd=self.repo), status_before)
        self.assertEqual(self.git('status', '--porcelain', cwd=self.linked), linked_before)


class ClearFailureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
        self.env.update({'HOME': str(self.root), 'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': os.devnull,
                         'GIT_AUTHOR_NAME': 'Owner', 'GIT_AUTHOR_EMAIL': 'owner@example.com',
                         'GIT_COMMITTER_NAME': 'Owner', 'GIT_COMMITTER_EMAIL': 'owner@example.com'})

    def git(self, *args, cwd):
        subprocess.run(
            ['git', '--no-optional-locks', '-c', 'user.name=Owner', '-c', 'user.email=owner@example.com', *args],
            cwd=cwd, env=self.env, check=True, capture_output=True, text=True)

    def inventory(self, repo):
        return subprocess.run([sys.executable, '-I', str(SCRIPT), '--repo', str(repo)], cwd=self.root,
                              env=self.env, capture_output=True, text=True, timeout=60)

    def test_repo_with_no_remote_is_a_clear_line(self):
        repo = self.root / 'solo'
        repo.mkdir()
        self.git('init', '-q', '-b', 'main', str(repo), cwd=self.root)
        (repo / 'README.md').write_text('solo\n')
        self.git('add', 'README.md', cwd=repo)
        self.git('commit', '-qm', 'Solo', cwd=repo)
        result = self.inventory(repo)
        blob = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, blob)
        self.assertNotIn('Traceback', blob)
        self.assertIn('No remote is configured.', result.stdout)
        self.assertIn('`main`', self.section(result.stdout, 'branches'))

    def test_non_repo_is_a_clear_line(self):
        path = self.root / 'not-a-repo'
        path.mkdir()
        (path / 'file.txt').write_text('hi\n')
        result = self.inventory(path)
        blob = result.stdout + result.stderr
        self.assertEqual(result.returncode, 0, blob)
        self.assertNotIn('Traceback', blob)
        self.assertIn('is not a git repository', result.stdout)
        self.assertIn('could not check: not a git repository', result.stdout)

    def section(self, text, title):
        marker = '## ' + title
        start = text.find(marker)
        self.assertNotEqual(start, -1, text)
        rest = text[start + len(marker):]
        nxt = rest.find('\n## ')
        return rest if nxt < 0 else rest[:nxt]


class QuietInventoryTests(unittest.TestCase):
    """The r1 report drops noise the r0 inventory printed."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name).resolve()
        self.home = self.root / 'home'
        self.home.mkdir()
        self.env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
        self.env.update({
            'HOME': str(self.home), 'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': os.devnull,
            'GIT_AUTHOR_NAME': 'Owner', 'GIT_AUTHOR_EMAIL': 'owner@example.com',
            'GIT_COMMITTER_NAME': 'Owner', 'GIT_COMMITTER_EMAIL': 'owner@example.com',
            'GIT_OPTIONAL_LOCKS': '0'})
        self.repo = self.home / 'orbit-notes'
        self.ssh = self.home / '.ssh'
        self.data = self.home / 'data-dir'
        self.only_dev = self.home / 'only-devcontainer'
        self.detached = self.repo / 'detached-wt'
        self.linked = self.repo / '.claude' / 'worktrees' / 'env-wt'
        self.build()

    def git(self, *args, cwd):
        return subprocess.run(
            ['git', '--no-optional-locks', '-c', 'user.name=Owner', '-c', 'user.email=owner@example.com', *args],
            cwd=cwd, env=self.env, check=True, capture_output=True, text=True).stdout

    def build(self):
        remote = self.root / 'remote.git'
        self.git('init', '-q', '--bare', '-b', 'main', str(remote), cwd=self.root)
        self.git('clone', '-q', str(remote), str(self.repo), cwd=self.root)
        checkout = subprocess.run(['git', 'checkout', '-q', '-b', 'main'], cwd=self.repo, env=self.env,
                                  capture_output=True, text=True)
        if checkout.returncode != 0:
            self.git('checkout', '-q', 'main', cwd=self.repo)
        (self.repo / '.gitignore').write_text('/tmp/\nnode_modules/\nnoise-*\nwide/\n.env\n')
        (self.repo / 'README.md').write_text('# orbit-notes\n')
        scripts = self.repo / 'scripts'
        scripts.mkdir()
        self.ssh.mkdir()
        (self.ssh / 'id').write_text('not-a-key\n')
        self.data.mkdir()
        (self.data / 'keep.txt').write_text('keep\n')
        self.only_dev.mkdir()
        (self.only_dev / 'skip.txt').write_text('skip\n')
        (scripts / 'paths.sh').write_text('#!/bin/bash\nSSH=%s\nDATA=%s\n' % (self.ssh, self.data))
        devcontainer = self.repo / '.devcontainer'
        devcontainer.mkdir()
        (devcontainer / 'setup.sh').write_text('#!/bin/bash\nONLY=%s\n' % self.only_dev)
        self.git('add', '-A', cwd=self.repo)
        self.git('commit', '-qm', 'Start', cwd=self.repo)
        self.git('push', '-q', 'origin', 'main', cwd=self.repo)
        self.git('checkout', '-q', '-b', 'wip/seven', cwd=self.repo)
        for number in range(1, 8):
            (self.repo / 'seven.txt').write_text('n=%s\n' % number)
            self.git('add', 'seven.txt', cwd=self.repo)
            self.git('commit', '-qm', 'seven %s' % number, cwd=self.repo)
        self.git('worktree', 'add', '--detach', str(self.detached), 'wip/seven', cwd=self.repo)
        self.git('worktree', 'add', '-q', '-b', 'fix/env', str(self.linked), 'main', cwd=self.repo)
        (self.linked / '.env').write_text('WORKTREE_KEY=nope\n')
        (self.repo / '.env').write_text('GEMINI_API_KEY=%s\n' % CANARY)
        (self.repo / '.env.example').write_text('GEMINI_API_KEY=example\n')
        (self.repo / '.env.sample').write_text('TOKEN=sample\n')
        modules = self.repo / 'web' / 'node_modules' / 'pkg'
        modules.mkdir(parents=True)
        (modules / 'index.js').write_text('module.exports = {}\n')
        wide = self.repo / 'wide'
        wide.mkdir()
        (wide / 'big.bin').write_bytes(b'b' * 200)
        (wide / 'small.bin').write_bytes(b's' * 10)
        for number in range(31):
            (self.repo / ('noise-%02d' % number)).write_text('x\n')
        (self.repo / 'tmp' / 'fixtures').mkdir(parents=True)
        (self.repo / 'tmp' / 'fixtures' / 'corpus.json').write_text('{}\n')

    def run_inventory(self):
        return subprocess.run([sys.executable, '-I', str(SCRIPT), '--repo', str(self.repo)],
                              cwd=self.repo, env=self.env, capture_output=True, text=True, timeout=90)

    def inventory(self):
        if not hasattr(self, '_text'):
            result = self.run_inventory()
            self.assertEqual(result.returncode, 0, result.stderr or result.stdout)
            self.assertNotIn('Traceback', result.stdout + result.stderr)
            self.assertNotIn(CANARY, result.stdout + result.stderr)
            self._text = result.stdout
        return self._text

    def section(self, title):
        text = self.inventory()
        marker = '## ' + title
        start = text.find(marker)
        self.assertNotEqual(start, -1, text)
        rest = text[start + len(marker):]
        nxt = rest.find('\n## ')
        return rest if nxt < 0 else rest[:nxt]

    def test_env_examples_and_worktree_env_are_skipped(self):
        env = self.section('env files')
        names = [line for line in env.splitlines() if line.startswith('- ')]
        self.assertIn('- `.env`', names)
        self.assertFalse(any('example' in line or 'sample' in line or 'worktrees' in line for line in names), names)
        self.assertRegex(env, r'Skipped [1-9]\d* other \.env\* names\.')

    def test_nested_ignored_node_modules_is_listed(self):
        ignored = self.section('untracked and ignored files').split('### ignored', 1)[1]
        self.assertIn('`web/node_modules/`', ignored)

    def test_ignored_list_caps_at_30(self):
        ignored = self.section('untracked and ignored files').split('### ignored', 1)[1]
        self.assertRegex(ignored, r'… \d+ more, \d+\.\d+ MB')

    def test_hidden_home_and_devcontainer_paths_are_dropped(self):
        body = self.section('paths outside the repo')
        self.assertIn(str(self.data.resolve()), body)
        self.assertNotIn(str(self.ssh.resolve()), body)
        self.assertNotIn(str(self.only_dev.resolve()), body)

    def test_seven_unpushed_commits_show_five_subjects(self):
        body = self.section('branches')
        self.assertRegex(body, r'`wip/seven` \| 7 \|')
        start = body.find('- `wip/seven`')
        self.assertNotEqual(start, -1, body)
        block = body[start:]
        nxt = block.find('\n- `', 1)
        if nxt > 0:
            block = block[:nxt]
        self.assertIn('… and 2 more', block)
        self.assertEqual(len(re.findall(r'`[0-9a-f]+` seven \d', block)), 5)
        self.assertNotIn('seven 1', block)
        self.assertNotIn('seven 2', block)

    def test_detached_worktree_on_no_remote_is_flagged(self):
        body = self.section('worktrees')
        row = next(line for line in body.splitlines() if str(self.detached.resolve()) in line)
        self.assertIn('on no remote', row)
        self.assertIn('unpushed work on no branch', row)

    def test_folder_over_the_threshold_lists_children(self):
        sys.dont_write_bytecode = True
        spec = importlib.util.spec_from_file_location('codespace_ready_inventory', SCRIPT)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.addCleanup(lambda: shutil.rmtree(SCRIPT.parent / '__pycache__', ignore_errors=True))
        mod.FOLDER_BREAKDOWN = 50
        text = mod.render(str(self.repo))
        ignored = text.split('### ignored', 1)[1].split('### ', 1)[0]
        self.assertIn('`wide/`', ignored)
        self.assertIn('`big.bin`', ignored)
        self.assertIn('`small.bin`', ignored)


class PackagingTests(unittest.TestCase):
    def test_skill_files_are_managed(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp).resolve()
            config = home / 'chezmoi.toml'
            config.write_text('[data]\ngitName = "Fixture"\ngitEmail = "fixture@example.invalid"\n')
            managed = subprocess.check_output(
                ['chezmoi', '--source', str(SOURCE), '--destination', str(home), '--config', str(config),
                 '--persistent-state', str(home / 'state.boltdb'), 'managed'], text=True).splitlines()
        for path in ('.claude/skills/codespace-ready/SKILL.md',
                     '.claude/skills/codespace-ready/scripts/inventory.py'):
            self.assertIn(path, managed, managed)
        self.assertEqual([p for p in managed if '__pycache__' in p or p.endswith('.pyc')], [])


def tree_listing(root):
    rows = []
    root = Path(root).resolve()
    st = root.lstat()
    rows.append(('.', st.st_mtime_ns, st.st_size, stat.S_IFMT(st.st_mode)))
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames.sort()
        for name in sorted(dirnames + filenames):
            path = Path(dirpath) / name
            st = path.lstat()
            rows.append((str(path.relative_to(root)), st.st_mtime_ns, st.st_size, stat.S_IFMT(st.st_mode)))
    return tuple(rows)


if __name__ == '__main__':
    unittest.main()

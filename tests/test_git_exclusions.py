"""Prove a normal git add cannot stage known private dotfiles or recovery data."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1]


class GitExclusionTests(unittest.TestCase):
    def test_git_add_skips_private_files_and_retains_intended_templates(self):
        private = [
            '.env', '.env.production', 'dot_env', 'private_dot_env.local',
            '.zprofile', 'dot_zprofile', 'private_dot_zprofile',
            '.zshrc.local', 'dot_zshrc.local', 'private_dot_zshrc.local',
            'machine.json', '.config/chezmoi/machine.json',
            'dot_config/chezmoi/chezmoi.toml', 'private_dot_config/chezmoi/machine.json',
            '.ssh/id_ed25519', 'private_dot_ssh/id_ed25519',
            '.git-credentials', 'private_dot_git-credentials',
            '.config/gh/hosts.yml', 'dot_config/gh/hosts.yml',
            '.codex/auth.json', 'private_dot_codex/auth.json', 'dot_codex/config.toml',
            'private_dot_claude/.credentials.json', '.claude/settings.json',
            'private_dot_claude/settings.json', 'private_dot_claude/private_settings.json',
            'snapshot/source.tar.gz', 'history.bundle', 'installed.tgz', 'backup.zip',
            'backups/raw-settings.json', 'legacy-source/dot_zprofile',
            'private.pem', 'client.key', 'state.sqlite3',
        ]
        public = [
            '.chezmoitemplates/machine.json.tmpl', '.chezmoitemplates/claude-settings.json',
            'private_dot_claude/private_settings.json.tmpl',
            'dot_config/git/identity-personal.tmpl', 'dot_codex/AGENTS.md',
            'dot_codex/agents/ship_worker.toml', 'private_dot_claude/CLAUDE.md',
            'dot_gitconfig.tmpl', 'dot_zshrc.tmpl', 'README.md', 'Taskfile.yml',
        ]
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Test repository policy independently of machine/global exclusions.
            env = {**os.environ, 'GIT_CONFIG_GLOBAL': os.devnull, 'GIT_CONFIG_NOSYSTEM': '1'}
            subprocess.run(['git', 'init', '-q', str(root)], env=env, check=True)
            shutil.copy2(SOURCE / '.gitignore', root / '.gitignore')
            for name in private + public:
                p = root / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text('harmless fixture\n')
            subprocess.run(['git', '-C', str(root), 'add', '--all'], env=env, check=True)
            staged = set(subprocess.check_output(['git', '-C', str(root), 'ls-files'], env=env, text=True).splitlines())
            self.assertEqual(sorted(staged.intersection(private)), [], 'Private paths were staged')
            self.assertTrue(set(public).issubset(staged), sorted(set(public) - staged))

    def test_existing_tracked_source_is_not_hidden_by_ignore_rules(self):
        paths = subprocess.check_output(['git', '-C', str(SOURCE), 'ls-files', '-z'])
        result = subprocess.run(['git', '-C', str(SOURCE), 'check-ignore', '--no-index', '-z', '--stdin'],
                                input=paths, capture_output=True)
        self.assertEqual(result.stdout, b'', 'An intended tracked source file is ignored')
        self.assertEqual(result.returncode, 1, result.stderr)

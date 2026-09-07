"""Exercise the actual chezmoi renderer against isolated home directories."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import tomllib
import unittest

SOURCE = Path(__file__).resolve().parents[1]

class RenderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name).resolve()
        self.config = self.home / 'chezmoi.toml'
        self.config.write_text('[data]\ngitName = "Fixture"\ngitEmail = "fixture@example.invalid"\n')
        self.command = ['chezmoi', '--source', str(SOURCE), '--destination', str(self.home),
                        '--config', str(self.config), '--persistent-state', str(self.home / 'state.boltdb')]

    def profile(self, obj):
        target = self.home / '.config/chezmoi/machine.json'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(obj))
        return target

    def render(self, path):
        return subprocess.check_output(self.command + ['cat', str(self.home / path)], text=True)

    def test_claude_local_preferences_and_live_model_survive(self):
        self.profile({'claudeSettings': {'effortLevel': 'medium', 'permissions': {'defaultMode': 'default'},
                      'enabledPlugins': {'fixture@local': False}, 'model': 'stale-profile-model'}})
        target = self.home / '.claude/settings.json'
        target.parent.mkdir()
        target.write_text('{"model":"active-model"}')
        data = json.loads(self.render('.claude/settings.json'))
        self.assertEqual(data['model'], 'active-model')
        self.assertEqual(data['effortLevel'], 'medium')
        self.assertEqual(data['permissions']['defaultMode'], 'default')
        self.assertFalse(data['enabledPlugins']['fixture@local'])

    def test_herdr_host_preferences_and_resume_policy(self):
        self.profile({'herdr': {'theme': {'custom': {'green': '#123456'}},
                               'experimental': {'allow_nested': True}}})
        data = tomllib.loads(self.render('.config/herdr/config.toml'))
        self.assertEqual(data['theme']['custom']['green'], '#123456')
        self.assertTrue(data['experimental']['allow_nested'])
        self.assertIsInstance(data['advanced']['scrollback_limit_bytes'], int)
        self.assertTrue(data['session']['resume_agents_on_restore'])
        self.assertEqual(data['ui']['toast']['delivery'], 'herdr')

    def test_identity_uses_machine_profile(self):
        self.profile({'git': {'name': 'Machine Owner', 'email': 'machine@example.invalid'}})
        target = self.home / 'rendered-gitconfig'
        target.write_text(self.render('.gitconfig'))
        email = subprocess.check_output(['git', 'config', '--file', str(target), 'user.email'], text=True).strip()
        self.assertEqual(email, 'machine@example.invalid')

    def install_git_identity(self):
        managed = subprocess.check_output(self.command + ['managed'], text=True).splitlines()
        for path in ['.gitconfig'] + [p for p in managed if p.startswith('.config/git/identity-')]:
            target = self.home / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(self.render(path))
        self.git_env = {**os.environ, 'HOME': str(self.home), 'GIT_CONFIG_NOSYSTEM': '1',
                        'GIT_CONFIG_GLOBAL': str(self.home / '.gitconfig')}

    def git(self, repo, *args):
        return subprocess.check_output(['git', '-C', str(repo), *args],
                                       env=self.git_env, text=True, stderr=subprocess.PIPE).strip()

    def test_work_identity_follows_https_and_ssh_remotes(self):
        prefixes = ['https://github.com/', 'git@github.com:', 'ssh://git@github.com/']
        self.profile({'git': {'name': 'Owner', 'email': 'personal@example.invalid',
                             'workEmail': 'work@example.invalid',
                             'workRemotePatterns': [p + 'work-org/**' for p in prefixes]}})
        self.install_git_identity()
        repo = self.home / 'repo'
        repo.mkdir()
        self.git(repo, 'init')
        self.git(repo, 'remote', 'add', 'origin', 'https://github.com/personal/repo.git')
        self.assertEqual(self.git(repo, 'config', 'user.email'), 'personal@example.invalid')
        for prefix in prefixes:
            with self.subTest(prefix=prefix):
                self.git(repo, 'remote', 'set-url', 'origin', prefix + 'work-org/repo.git')
                self.assertIn('Owner <work@example.invalid>', self.git(repo, 'var', 'GIT_AUTHOR_IDENT'))
                self.assertIn('Owner <work@example.invalid>', self.git(repo, 'var', 'GIT_COMMITTER_IDENT'))

    def test_personal_remote_overrides_work_directory_and_worktree_inherits(self):
        work = self.home / 'work'
        self.profile({'git': {'name': 'Owner', 'email': 'personal@example.invalid',
                             'workEmail': 'work@example.invalid',
                             'workDirectories': [str(work) + '/'],
                             'personalRemotePatterns': ['https://github.com/personal/**']}})
        self.install_git_identity()
        repo = work / 'repo'
        repo.mkdir(parents=True)
        self.git(repo, 'init')
        self.assertEqual(self.git(repo, 'config', 'user.email'), 'work@example.invalid')
        self.git(repo, 'commit', '--allow-empty', '-m', 'Fixture')
        linked = self.home / 'linked'
        self.git(repo, 'worktree', 'add', '-b', 'fixture-linked', str(linked))
        self.assertEqual(self.git(linked, 'config', 'user.email'), 'work@example.invalid')
        self.git(repo, 'remote', 'add', 'origin', 'https://github.com/personal/dotfiles.git')
        for checkout in [repo, linked]:
            self.assertEqual(self.git(checkout, 'config', 'user.email'), 'personal@example.invalid')
        self.git(repo, 'config', '--local', 'user.email', 'explicit@example.invalid')
        self.assertEqual(self.git(linked, 'config', 'user.email'), 'explicit@example.invalid')

    def test_invalid_profile_refuses_render(self):
        self.profile({}).write_text('{broken')
        result = subprocess.run(self.command + ['cat', str(self.home / '.claude/settings.json')], capture_output=True)
        self.assertNotEqual(result.returncode, 0)

    def test_invalid_live_settings_refuses_render(self):
        target = self.home / '.claude/settings.json'
        target.parent.mkdir()
        target.write_text('{broken')
        result = subprocess.run(self.command + ['cat', str(target)], capture_output=True)
        self.assertNotEqual(result.returncode, 0)

    def test_repository_and_private_state_are_not_installed(self):
        managed = subprocess.check_output(self.command + ['managed'], text=True).splitlines()
        self.assertNotIn('.config/nvim/lazy-lock.json', managed)
        for path in managed:
            self.assertFalse(path.startswith(('tests', 'scripts', 'docs', '.config/chezmoi', '.ssh', '.codex/skills')), path)
            self.assertNotIn(path, ['Taskfile.yml', 'README.md', 'LICENSE'])

    def test_codespace_default_is_host_data(self):
        self.profile({'codespace': 'fixture-codespace'})
        shell = self.render('.zshrc')
        self.assertIn('fixture-codespace', shell)
        self.assertIn('csalive()', shell)
        subprocess.run(['zsh', '-n'], input=shell, text=True, check=True)

    def test_machine_local_shell_additions_survive_shared_config(self):
        (self.home / '.zshrc').write_text(self.render('.zshrc'))
        (self.home / '.zshrc.local').write_text('export DOTFILES_LOCAL_FIXTURE=loaded\n')
        antidote = self.home / '.antidote'
        antidote.mkdir()
        (antidote / 'antidote.zsh').write_text('antidote() { :; }\n')
        result = subprocess.run(['zsh', '-ic', 'print -r -- "LOCAL:${DOTFILES_LOCAL_FIXTURE:-missing}"'],
                                env={**os.environ, 'HOME': str(self.home), 'ZDOTDIR': str(self.home),
                                     'PATH': '/usr/bin:/bin', 'TOOLBELT_QUIET': '1'},
                                text=True, capture_output=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('LOCAL:loaded', result.stdout)
        managed = subprocess.check_output(self.command + ['managed'], text=True).splitlines()
        self.assertNotIn('.zshrc.local', managed)

    def test_numeric_override_passes_the_herdr_parser(self):
        self.profile({'herdr': {'advanced': {'scrollback_limit_bytes': 12345678}}})
        rendered = self.render('.config/herdr/config.toml')
        self.assertIsInstance(tomllib.loads(rendered)['advanced']['scrollback_limit_bytes'], int)
        import shutil
        if shutil.which('herdr'):
            config = self.home / 'herdr.toml'
            config.write_text(rendered)
            subprocess.run(['herdr', 'config', 'check'], env={**os.environ, 'HERDR_CONFIG_PATH': str(config)}, check=True, capture_output=True)

    def test_invalid_codespace_refuses_render(self):
        self.profile({'codespace': "team's-code"})
        result = subprocess.run(self.command + ['cat', str(self.home / '.zshrc')], capture_output=True)
        self.assertNotEqual(result.returncode, 0)

if __name__ == '__main__':
    unittest.main()

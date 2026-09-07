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
        self.home = Path(self.tmp.name)
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
        self.assertTrue(data['session']['resume_agents_on_restore'])
        self.assertEqual(data['ui']['toast']['delivery'], 'herdr')

    def test_identity_uses_machine_profile(self):
        self.profile({'git': {'name': 'Machine Owner', 'email': 'machine@example.invalid'}})
        target = self.home / 'rendered-gitconfig'
        target.write_text(self.render('.gitconfig'))
        email = subprocess.check_output(['git', 'config', '--file', str(target), 'user.email'], text=True).strip()
        self.assertEqual(email, 'machine@example.invalid')

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
        for path in managed:
            self.assertFalse(path.startswith(('tests', 'scripts', 'docs', '.config/chezmoi', '.ssh', '.codex/skills')), path)
            self.assertNotIn(path, ['Taskfile.yml', 'README.md', 'LICENSE'])

    def test_codespace_default_is_host_data(self):
        self.profile({'codespace': 'fixture-codespace'})
        shell = self.render('.zshrc')
        self.assertIn('fixture-codespace', shell)
        self.assertIn('csalive()', shell)
        subprocess.run(['zsh', '-n'], input=shell, text=True, check=True)

if __name__ == '__main__':
    unittest.main()

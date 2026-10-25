"""The Linux toolbelt installer: covers .zshrc's toolbelt and never fails an apply."""
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1]
SCRIPT = SOURCE / '.chezmoiscripts/run_onchange_after_install-toolbelt.sh'


class ToolbeltInstallerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name).resolve()
        self.shim = self.home / 'shim'
        self.shim.mkdir()

    def run_as(self, system, **env):
        # Only a fake uname is on PATH: no apt-get, curl or sudo, so nothing can be installed.
        uname = self.shim / 'uname'
        uname.write_text(f'#!/bin/sh\necho {system}\n')
        uname.chmod(0o755)
        return subprocess.run(['/bin/bash', str(SCRIPT)], capture_output=True, text=True, timeout=30,
                              env={'PATH': str(self.shim), 'HOME': str(self.home), **env})

    def test_every_toolbelt_tool_has_an_install_line(self):
        shell = (SOURCE / 'dot_zshrc.tmpl').read_text()
        block = re.search(r'^_TOOLBELT=\((.*?)^\)', shell, re.M | re.S).group(1)
        script = SCRIPT.read_text()
        commands = [record.split('|')[1] for record in re.findall(r'"([^"]+)"', block)]
        self.assertGreater(len(commands), 10)
        for names in commands:
            with self.subTest(commands=names):
                self.assertIn('have ' + ' '.join(names.split(',')) + ' ||', script)
        self.assertIn('have starship ||', script)

    def test_macos_and_an_explicit_skip_do_nothing(self):
        for system, env in (('Darwin', {}), ('Linux', {'DOTFILES_SKIP_TOOLBELT': '1'})):
            with self.subTest(system=system, env=env):
                result = self.run_as(system, **env)
                self.assertEqual((result.returncode, result.stdout, result.stderr), (0, '', ''))
                self.assertFalse((self.home / '.local').exists())

    def test_a_system_without_apt_reports_what_is_missing_and_still_succeeds(self):
        result = self.run_as('Linux')
        self.assertEqual(result.returncode, 0)
        self.assertIn('not an apt-based system, so nothing was installed', result.stderr)
        self.assertIn('Missing: rg fd fzf', result.stderr)
        self.assertNotIn('fd-find', result.stderr)
        self.assertFalse((self.home / '.local').exists())

    def test_the_installer_passes_shellcheck(self):
        if subprocess.run(['sh', '-c', 'command -v shellcheck'], capture_output=True).returncode:
            self.skipTest('shellcheck is not installed')
        subprocess.run(['shellcheck', str(SCRIPT)], check=True)


if __name__ == '__main__':
    unittest.main()

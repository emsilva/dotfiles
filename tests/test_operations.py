import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1]
SCRIPT = SOURCE / 'scripts/dotfiles.py'

class OperationTests(unittest.TestCase):
    def test_backup_preserves_live_bytes_symlinks_and_profile(self):
        self.assertTrue(SCRIPT.exists(), 'The private backup entrypoint is not implemented')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / 'source'
            (source / 'scripts').mkdir(parents=True)
            shutil.copy2(SCRIPT, source / 'scripts/dotfiles.py')
            (source / '.chezmoiignore').write_text('scripts\n')
            (source / 'dot_example').write_text('source version\n')
            (source / 'symlink_dot_link').write_text('.example\n')
            home = root / 'home'
            (home / '.config').mkdir(parents=True)
            preferences = root / 'private-preferences'
            preferences.mkdir()
            (home / '.config/chezmoi').symlink_to(preferences, target_is_directory=True)
            (home / '.example').write_text('uncommitted installed version\n')
            (home / '.link').symlink_to('.example')
            profile = root / 'external-machine.json'
            profile.write_text('{"private":"fixture"}\n')
            (preferences / 'machine.json').symlink_to(profile)
            config = root / 'config.toml'
            config.write_text('')
            subprocess.run(['git', 'init', '-q', str(source)], check=True)
            subprocess.run(['git', '-C', str(source), 'add', '.'], check=True)
            subprocess.run(['git', '-C', str(source), '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', 'commit', '-qm', 'fixture'], check=True)
            result = subprocess.check_output(['python3', str(source / 'scripts/dotfiles.py'), 'backup', '--destination', str(home), '--config', str(config)], text=True)
            backup = Path(result.strip())
            self.assertEqual(backup.stat().st_mode & 0o777, 0o700)
            with tarfile.open(backup / 'installed.tar.gz') as archive:
                self.assertEqual(archive.extractfile('.example').read(), b'uncommitted installed version\n')
                self.assertTrue(archive.getmember('.link').issym())
                self.assertTrue(archive.getmember('.config/chezmoi').issym())
            self.assertTrue((backup / 'machine-config.tar.gz').exists(), 'Resolved private preferences are missing from the backup')
            with tarfile.open(backup / 'machine-config.tar.gz') as archive:
                self.assertEqual(archive.extractfile('chezmoi/machine.json').read(), b'{"private":"fixture"}\n')
            manifest = json.loads((backup / 'manifest.json').read_text())
            for name, expected in manifest['sha256'].items():
                with (backup / name).open('rb') as stream:
                    self.assertEqual(hashlib.file_digest(stream, 'sha256').hexdigest(), expected)

    def test_sync_refuses_divergence_without_changing_head(self):
        self.assertTrue(SCRIPT.exists(), 'The guarded sync entrypoint is not implemented')
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            remote, seed, local, home = [root / name for name in ('remote', 'seed', 'local', 'home')]
            home.mkdir()
            config = root / 'config.toml'; config.write_text('')
            def git(where, *args):
                return subprocess.check_output(['git', '-C', str(where), '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', *args], stderr=subprocess.DEVNULL, text=True).strip()
            subprocess.run(['git', 'init', '-q', '--bare', '--initial-branch=main', str(remote)], check=True)
            subprocess.run(['git', 'clone', '-q', str(remote), str(seed)], check=True, stderr=subprocess.DEVNULL)
            (seed / 'scripts').mkdir(); shutil.copy2(SCRIPT, seed / 'scripts/dotfiles.py')
            (seed / '.chezmoiignore').write_text('*\n')
            git(seed, 'add', '.'); git(seed, 'commit', '-qm', 'base'); git(seed, 'push', 'origin', 'main')
            subprocess.run(['git', 'clone', '-q', str(remote), str(local)], check=True)
            (seed / 'remote-change').write_text('remote'); git(seed, 'add', '.'); git(seed, 'commit', '-qm', 'remote'); git(seed, 'push', 'origin', 'main')
            (local / 'local-change').write_text('local'); git(local, 'add', '.'); git(local, 'commit', '-qm', 'local')
            before = git(local, 'rev-parse', 'HEAD')
            result = subprocess.run(['python3', str(local / 'scripts/dotfiles.py'), 'sync', '--destination', str(home), '--config', str(config)], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('diverged', result.stderr)
            self.assertEqual(git(local, 'rev-parse', 'HEAD'), before)

    def test_sync_refuses_drift_then_fast_forwards_without_applying(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            remote, seed, local, home = [root / name for name in ('remote', 'seed', 'local', 'home')]
            home.mkdir()
            config = root / 'config.toml'; config.write_text('')
            def git(where, *args):
                return subprocess.check_output(['git', '-C', str(where), '-c', 'user.name=Fixture', '-c', 'user.email=fixture@example.invalid', *args], stderr=subprocess.DEVNULL, text=True).strip()
            subprocess.run(['git', 'init', '-q', '--bare', '--initial-branch=main', str(remote)], check=True)
            subprocess.run(['git', 'clone', '-q', str(remote), str(seed)], check=True, stderr=subprocess.DEVNULL)
            (seed / 'scripts').mkdir(); shutil.copy2(SCRIPT, seed / 'scripts/dotfiles.py')
            (seed / '.chezmoiignore').write_text('scripts\n')
            (seed / 'dot_example').write_text('original\n')
            (home / '.example').write_text('original\n')
            git(seed, 'add', '.'); git(seed, 'commit', '-qm', 'base'); git(seed, 'push', 'origin', 'main')
            subprocess.run(['git', 'clone', '-q', str(remote), str(local)], check=True)
            before = git(local, 'rev-parse', 'HEAD')
            (seed / 'dot_example').write_text('upstream\n'); git(seed, 'add', '.'); git(seed, 'commit', '-qm', 'upstream'); git(seed, 'push', 'origin', 'main')
            command = ['python3', str(local / 'scripts/dotfiles.py'), 'sync', '--destination', str(home), '--config', str(config)]
            (local / 'dot_example').write_text('local source edit\n')
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Source checkout has local changes', result.stderr)
            self.assertEqual(git(local, 'rev-parse', 'HEAD'), before)
            (local / 'dot_example').write_text('original\n')
            (home / '.example').write_text('local installed edit\n')
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Installed dotfiles differ', result.stderr)
            self.assertEqual(git(local, 'rev-parse', 'HEAD'), before)
            (home / '.example').write_text('original\n')
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(git(local, 'rev-parse', 'HEAD'), git(seed, 'rev-parse', 'HEAD'))
            self.assertEqual((home / '.example').read_text(), 'original\n')
            self.assertEqual((local / 'dot_example').read_text(), 'upstream\n')

if __name__ == '__main__':
    unittest.main()

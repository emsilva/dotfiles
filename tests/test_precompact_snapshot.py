"""The PreCompact snapshot lands in the memory folder Claude uses for the session."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

HOOK = Path(__file__).resolve().parents[1] / 'private_dot_claude/skills/session-handoff/hooks/executable_precompact-snapshot.sh'


class SnapshotFolderTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        base = Path(self.tmp.name).resolve()
        self.home = base / 'home'
        self.project = base / 'work' / 'project'
        self.project.mkdir(parents=True)
        transcripts = self.home / '.claude/projects/-work-project'
        transcripts.mkdir(parents=True)
        self.transcript = transcripts / 'session.jsonl'
        self.transcript.write_text('')
        self.default = transcripts / 'memory/handoffs'

    def settings(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value if isinstance(value, str) else json.dumps(value))

    def run_hook(self, cwd=None):
        payload = json.dumps({'session_id': 's1', 'transcript_path': str(self.transcript),
                              'cwd': str(cwd or self.project), 'trigger': 'auto'})
        env = {'HOME': str(self.home), 'PATH': os.environ['PATH']}
        result = subprocess.run(['bash', str(HOOK)], input=payload, text=True, capture_output=True,
                                env=env, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)

    def snapshots(self, folder):
        return sorted(Path(folder).glob('EMERGENCY-*.md'))

    def test_without_a_setting_the_snapshot_goes_beside_the_transcript(self):
        self.run_hook()
        self.assertEqual(len(self.snapshots(self.default)), 1)

    def test_a_local_setting_routes_the_snapshot_to_that_folder(self):
        memory = self.project / '.scratch/memory/claude'
        self.settings(self.project / '.claude/settings.local.json', {'autoMemoryDirectory': str(memory)})
        self.run_hook()
        self.assertEqual(len(self.snapshots(memory / 'handoffs')), 1)
        self.assertEqual(self.snapshots(self.default), [])

    def test_local_beats_project_beats_user(self):
        local, shared, user = (self.home / name for name in ('local', 'shared', 'user'))
        self.settings(self.project / '.claude/settings.local.json', {'autoMemoryDirectory': str(local)})
        self.settings(self.project / '.claude/settings.json', {'autoMemoryDirectory': str(shared)})
        self.settings(self.home / '.claude/settings.json', {'autoMemoryDirectory': str(user)})
        self.run_hook()
        self.assertEqual(len(self.snapshots(local / 'handoffs')), 1)
        (self.project / '.claude/settings.local.json').unlink()
        self.run_hook()
        self.assertEqual(len(self.snapshots(shared / 'handoffs')), 1)
        (self.project / '.claude/settings.json').unlink()
        self.run_hook()
        self.assertEqual(len(self.snapshots(user / 'handoffs')), 1)
        self.assertEqual(self.snapshots(self.default), [])

    def test_a_tilde_path_is_expanded_against_home(self):
        self.settings(self.home / '.claude/settings.json', {'autoMemoryDirectory': '~/notes/memory'})
        self.run_hook()
        self.assertEqual(len(self.snapshots(self.home / 'notes/memory/handoffs')), 1)

    def test_a_relative_or_unreadable_setting_falls_back_to_the_default(self):
        self.settings(self.project / '.claude/settings.local.json', {'autoMemoryDirectory': 'relative/memory'})
        self.settings(self.home / '.claude/settings.json', '{not json')
        self.run_hook()
        self.assertEqual(len(self.snapshots(self.default)), 1)
        self.assertFalse((self.project / 'relative').exists())

    def test_the_local_file_at_the_git_root_counts_from_a_subdirectory(self):
        subprocess.run(['git', 'init', '-q', str(self.project)], check=True)
        memory = self.project / '.scratch/memory/claude'
        self.settings(self.project / '.claude/settings.local.json', {'autoMemoryDirectory': str(memory)})
        subdirectory = self.project / 'src'
        subdirectory.mkdir()
        self.run_hook(cwd=subdirectory)
        self.assertEqual(len(self.snapshots(memory / 'handoffs')), 1)


if __name__ == '__main__':
    unittest.main()

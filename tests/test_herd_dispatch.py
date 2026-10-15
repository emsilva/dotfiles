"""herd.py dispatch: the one-line brief, delivery confirmed in the worker's own files, the session read-back."""
import hashlib
import gc
import json
from pathlib import Path
import time
import unittest
from unittest import mock
import warnings

from handoff_fixtures import prompt
from herd_fixtures import CODEX_BANNER, HerdCase, agent, herdlib, listing

TIME = '2026-10-14T10:00:01.000Z'
FAST = {'HERD_RESEND_SECONDS': '2', 'HERD_CONFIRM_SECONDS': '3'}
# Codex 0.162.1's /new in a git repo (measured live 2026-10-14; herdr reports the pane idle meanwhile).
WHERE = ('  Where should the new conversation run?\n› 1. Use current Git worktree  Keep using the current working '
         'directory\n  2. Create new Git worktree   Create a separate checkout of this repository\n'
         '  enter select · esc back\n')


class DispatchCase(HerdCase):
    def setUp(self):
        super().setUp()
        self.brief = self.root / 'BRIEF-x.md'
        self.brief.write_text('do the thing\n')
        self.sha = hashlib.sha256(self.brief.read_bytes()).hexdigest()
        self.report = self.root / 'out' / 'REPORT.md'
        self.line = ('Read and execute %s (sha256 %s). Deliver %s, reply with its path and sha256, then end your '
                     'turn. For a ruling, write %s and end your turn.'
                     % (self.brief, self.sha[:16], self.report, self.root / 'out' / 'BLOCKED.md'))

    def rollout(self, sid, line=None, cwd=None, timestamp=TIME, subagent=False):
        """(path, text) of a Codex session file as 0.162.1 writes it."""
        meta = {'id': sid, 'timestamp': timestamp, 'cwd': str(cwd or self.repo), 'originator': 'codex-tui'}
        if subagent:
            meta.update(parent_thread_id='P1', thread_source='subagent', source={'subagent': {}})
        else:
            meta.update(thread_source='user', source='cli')
        text = json.dumps({'timestamp': timestamp, 'type': 'session_meta', 'payload': meta}) + '\n'
        if line:
            text += json.dumps({'timestamp': timestamp, 'type': 'response_item', 'payload': {
                'type': 'message', 'role': 'user', 'content': [{'type': 'input_text', 'text': line}]}}) + '\n'
        path = self.codex_home / 'sessions' / '2026' / '10' / '14' / ('rollout-2026-10-14T10-00-01-%s.jsonl' % sid)
        return [str(path), text]

    def codex_worker(self, status='idle', session=None):
        self.record(self.launch_row('one-xhigh-aaaa', 'wT:p2', session=session))
        return listing({'pane_id': 'wT:p2', 'tab_id': 'wT:t1', 'cwd': str(self.repo), 'agent': 'codex',
                        'agent_status': status, 'name': 'one-xhigh-aaaa',
                        **({'agent_session': {'value': session}} if session else {})})

    def dispatch(self, answers, *extra, env=None, code=None):
        return self.herd(answers, 'dispatch', 'one-xhigh-aaaa', '--brief', str(self.brief), '--deliverable',
                         str(self.report), *extra, env=env, code=code)

    def snapshot_code(self, path, denied=False):
        # Delete the actual file after discovery, immediately before stat. Other paths use the real stat.
        action = "raise PermissionError('snapshot denied')" if denied else 'os.unlink(candidate)'
        return ("import herd, herd_dispatch, os\nfrom unittest import mock\n"
                "original_size = herd_dispatch.os.path.getsize\n"
                "def snapshot_size(candidate):\n"
                "    if candidate == %r:\n        %s\n"
                "    return original_size(candidate)\n"
                "with mock.patch.object(herd_dispatch.os.path, 'getsize', side_effect=snapshot_size):\n"
                "    sys.exit(herd.main(sys.argv[1:]))\n") % (str(path), action)

    def prompts(self):
        return [c[3] for c in self.calls(['agent', 'prompt'])]


class CodexDispatchTests(DispatchCase):
    def test_a_vanished_snapshot_rollout_does_not_abort_dispatch(self):
        panes, agents = self.codex_worker()
        path, text = self.rollout('OLD', self.line)
        Path(path).parent.mkdir(parents=True)
        Path(path).write_text(text)
        result = self.dispatch({'pane list': [panes], 'agent list': [agents],
                                'agent prompt': [{'out': '{}', 'write': [self.rollout('C1', self.line)]}],
                                'agent get': [agent('working', 'wT:p2', session='C1')]},
                               code=self.snapshot_code(path))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['session_id'], 'C1')
        self.assertEqual(self.prompts(), [self.line])
        self.assertEqual([row['type'] for row in self.rows()], ['launch', 'dispatch'])
        self.assertFalse(Path(path).exists(), 'the snapshot race was not exercised')

    def test_a_denied_snapshot_rollout_still_prevents_dispatch(self):
        panes, agents = self.codex_worker()
        path, text = self.rollout('OLD')
        Path(path).parent.mkdir(parents=True)
        Path(path).write_text(text)
        result = self.dispatch({'pane list': [panes], 'agent list': [agents]},
                               code=self.snapshot_code(path, denied=True))
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn('cannot bound delivery to new transcript bytes: snapshot denied', result.stderr)
        self.assertEqual(self.prompts(), [])
        self.assertEqual([row['type'] for row in self.rows()], ['launch'])
        self.assertTrue(Path(path).is_file())

    def test_herdr_fallback_refuses_subagents_and_other_working_directories(self):
        panes, agents = self.codex_worker()
        for subagent, cwd in ((True, self.repo), (False, self.root / 'other')):
            with self.subTest(subagent=subagent, cwd=cwd):
                path, text = self.rollout('C1', self.line, cwd=cwd, subagent=subagent)
                meta, prompt_text = text.split('\n', 1)
                Path(path).parent.mkdir(parents=True, exist_ok=True)
                Path(path).write_text(meta + '\n')
                r = self.dispatch({'pane list': [panes], 'agent list': [agents],
                                   'agent prompt': [{'out': '{}', 'write': [[path, prompt_text]]}],
                                   'agent get': [agent('working', 'wT:p2', session='C1')]},
                                  env={'HERD_RESEND_SECONDS': '0', 'HERD_CONFIRM_SECONDS': '0'})
                self.assertEqual(r.returncode, 1, r.stderr)
                self.assertEqual([r['type'] for r in self.rows()], ['launch'])

    def test_a_valid_existing_session_fallback_keeps_its_warning(self):
        panes, agents = self.codex_worker()
        path, text = self.rollout('C1', self.line)
        meta, prompt_text = text.split('\n', 1)
        Path(path).parent.mkdir(parents=True)
        Path(path).write_text(meta + '\n')
        r = self.dispatch({'pane list': [panes], 'agent list': [agents],
                           'agent prompt': [{'out': '{}', 'write': [[path, prompt_text]]}],
                           'agent get': [agent('working', 'wT:p2', session='C1')]})
        self.assertEqual(r.returncode, 0, r.stderr)
        row = json.loads(r.stdout)
        self.assertEqual(row['session_id'], 'C1')
        self.assertIn('no new session file passed the checks', row['session_warning'])

    def test_an_old_identical_prompt_cannot_confirm_a_lost_redispatch(self):
        panes, agents = self.codex_worker(session='C1')
        path, text = self.rollout('C1', self.line)
        Path(path).parent.mkdir(parents=True)
        Path(path).write_text(text)
        r = self.dispatch({'pane list': [panes], 'agent list': [agents], 'agent prompt': [{'out': '{}'}],
                           'agent get': [agent('working', 'wT:p2', session='C1')]},
                          env={'HERD_RESEND_SECONDS': '0', 'HERD_CONFIRM_SECONDS': '0'})
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertEqual(self.prompts(), [self.line, self.line])
        self.assertEqual([r['type'] for r in self.rows()], ['launch'])

    def test_a_redispatch_confirms_a_newly_appended_identical_prompt(self):
        panes, agents = self.codex_worker(session='C1')
        path, text = self.rollout('C1', self.line)
        Path(path).parent.mkdir(parents=True)
        Path(path).write_text(text)
        new_prompt = text.split('\n', 1)[1]
        r = self.dispatch({'pane list': [panes], 'agent list': [agents],
                           'agent prompt': [{'out': '{}'}, {'out': '{}', 'write': [[path, new_prompt]]}],
                           'agent get': [agent('working', 'wT:p2', session='C1')]},
                          env={'HERD_RESEND_SECONDS': '0', 'HERD_CONFIRM_SECONDS': '0'})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.prompts(), [self.line, self.line])

    def test_the_first_brief_reads_the_session_from_herdr_and_the_new_file(self):
        panes, agents = self.codex_worker()
        r = self.dispatch({'pane list': [panes], 'agent list': [agents],
                           'agent prompt': [{'out': '{}', 'write': [self.rollout('C1', self.line)]}],
                           'agent get': [agent('working', 'wT:p2', session='C1')]})
        self.assertEqual(r.returncode, 0, r.stderr)
        row = json.loads(r.stdout)
        self.assertEqual(self.prompts(), [self.line])
        self.assertEqual(self.calls(['agent', 'prompt'])[0][2], 'wT:p2')
        self.assertEqual({k: row[k] for k in ('seq', 'brief', 'brief_sha256', 'deliverable', 'blocked', 'reset',
                                              'session_id')},
                         {'seq': 1, 'brief': str(self.brief), 'brief_sha256': self.sha, 'deliverable': str(self.report),
                          'blocked': str(self.root / 'out' / 'BLOCKED.md'), 'reset': None, 'session_id': 'C1'})
        self.assertNotIn('session_warning', row)
        self.assertIn('herd.py wait', row['wait'])
        self.assertEqual([r['type'] for r in self.rows()], ['launch', 'dispatch'])

    def test_when_herdr_learns_no_session_the_file_gives_it(self):
        panes, agents = self.codex_worker()
        r = self.dispatch({'pane list': [panes], 'agent list': [agents],
                           'agent prompt': [{'out': '{}', 'write': [self.rollout('C1', self.line)]}],
                           'agent get': [agent('working', 'wT:p2')]})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)['session_id'], 'C1')

    def test_a_disagreement_takes_the_file_and_says_so(self):
        panes, agents = self.codex_worker()
        r = self.dispatch({'pane list': [panes], 'agent list': [agents],
                           'agent prompt': [{'out': '{}', 'write': [self.rollout('C1', self.line)]}],
                           'agent get': [agent('working', 'wT:p2', session='C7')]})
        row = json.loads(r.stdout)
        self.assertEqual((row['session_id'], row['session_warning']),
                         ('C1', 'herdr reports session C7, the new session file says C1'))

    def test_a_subagent_file_in_the_same_folder_is_not_the_workers_session(self):
        # A Codex worker's own subagents write session files with its cwd, after the prompt, holding its text.
        panes, agents = self.codex_worker()
        r = self.dispatch({'pane list': [panes], 'agent list': [agents],
                           'agent prompt': [{'out': '{}', 'write': [self.rollout('SUB', self.line, subagent=True),
                                                                    self.rollout('C1', self.line)]}],
                           'agent get': [agent('working', 'wT:p2')]})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)['session_id'], 'C1')

    def test_the_session_file_is_bounded_by_the_start_not_the_launch_row(self):
        # Codex stamps its session file with its own start: after started_at, before the launch row's `at` (written
        # once the banner is checked). A file stamped before started_at is another session's.
        self.record(dict(self.launch_row('one-xhigh-aaaa', 'wT:p2'), started_at='2026-10-14T10:00:00Z',
                         at='2026-10-14T10:00:03Z'))
        panes, agents = listing({'pane_id': 'wT:p2', 'tab_id': 'wT:t1', 'cwd': str(self.repo), 'agent': 'codex',
                                 'agent_status': 'idle', 'name': 'one-xhigh-aaaa'})
        r = self.dispatch({'pane list': [panes], 'agent list': [agents],
                           'agent prompt': [{'out': '{}', 'write': [
                               self.rollout('OLD', self.line, timestamp='2026-10-14T09:59:59.000Z'),
                               self.rollout('C1', self.line, timestamp='2026-10-14T10:00:01.000Z')]}],
                           'agent get': [agent('working', 'wT:p2')]}, env=FAST)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)['session_id'], 'C1')

    def test_a_session_another_worker_claimed_is_not_read_back(self):
        self.record(self.launch_row('two-xhigh-bbbb', 'wT:p3', session='C9'))
        panes, agents = self.codex_worker()
        r = self.dispatch({'pane list': [panes], 'agent list': [agents],
                           'agent prompt': [{'out': '{}', 'write': [self.rollout('C9', self.line),
                                                                    self.rollout('C1', self.line)]}],
                           'agent get': [agent('working', 'wT:p2')]})
        self.assertEqual(json.loads(r.stdout)['session_id'], 'C1')

    def test_a_running_session_takes_the_brief_in_its_own_file(self):
        path, text = self.rollout('C1')
        panes, agents = self.codex_worker(session='C1')
        self.codex_home.joinpath('sessions', '2026', '10', '14').mkdir(parents=True)
        Path(path).write_text(text)
        r = self.dispatch({'pane list': [panes], 'agent list': [agents],
                           'agent prompt': [{'out': '{}', 'write': [[path, self.rollout('C1', self.line)[1]]]}],
                           'agent get': [agent('working', 'wT:p2', session='C1')]})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)['session_id'], 'C1')

    def test_dispatches_in_one_folder_take_turns(self):
        # Read-only workers share the repo as their cwd: the window from the prompt to its session file is held per
        # folder, so a second dispatch cannot read the first one's new file as its own.
        panes, agents = self.codex_worker()
        lock = 'herd.lock.' + hashlib.sha1(str(self.repo).encode()).hexdigest()
        proc = None
        try:
            with herdlib.locked(str(self.pdir), lock):
                proc = self.start({'pane list': [panes], 'agent list': [agents],
                                   'agent prompt': [{'out': '{}', 'write': [self.rollout('C1', self.line)]}],
                                   'agent get': [agent('working', 'wT:p2')]},
                                  'dispatch', 'one-xhigh-aaaa', '--brief', str(self.brief), '--deliverable',
                                  str(self.report))
                deadline = time.monotonic() + 15
                while not self.calls(['agent', 'list']) and time.monotonic() < deadline:
                    time.sleep(0.05)
                time.sleep(1)   # past the live-pane read, the dispatch now waits on the folder's lock
                self.assertEqual(self.prompts(), [])
            out, err = proc.communicate(timeout=60)
            self.assertEqual(proc.returncode, 0, err)
            self.assertEqual(self.prompts(), [self.line])
        finally:
            if proc is not None:
                if proc.poll() is None:
                    proc.kill()
                proc.communicate(timeout=10)

    def test_a_lost_prompt_is_sent_once_more(self):
        panes, agents = self.codex_worker()
        r = self.dispatch({'pane list': [panes], 'agent list': [agents],
                           'agent prompt': [{'out': '{}'}, {'out': '{}', 'write': [self.rollout('C1', self.line)]}],
                           'agent get': [agent('idle', 'wT:p2')]}, env=FAST)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.prompts(), [self.line, self.line])

    def test_a_stalled_answer_from_herdr_is_settled_by_the_session_file(self):
        stalled = {'out': json.dumps({'error': {'code': 'agent_prompt_stalled', 'message': 'no lifecycle change'}}),
                   'code': 1, 'write': [self.rollout('C1', self.line)]}
        panes, agents = self.codex_worker()
        r = self.dispatch({'pane list': [panes], 'agent list': [agents], 'agent prompt': [stalled],
                           'agent get': [agent('working', 'wT:p2', session='C1')]})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((json.loads(r.stdout)['session_id'], self.prompts()), ('C1', [self.line]))

    def test_a_prompt_that_never_arrives_records_nothing(self):
        panes, agents = self.codex_worker()
        r = self.dispatch({'pane list': [panes], 'agent list': [agents], 'agent prompt': [{'out': '{}'}],
                           'agent get': [agent('idle', 'wT:p2')]}, env=FAST)
        self.assertEqual(r.returncode, 1)
        self.assertIn('did not reach one-xhigh-aaaa (sent twice', r.stderr)
        self.assertEqual(len(self.prompts()), 2)
        self.assertEqual([r['type'] for r in self.rows()], ['launch'])

    def test_new_resets_first_and_reads_the_new_session(self):
        panes, agents = self.codex_worker(session='C1')
        r = self.dispatch({'pane list': [panes], 'agent list': [agents],
                           'agent prompt': [{'out': '{}'}, {'out': '{}', 'write': [self.rollout(
                               'C2', self.line, timestamp='2099-01-01T00:00:00Z')]}],
                           'pane read': [{'out': WHERE}, {'out': ''}, CODEX_BANNER],
                           'agent get': [agent('idle', 'wT:p2', session='C1'), agent('idle', 'wT:p2', session='C1'),
                                         agent('working', 'wT:p2', session='C2')]}, '--reset', 'new')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.prompts(), ['/new', self.line])
        self.assertEqual([c[3] for c in self.calls(['agent', 'send-keys'])], ['enter'])
        row = json.loads(r.stdout)
        self.assertEqual((row['reset'], row['session_id']), ('new', 'C2'))
        self.assertNotIn('session_warning', row)


    def test_new_never_moves_the_worker_to_another_worktree(self):
        panes, agents = self.codex_worker(session='C1')
        moved = WHERE.replace('› 1.', '  1.').replace('  2. Create', '› 2. Create')
        r = self.dispatch({'pane list': [panes], 'agent list': [agents], 'agent prompt': [{'out': '{}'}],
                           'pane read': [{'out': moved}, {'out': ''}],
                           'agent get': [agent('idle', 'wT:p2', session='C1')]}, '--reset', 'new')
        self.assertEqual(r.returncode, 1)
        self.assertIn('"Use current Git worktree" is not selected', r.stderr)
        self.assertEqual(self.calls(['agent', 'send-keys']), [])
        self.assertEqual(self.prompts(), ['/new'])


class RefusalTests(DispatchCase):
    def test_a_worker_that_is_not_idle_gets_nothing(self):
        for status in ('working', 'blocked'):
            with self.subTest(status=status):
                (self.pdir / 'herd.jsonl').unlink(missing_ok=True)
                panes, agents = self.codex_worker(status=status)
                r = self.dispatch({'pane list': [panes], 'agent list': [agents]})
                self.assertEqual(r.returncode, 1)
                self.assertIn('is %s: dispatch only to an idle worker' % status, r.stderr)
                self.assertEqual(self.prompts(), [])

    def test_a_line_over_700_characters_is_refused_with_the_lengths(self):
        panes, agents = self.codex_worker()
        deep = self.root / ('d' * 200) / ('e' * 200) / 'REPORT.md'
        r = self.herd({'pane list': [panes], 'agent list': [agents]}, 'dispatch', 'one-xhigh-aaaa', '--brief',
                      str(self.brief), '--deliverable', str(deep))
        self.assertEqual(r.returncode, 1)
        self.assertIn('over 700', r.stderr)
        self.assertIn('deliverable %d' % len(str(deep)), r.stderr)
        self.assertEqual(self.prompts(), [])

    def test_a_reset_of_the_other_kind_is_refused(self):
        panes, agents = self.codex_worker()
        r = self.dispatch({'pane list': [panes], 'agent list': [agents]}, '--reset', 'clear')
        self.assertEqual(r.returncode, 1)
        self.assertIn('--reset clear is for claude workers', r.stderr)

    def test_a_lost_worker_and_an_unknown_name(self):
        self.codex_worker()
        panes, agents = listing()
        r = self.dispatch({'pane list': [panes], 'agent list': [agents]})
        self.assertEqual(r.returncode, 1)
        self.assertIn('has no live pane', r.stderr)
        r = self.herd({}, 'dispatch', 'nobody-xhigh-0000', '--brief', str(self.brief), '--deliverable', 'x')
        self.assertEqual(r.returncode, 2)
        self.assertIn("no open launch is called 'nobody-xhigh-0000'", r.stderr)


class ClaudeDispatchTests(DispatchCase):
    def test_a_vanished_snapshot_transcript_does_not_abort_dispatch(self):
        panes, agents = self.claude_worker('W1')
        path = Path(self.worker_transcript('OLD'))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(prompt(self.line)) + '\n')
        result = self.dispatch({'pane list': [panes], 'agent list': [agents],
                                'agent prompt': [{'out': '{}', 'write': [[self.worker_transcript('W1'),
                                                                        json.dumps(prompt(self.line)) + '\n']]}],
                                'agent get': [agent('working', 'wT:p2', session='W1', kind='claude')]},
                               code=self.snapshot_code(path))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['session_id'], 'W1')
        self.assertEqual(self.prompts(), [self.line])
        self.assertEqual([row['type'] for row in self.rows()], ['launch', 'dispatch'])
        self.assertFalse(path.exists(), 'the snapshot race was not exercised')

    def test_a_denied_snapshot_transcript_still_prevents_dispatch(self):
        panes, agents = self.claude_worker('W1')
        path = Path(self.worker_transcript('OLD'))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(prompt(self.line)) + '\n')
        result = self.dispatch({'pane list': [panes], 'agent list': [agents]},
                               code=self.snapshot_code(path, denied=True))
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn('cannot bound delivery to new transcript bytes: snapshot denied', result.stderr)
        self.assertEqual(self.prompts(), [])
        self.assertEqual([row['type'] for row in self.rows()], ['launch'])
        self.assertTrue(path.is_file())

    def test_an_old_identical_prompt_cannot_confirm_a_lost_redispatch(self):
        panes, agents = self.claude_worker('W1')
        path = Path(self.worker_transcript('W1'))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(prompt(self.line)) + '\n')
        r = self.dispatch({'pane list': [panes], 'agent list': [agents], 'agent prompt': [{'out': '{}'}],
                           'agent get': [agent('working', 'wT:p2', session='W1', kind='claude')]},
                          env={'HERD_RESEND_SECONDS': '0', 'HERD_CONFIRM_SECONDS': '0'})
        self.assertEqual(r.returncode, 1, r.stderr)
        self.assertEqual(self.prompts(), [self.line, self.line])
        self.assertEqual([r['type'] for r in self.rows()], ['launch'])

    def test_a_redispatch_confirms_a_newly_appended_identical_prompt(self):
        panes, agents = self.claude_worker('W1')
        path = Path(self.worker_transcript('W1'))
        path.parent.mkdir(parents=True, exist_ok=True)
        text = json.dumps(prompt(self.line)) + '\n'
        path.write_text(text)
        r = self.dispatch({'pane list': [panes], 'agent list': [agents],
                           'agent prompt': [{'out': '{}'}, {'out': '{}', 'write': [[str(path), text]]}],
                           'agent get': [agent('working', 'wT:p2', session='W1', kind='claude')]},
                          env={'HERD_RESEND_SECONDS': '0', 'HERD_CONFIRM_SECONDS': '0'})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.prompts(), [self.line, self.line])

    def claude_worker(self, session):
        self.record(dict(self.launch_row('one-xhigh-aaaa', 'wT:p2', session=session, kind='claude'),
                         model='claude-opus-5-5'))
        return listing({'pane_id': 'wT:p2', 'tab_id': 'wT:t1', 'cwd': str(self.repo), 'agent': 'claude',
                        'agent_status': 'idle', 'name': 'one-xhigh-aaaa', 'agent_session': {'value': session}})

    def worker_transcript(self, session):
        return str(self.projects / '-x-repo' / ('%s.jsonl' % session))

    def test_the_brief_is_confirmed_in_the_workers_transcript(self):
        panes, agents = self.claude_worker('W1')
        r = self.dispatch({'pane list': [panes], 'agent list': [agents],
                           'agent prompt': [{'out': '{}', 'write': [[self.worker_transcript('W1'),
                                                                     json.dumps(prompt(self.line)) + '\n']]}],
                           'agent get': [agent('working', 'wT:p2', session='W1', kind='claude')]})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)['session_id'], 'W1')

    def test_clear_reads_the_new_session_at_once(self):
        panes, agents = self.claude_worker('W1')
        r = self.dispatch({'pane list': [panes], 'agent list': [agents],
                           'agent prompt': [{'out': '{}'}, {'out': '{}', 'write': [[self.worker_transcript('W2'),
                                                                                    json.dumps(prompt(self.line)) + '\n']]}],
                           'pane read': [{'out': ' Opus 5.5 with xhigh effort\n'}],
                           'agent get': [agent('idle', 'wT:p2', session='W2', kind='claude')]}, '--reset', 'clear')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.prompts(), ['/clear', self.line])
        self.assertEqual(json.loads(r.stdout)['session_id'], 'W2')


class DispatchHygieneTests(unittest.TestCase):
    def test_the_running_session_fixture_closes_its_rollout_file(self):
        case = CodexDispatchTests('test_a_running_session_takes_the_brief_in_its_own_file')
        result = unittest.TestResult()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always', ResourceWarning)
            case.run(result)
            gc.collect()
        self.assertTrue(result.wasSuccessful(), result.errors + result.failures)
        self.assertEqual([str(w.message) for w in caught if issubclass(w.category, ResourceWarning)], [])

    def test_a_failed_lock_assertion_still_reaps_the_dispatch_process(self):
        case = CodexDispatchTests('test_dispatches_in_one_folder_take_turns')
        case.setUp()
        started = []
        real_start = case.start

        def start(answers, *args):
            answers['agent prompt'][0]['sleep'] = 5
            proc = real_start(answers, *args)
            started.append(proc)
            return proc

        try:
            with mock.patch.object(case, 'start', side_effect=start), \
                    mock.patch.object(case, 'assertEqual', side_effect=AssertionError('forced lock assertion')):
                with self.assertRaisesRegex(AssertionError, 'forced lock assertion'):
                    case.test_dispatches_in_one_folder_take_turns()
            self.assertEqual(len(started), 1)
            self.assertIsNotNone(started[0].poll(), 'failed assertion left its dispatch process running')
        finally:
            for proc in started:
                if proc.poll() is None:
                    proc.kill()
                proc.communicate(timeout=10)
            case.tearDown()


if __name__ == '__main__':
    unittest.main()

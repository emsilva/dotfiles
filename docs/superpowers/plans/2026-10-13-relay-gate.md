# Relay gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A Claude Code Stop and PostToolUse hook, `relay-gate.py`, that has a herdr lead run `/relay` at its first safe turn end at or above 50% context, never loops after a failed relay, and alerts the owner when it cannot relay.

**Architecture:** One stdlib CLI in the session-handoff skill's `scripts/` (`relay-gate.py stop|tool`) reads the hook JSON, meters the transcript (`transcript.context_fill`), decides from the session's relay dirs (`relaylib.relays_of`) and a per-lead state file, and prints a Stop block or a PostToolUse `additionalContext`. The safe-point rules move from `relay-check.py` into `relaylib.py` so the gate and `/relay`'s checklist cannot disagree. Registration in `~/.claude/settings.json` is the owner's; this plan tests with per-session `--settings`.

**Tech Stack:** Python 3 stdlib only (`python3 -I`), unittest, the existing herdr stub fixture, herdr 0.9.2-preview and Claude Code 2.1.296 for the live run.

**Spec:** `docs/superpowers/specs/2026-10-13-relay-gate-design.md`. Read it before any task: the plan argues from it.

**Proof:** every task's code below was applied in order to a scratch copy of this worktree and run with the task's own commands before this plan was committed: each RED step failed as stated, each GREEN step passed, and the full suite ended at `Ran 206 tests ... OK`.

## Global Constraints

- Stdlib Python only. CLIs run as `python3 -I`, set `sys.dont_write_bytecode = True` and insert their own directory on `sys.path` before importing `transcript` or `relaylib`: bytecode beside them in the chezmoi source would be deployed.
- Constants (spec "Parts"): threshold 50 (`RELAY_GATE_THRESHOLD`), cap 60 (`RELAY_GATE_CAP`), band step 10 (`RELAY_GATE_STEP`), back-off 1,800 s (`RELAY_GATE_BACKOFF_S`), throttle 60 s (`RELAY_GATE_THROTTLE_S`), window override (`RELAY_GATE_WINDOW`, tokens). Each override is test-only.
- `WINDOWS` starts with `{"claude-opus-5-5": 1_000_000}`, the only measured window.
- Hook timeouts 10 s (Stop) and 5 s (PostToolUse); the call stops gathering after 7 s and 3 s; every herdr call is bounded at 2 s.
- The gate never fails closed: on any error it exits 0 with no output. It never exits 2 (a hook's exit 2 blocks the session).
- Only a lead gets a state file, `<project>/relay/gate/<session-id>.json`, `"version": 1`; other sessions' files older than 7 days are pruned; `errors.log` keeps its last 100 KB; the per-session error marker is created with `O_EXCL`.
- A lead is a herdr pane name starting with `lead-`, or the session id in `<project>/relay/lead.json`. One lead per project.
- `relay-launch.sh` is unchanged. No task edits `~/.claude` or `settings.json`: deployment waits for the owner.
- The test command is the Taskfile's: `python3 -m unittest discover -s tests -v` from the repo root.

## Review Focus

- **A hook input without `transcript_path` or `session_id`** (an older or different Claude Code event): the gate must stay silent and write nothing. Pinned in Task 3 (`test_an_input_without_a_transcript_or_session_is_ignored`).
- **Parallel tool calls** fire PostToolUse hooks concurrently, all writing the same state file: the state must stay valid JSON with one band recorded. Pinned in Task 5 (`test_parallel_tool_calls_leave_a_valid_state`).
- **A `failed.json` torn by a crash mid-write** must still count as a failure, or the back-off is skipped. Pinned in Task 1 (`test_a_torn_failed_json_is_still_a_failure`).
- **A typed prompt whose timestamp cannot be read** must not defer the ask forever. Pinned in Task 4 (`test_a_prompt_without_a_readable_time_does_not_defer`).
- **A 10 MB lead transcript** (a real lead's size) must be metered well inside the Stop budget. Pinned in Task 2 (`test_a_10_mb_transcript_is_read_well_inside_the_stop_budget`).

## Files

| File | Responsibility | Task |
|---|---|---|
| `private_dot_claude/skills/session-handoff/scripts/relaylib.py` (new) | safe-point blockers (moved from relay-check.py), this session's relays classified by fact, will-repeat failures | 1 |
| `private_dot_claude/skills/session-handoff/scripts/relay-check.py` | imports `relaylib.blockers`; no behaviour change | 1 |
| `private_dot_claude/skills/session-handoff/scripts/transcript.py` | `WINDOWS`, `FILL_KEYS`, `context_fill()` | 2 |
| `private_dot_claude/skills/session-handoff/scripts/relay-gate.py` (new) | the hook: identity, state, errors (Task 3), Stop decision (Task 4), nudge (Task 5) | 3–5 |
| `tests/handoff_fixtures.py` | `usage()` record fixture | 2 |
| `tests/test_relaylib.py` (new) | relaylib tests; `make_relay()` reused by the gate tests | 1 |
| `tests/test_handoff_transcript.py` | meter tests, beside the module's other tests | 2 |
| `tests/test_relay_gate.py` (new) | gate tests (subprocess, herdr stub, fake HOME) | 3–5 |
| `private_dot_claude/skills/session-handoff/references/relay.md`, `SKILL.md`, `private_dot_claude/CLAUDE.md`, `tests/test_handoff_docs.py` | the automatic-relay docs and their pins | 6 |

---

### Task 1: relaylib: shared blockers and this session's relays

**Files:**
- Create: `private_dot_claude/skills/session-handoff/scripts/relaylib.py`
- Modify: `private_dot_claude/skills/session-handoff/scripts/relay-check.py` (the import block, `GIT_BUSY`, `blockers()`, its one caller in `cmd_checklist`)
- Test: `tests/test_relaylib.py`

**Interfaces:**
- Consumes: nothing new.
- Produces:
  - `relaylib.read_json(path) -> object` (raises `OSError`/`ValueError`).
  - `relaylib.blockers(repo: str, tasks: list[dict]) -> list[str]`: unchanged from `relay-check.py`; `tasks` are `transcript.open_tasks()` records.
  - `relaylib.ABANDONED_AFTER = 1500` (seconds).
  - `relaylib.classify(rdir: str, now: float) -> dict` and `relaylib.relays_of(project_dir: str, session_id: str, now: float | None = None) -> list[dict]`: each entry `{'id', 'dir', 'state', 'stage', 'reason', 'failed_at', 'handover_at'}`, `state` one of `closed`, `failed`, `abandoned`, `frozen`, `in_progress`; `failed_at` is a POSIX time (failed.json's mtime, or the last activity of an abandoned dir).
  - `relaylib.will_repeat(entry: dict) -> bool`.
  - `tests/test_relaylib.make_relay(project, rid, session=SID, files=(), age=0) -> Path`, reused by `tests/test_relay_gate.py`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_relaylib.py`:

```python
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

from handoff_fixtures import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import relaylib  # noqa: E402

SID = '44444444-4444-4444-8444-444444444444'


def make_relay(project, rid, session=SID, files=(), age=0):
    """A relay dir whose checklist names `session`; every file in it gets an mtime `age` seconds ago.

    files: names (e.g. 'launch.json', 'fired/relay-x-w1') or (name, json-able content) pairs."""
    rdir = Path(project) / 'relay' / rid
    rdir.mkdir(parents=True)
    (rdir / 'checklist.json').write_text(json.dumps({'relay_id': rid, 'predecessor': {'session_id': session}}))
    for f in files:
        name, content = f if isinstance(f, tuple) else (f, {})
        path = rdir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(content) if not isinstance(content, str) else content)
    when = time.time() - age
    for path in rdir.rglob('*'):
        os.utime(path, (when, when))
    return rdir


class BlockersTests(unittest.TestCase):
    def test_agents_and_workflows_block_shells_and_monitors_do_not(self):
        tasks = [{'kind': 'agent', 'id': 'a1', 'description': 'review', 'command': ''},
                 {'kind': 'workflow', 'id': 'w1', 'description': '', 'command': 'export const meta'},
                 {'kind': 'shell', 'id': 'b1', 'description': 'wait', 'command': 'sleep 9'},
                 {'kind': 'monitor', 'id': 'm1', 'description': 'tail', 'command': 'tail -f x'}]
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(relaylib.blockers(tmp, tasks),
                             ['agent a1 is running inside this session (review)',
                              'workflow w1 is running inside this session (export const meta)'])

    def test_git_mid_merge_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            subprocess.run(['git', 'init', '-q', tmp], check=True)
            self.assertEqual(relaylib.blockers(tmp, []), [])
            (Path(tmp) / '.git' / 'MERGE_HEAD').write_text('0' * 40 + '\n')
            self.assertEqual(relaylib.blockers(tmp, []), ['git is mid-operation (MERGE_HEAD present)'])


class RelaysOfTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.project = Path(self.tmp.name) / 'proj'

    def tearDown(self):
        self.tmp.cleanup()

    def states(self):
        return {r['id']: r['state'] for r in relaylib.relays_of(str(self.project), SID)}

    def test_each_dir_is_classified_by_fact(self):
        make_relay(self.project, 'R1', files=['launch.json', ('failed.json', {'stage': 'receipt'}), 'closed.json'])
        make_relay(self.project, 'R2', files=['launch.json', ('failed.json', {'stage': 'launch', 'reason': 'x'})])
        make_relay(self.project, 'R3', files=['launch.json', 'receipt.json', 'handover.md'])
        make_relay(self.project, 'R4', files=['launch.json'], age=24 * 60)
        make_relay(self.project, 'R5', files=['launch.json'], age=26 * 60)
        self.assertEqual(self.states(), {'R1': 'closed', 'R2': 'failed', 'R3': 'frozen', 'R4': 'in_progress',
                                         'R5': 'abandoned'})

    def test_fresh_fix_and_fired_files_keep_an_old_relay_in_progress(self):
        old = make_relay(self.project, 'R1', files=['launch.json', 'receipt.json'], age=40 * 60)
        (old / 'fix-1').write_text('')
        make_relay(self.project, 'R2', files=['launch.json'], age=40 * 60)
        fired = self.project / 'relay' / 'R2' / 'fired'
        fired.mkdir()
        (fired / 'relay-R2-w1').write_text('')
        self.assertEqual(self.states(), {'R1': 'in_progress', 'R2': 'in_progress'})

    def test_failure_time_is_the_failed_json_mtime_and_its_fields_are_read(self):
        make_relay(self.project, 'R1', files=[('failed.json', {'stage': 'check', 'reason': 'FAIL identity: x',
                                                                'at': '2026-10-13T10:15:27'})], age=600)
        [entry] = relaylib.relays_of(str(self.project), SID)
        self.assertAlmostEqual(entry['failed_at'], time.time() - 600, delta=5)
        self.assertEqual((entry['stage'], entry['reason']), ('check', 'FAIL identity: x'))

    def test_an_abandoned_dir_failed_at_its_last_activity(self):
        make_relay(self.project, 'R1', files=['launch.json'], age=30 * 60)
        [entry] = relaylib.relays_of(str(self.project), SID)
        self.assertEqual(entry['state'], 'abandoned')
        self.assertAlmostEqual(entry['failed_at'], time.time() - 30 * 60, delta=5)

    def test_other_sessions_gate_state_and_unreadable_checklists_are_ignored(self):
        make_relay(self.project, 'R1', session='someone-else', files=['launch.json'])
        gate = self.project / 'relay' / 'gate'
        gate.mkdir(parents=True)
        (gate / (SID + '.json')).write_text('{}')
        (self.project / 'relay' / 'lead.json').write_text(json.dumps({'session_id': SID}))
        bad = self.project / 'relay' / 'R2'
        bad.mkdir()
        (bad / 'checklist.json').write_text('{torn')
        self.assertEqual(relaylib.relays_of(str(self.project), SID), [])

    def test_a_torn_failed_json_is_still_a_failure(self):
        make_relay(self.project, 'R1', files=[('failed.json', '{"stage": "rec')])
        [entry] = relaylib.relays_of(str(self.project), SID)
        self.assertEqual((entry['state'], entry['stage'], entry['reason']), ('failed', None, None))

    def test_no_relay_dir_at_all(self):
        self.assertEqual(relaylib.relays_of(str(self.project), SID), [])


class WillRepeatTests(unittest.TestCase):
    def test_identity_at_the_check_and_a_taken_name_repeat(self):
        self.assertTrue(relaylib.will_repeat({'stage': 'check', 'reason': "FAIL identity: successor "
                                                                          "permission_mode 'default'"}))
        self.assertTrue(relaylib.will_repeat({'stage': 'launch', 'reason': 'agent start: agent_name_taken'}))

    def test_other_failures_do_not(self):
        self.assertFalse(relaylib.will_repeat({'stage': 'receipt', 'reason': 'successor=gone receipt=none'}))
        self.assertFalse(relaylib.will_repeat({'stage': 'launch', 'reason': 'identity: x'}))
        self.assertFalse(relaylib.will_repeat({'stage': None, 'reason': None}))


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `python3 -m unittest discover -s tests -p test_relaylib.py -v`
Expected: FAIL, output contains `No module named 'relaylib'`

- [ ] **Step 3: Write the module and move `blockers()` into it**

Create `private_dot_claude/skills/session-handoff/scripts/relaylib.py`:

```python
"""Relay facts shared by relay-check.py and relay-gate.py: the safe-point blockers and this session's relays.

Stdlib only. The CLIs run under `python3 -I` and put this directory on sys.path before importing it.
"""
import glob
import json
import os
import subprocess
import time

GIT_BUSY = ('MERGE_HEAD', 'CHERRY_PICK_HEAD', 'REVERT_HEAD', 'rebase-merge', 'rebase-apply')
# Piece 1 waits at most 20 minutes for a receipt and 15 per fix round, and each wait starts from a fresh file
# (launch.json, fix-<round>): a relay dir with no activity for longer is abandoned.
ABANDONED_AFTER = 25 * 60
ACTIVITY = ('checklist.json', 'launch.json', 'receipt.json', 'fix-*', 'fired/*')


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, r.stdout.strip()


def blockers(repo, tasks):
    """Why a relay may not start now: an agent or workflow running inside this session (tasks are
    transcript.open_tasks records), or the repo mid-merge, rebase, cherry-pick or revert."""
    out = ['%s %s is running inside this session (%s)' % (t['kind'], t['id'], t['description'] or t['command'][:60])
           for t in tasks if t['kind'] in ('agent', 'workflow')]
    code, gitdir = run(['git', '-C', repo, 'rev-parse', '--absolute-git-dir'])
    if code == 0:
        out += ['git is mid-operation (%s present)' % name for name in GIT_BUSY
                if os.path.exists(os.path.join(gitdir, name))]
    return out


def read_json(path):
    with open(path) as fh:
        return json.load(fh)


def _mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return None


def _failure(path):
    """stage and reason of a failed.json; an unreadable one is a failure with neither."""
    try:
        data = read_json(path)
    except (OSError, ValueError):
        data = None
    data = data if isinstance(data, dict) else {}
    stage, reason = data.get('stage'), data.get('reason')
    return (stage if isinstance(stage, str) else None), (reason if isinstance(reason, str) else None)


def classify(rdir, now):
    """One relay dir, by fact: closed, failed, abandoned, frozen or in_progress.

    A later closed.json supersedes a failed.json. The failure time is failed.json's mtime (both writers make one;
    its `at` field is free-form and never parsed), or the last activity of an abandoned dir."""
    entry = {'id': os.path.basename(rdir), 'dir': rdir, 'state': None, 'stage': None, 'reason': None,
             'failed_at': None, 'handover_at': None}
    failed = os.path.join(rdir, 'failed.json')
    handover = os.path.join(rdir, 'handover.md')
    if os.path.exists(os.path.join(rdir, 'closed.json')):
        entry['state'] = 'closed'
    elif os.path.exists(failed):
        entry['state'], entry['failed_at'] = 'failed', _mtime(failed)
        entry['stage'], entry['reason'] = _failure(failed)
    elif os.path.exists(handover):
        entry['state'], entry['handover_at'] = 'frozen', _mtime(handover)
    else:
        times = [t for pattern in ACTIVITY for path in glob.glob(os.path.join(glob.escape(rdir), pattern))
                 if (t := _mtime(path)) is not None]
        newest = max(times) if times else None
        if newest is None or now - newest >= ABANDONED_AFTER:
            entry['state'], entry['failed_at'] = 'abandoned', newest if newest is not None else now
        else:
            entry['state'] = 'in_progress'
    return entry


def relays_of(project_dir, session_id, now=None):
    """The relay dirs under <project_dir>/relay/ whose checklist names this session as the predecessor."""
    now = time.time() if now is None else now
    out = []
    for path in sorted(glob.glob(os.path.join(glob.escape(project_dir), 'relay', '*', 'checklist.json'))):
        try:
            chk = read_json(path)
        except (OSError, ValueError):
            continue
        pred = chk.get('predecessor') if isinstance(chk, dict) else None
        if isinstance(pred, dict) and pred.get('session_id') == session_id:
            out.append(classify(os.path.dirname(path), now))
    return out


def will_repeat(entry):
    """A failure an automatic retry would meet again: an identity mismatch at the check, or a taken agent name."""
    reason = entry.get('reason') or ''
    return 'agent_name_taken' in reason or (entry.get('stage') == 'check' and 'identity:' in reason)
```

In `private_dot_claude/skills/session-handoff/scripts/relay-check.py`, replace:

```python
import transcript  # noqa: E402
```

with:

```python
import relaylib  # noqa: E402
import transcript  # noqa: E402
```

In `private_dot_claude/skills/session-handoff/scripts/relay-check.py`, replace:

```python
NAME_ROOM = 32 - len('lead-') - len('-next')   # herdr names are at most 32 characters
GIT_BUSY = ('MERGE_HEAD', 'CHERRY_PICK_HEAD', 'REVERT_HEAD', 'rebase-merge', 'rebase-apply')
```

with:

```python
NAME_ROOM = 32 - len('lead-') - len('-next')   # herdr names are at most 32 characters
```

In `private_dot_claude/skills/session-handoff/scripts/relay-check.py`, replace:

```python
def blockers(repo, tasks):
    out = ['%s %s is running inside this session (%s)' % (t['kind'], t['id'], t['description'] or t['command'][:60])
           for t in tasks if t['kind'] in ('agent', 'workflow')]
    code, gitdir = run(['git', '-C', repo, 'rev-parse', '--absolute-git-dir'])
    if code == 0:
        out += ['git is mid-operation (%s present)' % name for name in GIT_BUSY
                if os.path.exists(os.path.join(gitdir, name))]
    return out


def workers(repo, extra_roots, self_pane):
```

with:

```python
def workers(repo, extra_roots, self_pane):
```

In `private_dot_claude/skills/session-handoff/scripts/relay-check.py`, replace:

```python
    blocked = blockers(repo, tasks)
```

with:

```python
    blocked = relaylib.blockers(repo, tasks)
```

- [ ] **Step 4: Run the tests to make sure they pass**

Run: `python3 -m unittest discover -s tests -p test_relaylib.py -v`
Expected: PASS

Run: `python3 -m unittest discover -s tests -p test_handoff_relay_check.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add private_dot_claude/skills/session-handoff/scripts/relaylib.py private_dot_claude/skills/session-handoff/scripts/relay-check.py tests/test_relaylib.py
git commit -m "relay-gate: relaylib with the shared blockers and this session's relays"
```

### Task 2: The meter: `transcript.context_fill()`

**Files:**
- Modify: `private_dot_claude/skills/session-handoff/scripts/transcript.py` (module docstring, constants, a new function before `permission_mode`)
- Modify: `tests/handoff_fixtures.py` (a `usage()` fixture)
- Test: `tests/test_handoff_transcript.py` (a `ContextFillTests` class)

**Interfaces:**
- Consumes: `transcript.records(path)`.
- Produces:
  - `transcript.WINDOWS: dict[str, int]`, `transcript.FILL_KEYS: tuple[str, ...]`.
  - `transcript.context_fill(path: str, window: int | None = None) -> {'pct': float, 'tokens': int, 'model': str} | None`.
  - `handoff_fixtures.usage(message_tokens, second=0, model='claude-opus-5-5', advisor=False, sidechain=False) -> dict`: a main-thread assistant record whose context (last `message` iteration) is `message_tokens`.

- [ ] **Step 1: Write the failing tests**

The fixture first:

In `tests/handoff_fixtures.py`, replace:

```python
def _notice_text(task_id, status, payload=None):
```

with:

```python
def usage(message_tokens, second=0, model='claude-opus-5-5', advisor=False, sidechain=False):
    """A main-thread assistant record carrying usage as Claude Code 2.1.296 writes it.

    message_tokens: the context of the final API call (input + cache_read + cache_creation of the last
    `message` iteration). advisor=True adds an earlier `message` iteration and an `advisor_message` one, as an
    advisor turn does, so the top-level usage (the sum of the message iterations) reads about twice the context."""
    last = {'type': 'message', 'input_tokens': 2, 'cache_read_input_tokens': message_tokens - 1002,
            'cache_creation_input_tokens': 1000, 'output_tokens': 50}
    steps = [last]
    if advisor:
        steps = [dict(last, cache_read_input_tokens=message_tokens - 3002),
                 {'type': 'advisor_message', 'input_tokens': 91782, 'cache_read_input_tokens': 0,
                  'cache_creation_input_tokens': 0, 'output_tokens': 4394}, last]
    top = {k: sum(s[k] for s in steps if s['type'] == 'message')
           for k in ('input_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens', 'output_tokens')}
    return {'type': 'assistant', 'timestamp': ts(second), 'isSidechain': sidechain,
            'message': {'model': model, 'content': [], 'usage': dict(top, iterations=steps)}}


def _notice_text(task_id, status, payload=None):
```

Then the tests:

In `tests/test_handoff_transcript.py`, replace:

```python
import tempfile
import unittest
```

with:

```python
import tempfile
import time
import unittest
```

In `tests/test_handoff_transcript.py`, replace:

```python
from handoff_fixtures import (SCRIPTS, SOURCE, cron_create, cron_delete, monitor_event, notice, prompt,
                              queued_notice, tool_result, tool_use, ts, write_transcript)
```

with:

```python
from handoff_fixtures import (SCRIPTS, SOURCE, cron_create, cron_delete, monitor_event, notice, prompt,
                              queued_notice, tool_result, tool_use, ts, usage, write_transcript)
```

In `tests/test_handoff_transcript.py`, replace:

```python
class ChezmoiPackagingTests(unittest.TestCase):
```

with:

```python
class ContextFillTests(unittest.TestCase):
    def fill(self, recs, window=None):
        with tempfile.TemporaryDirectory() as tmp:
            return transcript.context_fill(str(write_transcript(tmp, SID, recs)), window)

    def test_the_newest_main_thread_record_decides(self):
        got = self.fill([usage(100_000, 1), usage(520_000, 2), usage(900_000, 3, sidechain=True)])
        self.assertEqual(got, {'pct': 52.0, 'tokens': 520_000, 'model': 'claude-opus-5-5'})

    def test_an_advisor_turn_reads_the_last_message_iteration_not_the_doubled_top_level(self):
        rec = usage(292_000, 1, advisor=True)
        top = rec['message']['usage']
        self.assertGreater(sum(top[k] for k in transcript.FILL_KEYS), 570_000)
        self.assertAlmostEqual(self.fill([rec])['pct'], 29.2)

    def test_no_iterations_falls_back_to_the_top_level(self):
        rec = usage(300_000, 1)
        del rec['message']['usage']['iterations']
        self.assertAlmostEqual(self.fill([rec])['pct'], 30.0)

    def test_synthetic_and_unknown_models(self):
        synthetic = usage(990_000, 2, model='<synthetic>')
        self.assertAlmostEqual(self.fill([usage(400_000, 1), synthetic])['pct'], 40.0)
        self.assertIsNone(self.fill([usage(400_000, 1, model='claude-sonnet-5-5')]))
        self.assertAlmostEqual(self.fill([usage(100_000, 1, model='claude-sonnet-5-5')], window=200_000)['pct'],
                               50.0)

    def test_a_10_mb_transcript_is_read_well_inside_the_stop_budget(self):
        filler = [prompt('x' * 2000, n % 3000) for n in range(5000)]
        started = time.time()
        got = self.fill(filler + [usage(520_000, 9)])
        self.assertLess(time.time() - started, 2.0)
        self.assertEqual(got['tokens'], 520_000)

    def test_no_usage_yet(self):
        self.assertIsNone(self.fill([prompt('hi', 1), tool_use('t1', 'Bash', {'command': 'ls'}, 2)]))


class ChezmoiPackagingTests(unittest.TestCase):
```

- [ ] **Step 2: Run them to make sure they fail**

Run: `python3 -m unittest discover -s tests -p test_handoff_transcript.py -v`
Expected: FAIL, output contains `module 'transcript' has no attribute`

- [ ] **Step 3: Write the meter**

In `private_dot_claude/skills/session-handoff/scripts/transcript.py`, replace:

```python
  carries an error string instead.
"""
```

with:

```python
  carries an error string instead.
- Context fill is read from the newest main-thread assistant record's last
  `usage.iterations` entry of type `message`: input + cache_read +
  cache_creation. The top-level usage sums every iteration, so an advisor turn
  counts the context twice (57.9% shown for 29.2% real, 2026-10-12).
"""
```

In `private_dot_claude/skills/session-handoff/scripts/transcript.py`, replace:

```python
TERMINAL = frozenset({'completed', 'failed', 'killed', 'stopped'})
```

with:

```python
TERMINAL = frozenset({'completed', 'failed', 'killed', 'stopped'})
# Context window per model id, in tokens: only measured ones. An unknown model has no fill.
WINDOWS = {'claude-opus-5-5': 1_000_000}
FILL_KEYS = ('input_tokens', 'cache_read_input_tokens', 'cache_creation_input_tokens')
```

In `private_dot_claude/skills/session-handoff/scripts/transcript.py`, replace:

```python
def permission_mode(path):
```

with:

```python
def context_fill(path, window=None):
    """How full the session's context is: {'pct', 'tokens', 'model'}, or None.

    None when no main-thread assistant record carries usage, or the window is unknown. window (tokens)
    overrides WINDOWS; the relay gate passes RELAY_GATE_WINDOW."""
    last = None
    for _, rec in records(path):
        if rec.get('type') == 'assistant' and not rec.get('isSidechain'):
            msg = rec.get('message') or {}
            model = msg.get('model')
            if isinstance(msg.get('usage'), dict) and isinstance(model, str) and model and not model.startswith('<'):
                last = msg
    if last is None:
        return None
    usage = last['usage']
    steps = [i for i in usage.get('iterations') or [] if isinstance(i, dict) and i.get('type') == 'message']
    source = steps[-1] if steps else usage
    tokens = sum(v for v in (source.get(k) for k in FILL_KEYS) if isinstance(v, int) and not isinstance(v, bool))
    size = window or WINDOWS.get(last['model'])
    if not size:
        return None
    return {'pct': 100.0 * tokens / size, 'tokens': tokens, 'model': last['model']}


def permission_mode(path):
```

- [ ] **Step 4: Run the tests to make sure they pass**

Run: `python3 -m unittest discover -s tests -p test_handoff_transcript.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add private_dot_claude/skills/session-handoff/scripts/transcript.py tests/handoff_fixtures.py tests/test_handoff_transcript.py
git commit -m "relay-gate: the context meter (last message iteration over a known window)"
```

### Task 3: relay-gate.py: identity, state and failing open

**Files:**
- Create: `private_dot_claude/skills/session-handoff/scripts/relay-gate.py`
- Test: `tests/test_relay_gate.py`

This task builds everything but the decisions: `decide()` asks unconditionally and `tool()` does nothing. Tasks 4 and 5 replace those two functions whole.

**Interfaces:**
- Consumes: `transcript.context_fill`, `transcript.last_model`, `transcript.WINDOWS` (Task 2); `relaylib.read_json` (Task 1).
- Produces (names Tasks 4 and 5 use):
  - `Config(env)` with `.threshold .cap .step .backoff .throttle .owner .window` (`.owner`: the owner-conversation window, 600 s, test override `RELAY_GATE_OWNER_S`; see the plan's deviation note).
  - `band_of(pct, cfg) -> int | float`, `fresh() -> dict`, `load_state(path) -> dict`, `save_state(path, state)`, `reset_bands(state, pct, cfg) -> bool`, `utc_now() -> str`.
  - `Call(inp, cfg, clock, now)` with `.inp .cfg .clock .now .session .transcript .project .state_path .pane .label .toasts`, `.lead() -> bool` and `.alert(text, then) -> dict` (records a toast, returns the Stop block asking for a push).
  - `HERDR_BOUND`, `HANDOVER_ALERT_AFTER`, `OWNER_RECENT`, `MAX_ASKS`.
  - `stop(call)` computes the fill, identity and state, then calls `decide(call, state, pct, band) -> dict | None` and saves; `main(argv) -> int`.
  - Tests: `GateCase` (`make_lead()`, `at(pct, *before)`, `gate(mode, tasks, env, **fields)`, `state()`, `toasts(expect)`, `assertAsk(out, attempt)`), `shell()`, `iso()`, `load_gate()`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_relay_gate.py`:

```python
import datetime
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock
import uuid

from handoff_fixtures import (SCRIPTS, agent_json, herdr_calls, herdr_stub, prompt, tool_result, tool_use, usage,
                              write_transcript)
from test_relaylib import make_relay

GATE = SCRIPTS / 'relay-gate.py'
SID = '55555555-5555-4555-8555-555555555555'


def load_gate():
    spec = importlib.util.spec_from_file_location('relay_gate', GATE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def iso(seconds_ago):
    when = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=seconds_ago)
    return when.isoformat().replace('+00:00', 'Z')


def shell(tid, desc='Wait for r', status='running'):
    return {'id': tid, 'type': 'shell', 'status': status, 'description': desc, 'command': 'until [ -f r ]; do sleep 5; done'}


def git_repo(root):
    repo = Path(root) / 'repo'
    repo.mkdir()
    subprocess.run(['git', 'init', '-q', str(repo)], check=True)
    return Path(os.path.realpath(repo))


class GateCase(unittest.TestCase):
    """A project dir under a fake ~/.claude/projects, a git repo as cwd, and a fake herdr."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.home = root / 'home'
        self.home.mkdir()
        self.projects = root / 'projects'
        self.project = self.projects / '-tmp-repo'
        self.project.mkdir(parents=True)
        self.repo = git_repo(root)
        self.recs = [usage(100_000, 1)]
        self.herd({'agent get': [{'out': agent_json('idle', pane='wT:p1', name='worker-high')}]})
        self.extra_env = {}

    def tearDown(self):
        self.tmp.cleanup()

    def herd(self, responses):
        self.env, self.log = herdr_stub(self.tmp.name, responses)
        self.env = {k: v for k, v in self.env.items() if not k.startswith('RELAY_GATE_')}
        self.env['HOME'] = str(self.home)

    def make_lead(self):
        (self.project / 'relay').mkdir(exist_ok=True)
        (self.project / 'relay' / 'lead.json').write_text(json.dumps({'session_id': SID, 'name': 'lead-repo'}))

    def at(self, pct, *before):
        """The transcript: `before` records, then a main-thread usage record at pct of a 1M window."""
        self.recs = list(before) + [usage(int(pct * 10_000), 50)]

    def gate(self, mode='stop', tasks=(), env=None, **fields):
        path = write_transcript(self.projects, SID, self.recs)
        inp = {'session_id': SID, 'transcript_path': str(path), 'cwd': str(self.repo),
               'hook_event_name': 'Stop' if mode == 'stop' else 'PostToolUse', 'prompt_id': str(uuid.uuid4()),
               'background_tasks': list(tasks), 'stop_hook_active': False}
        if mode == 'tool':
            inp.update(tool_name='Bash', tool_input={'command': 'ls'})
            del inp['background_tasks'], inp['stop_hook_active']
        inp.update(fields)
        inp = {k: v for k, v in inp.items() if v is not None}
        run_env = dict(self.env)
        run_env.update(self.extra_env)
        run_env.update(env or {})
        r = subprocess.run(['python3', '-I', str(GATE), mode], input=json.dumps(inp), capture_output=True, text=True,
                           env=run_env, timeout=30)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout) if r.stdout.strip() else None

    def state(self):
        path = self.project / 'relay' / 'gate' / (SID + '.json')
        return json.loads(path.read_text()) if path.exists() else None

    def toasts(self, expect, wait=3.0):
        """The toasts raised so far: they are detached, so wait until `expect` arrived, then a little longer."""
        end = time.time() + wait
        while time.time() < end:
            got = [c for c in herdr_calls(self.log) if c[:2] == ['notification', 'show']]
            if len(got) >= expect:
                break
            time.sleep(0.05)
        time.sleep(0.3)
        return [c for c in herdr_calls(self.log) if c[:2] == ['notification', 'show']]

    def assertAsk(self, out, attempt=1):
        self.assertIsNotNone(out)
        self.assertEqual(out['decision'], 'block')
        self.assertIn('Run /relay now, automatic relay attempt %d of 2.' % attempt, out['reason'])


class IdentityTests(GateCase):
    def test_outside_herdr_nothing_happens(self):
        self.make_lead()
        self.at(52)
        env = {k: v for k, v in self.env.items() if k != 'HERDR_ENV'}
        self.env = env
        self.assertIsNone(self.gate())
        self.assertIsNone(self.state())

    def test_a_subagent_or_teammate_is_never_gated(self):
        self.make_lead()
        self.at(52)
        for agent in ('ac8338d111984a8ec', 'aprobe-teammate-e833e05d3a936ff6'):
            self.assertIsNone(self.gate('tool', agent_id=agent, agent_type='general-purpose'))
        self.assertIsNone(self.state())

    def test_the_child_session_flag_does_not_exempt_the_lead(self):
        self.make_lead()
        self.at(52)
        self.assertAsk(self.gate(env={'CLAUDE_CODE_CHILD_SESSION': '1'}))

    def test_lead_json_is_a_fast_path_with_no_herdr_call(self):
        self.make_lead()
        self.at(52)
        self.assertAsk(self.gate())
        self.assertEqual([c for c in herdr_calls(self.log) if c[:2] == ['agent', 'get']], [])

    def test_a_lead_name_is_gated(self):
        self.herd({'agent get': [{'out': agent_json('idle', pane='wT:p1', name='lead-repo')}]})
        self.at(52)
        self.assertAsk(self.gate())
        self.assertEqual(self.state()['asked']['band'], 50)

    def test_a_worker_is_never_gated_and_gets_no_state(self):
        self.at(52)
        self.assertIsNone(self.gate())
        self.assertIsNone(self.gate('tool'))
        self.assertFalse((self.project / 'relay').exists())

    def test_an_input_without_a_transcript_or_session_is_ignored(self):
        self.make_lead()
        self.at(52)
        self.assertIsNone(self.gate(transcript_path=None))
        self.assertIsNone(self.gate(session_id=None))
        self.assertFalse((self.project / 'relay' / 'gate').exists())

    def test_below_the_threshold_nothing_is_read_or_written(self):
        self.at(49.9)
        self.assertIsNone(self.gate())
        self.assertEqual(herdr_calls(self.log), [])
        self.assertFalse((self.project / 'relay').exists())

    def test_an_unknown_model_toasts_a_lead_once_and_stays_inert(self):
        self.make_lead()
        self.recs = [usage(600_000, 1, model='claude-sonnet-5-5')]
        self.assertIsNone(self.gate())
        self.assertIsNone(self.gate())
        toasts = self.toasts(1)
        self.assertEqual(len(toasts), 1, toasts)
        self.assertIn('claude-sonnet-5-5', ' '.join(toasts[0]))
        self.assertEqual(self.state()['toasted'], ['unknown-model'])

    def test_an_unknown_model_on_a_worker_is_silent(self):
        self.recs = [usage(600_000, 1, model='claude-sonnet-5-5')]
        self.assertIsNone(self.gate())
        self.assertEqual(self.toasts(0, wait=0.2), [])


class StateTests(GateCase):
    def test_a_wrong_shaped_state_is_a_fresh_one(self):
        self.make_lead()
        self.at(52)
        gate_dir = self.project / 'relay' / 'gate'
        gate_dir.mkdir(parents=True)
        (gate_dir / (SID + '.json')).write_text(json.dumps({'version': 1, 'nudged': 'fifty',
                                                            'asked': {'band': 50, 'attempt': 1, 'tasks': [],
                                                                      'count': 3}}))
        self.assertAsk(self.gate())
        self.assertEqual(self.state()['asked']['count'], 1)

    def test_the_state_is_written_whole_and_no_temp_file_is_left(self):
        self.make_lead()
        self.at(52)
        self.gate()
        state = self.state()
        self.assertEqual((state['version'], state['meter']['pct']), (1, 52.0))
        self.assertEqual(sorted(p.name for p in (self.project / 'relay' / 'gate').iterdir()), [SID + '.json'])

    def test_other_sessions_old_state_files_are_pruned(self):
        self.make_lead()
        self.at(52)
        gate_dir = self.project / 'relay' / 'gate'
        gate_dir.mkdir(parents=True)
        old, recent = gate_dir / 'old-session.json', gate_dir / 'recent-session.json'
        for path in (old, recent):
            path.write_text('{}')
        week = time.time() - 8 * 24 * 3600
        os.utime(old, (week, week))
        self.gate()
        self.assertFalse(old.exists())
        self.assertTrue(recent.exists())

    def test_bands_follow_the_threshold(self):
        gate = load_gate()
        cfg = gate.Config({'RELAY_GATE_THRESHOLD': '7', 'RELAY_GATE_STEP': '1'})
        self.assertEqual([gate.band_of(p, cfg) for p in (7.0, 7.9, 8.2, 10.5)], [7, 7, 8, 10])
        cfg = gate.Config({})
        self.assertEqual([gate.band_of(p, cfg) for p in (50.0, 59.9, 60.0, 83.8)], [50, 50, 60, 80])
        self.assertEqual((cfg.threshold, cfg.cap, cfg.step, cfg.backoff, cfg.throttle, cfg.owner, cfg.window),
                         (50, 60, 10, 1800, 60, 600, None))
        self.assertEqual(gate.Config({'RELAY_GATE_STEP': '0', 'RELAY_GATE_CAP': 'x'}).step, 10)

class FailOpenTests(GateCase):
    def test_garbage_input_is_logged_and_toasted_once(self):
        for _ in range(2):
            r = subprocess.run(['python3', '-I', str(GATE), 'stop'], input='{torn', capture_output=True, text=True,
                               env=self.env, timeout=30)
            self.assertEqual((r.returncode, r.stdout), (0, ''))
        log = (self.home / '.claude' / 'relay-gate-errors.log').read_text()
        self.assertEqual(log.count('== '), 2)
        self.assertIn('JSONDecodeError', log)
        self.assertTrue((self.home / '.claude' / 'relay-gate-unknown.error').exists())
        self.assertEqual(len(self.toasts(1)), 1)

    def test_a_raising_helper_is_logged_beside_the_project(self):
        self.make_lead()
        broken = self.project / ('%s.jsonl' % SID)
        broken.mkdir()
        inp = {'session_id': SID, 'transcript_path': str(broken), 'cwd': str(self.repo), 'background_tasks': []}
        r = subprocess.run(['python3', '-I', str(GATE), 'stop'], input=json.dumps(inp), capture_output=True,
                           text=True, env=self.env, timeout=30)
        self.assertEqual((r.returncode, r.stdout), (0, ''))
        gate_dir = self.project / 'relay' / 'gate'
        self.assertIn('IsADirectoryError', (gate_dir / 'errors.log').read_text())
        self.assertTrue((gate_dir / (SID + '.error')).exists())
        self.assertEqual(len(self.toasts(1)), 1)

    def test_the_error_log_is_trimmed(self):
        log = self.home / '.claude' / 'relay-gate-errors.log'
        log.parent.mkdir()
        log.write_text('x' * 150_000)
        subprocess.run(['python3', '-I', str(GATE), 'stop'], input='[]', capture_output=True, text=True,
                       env=self.env, timeout=30)
        self.assertLessEqual(log.stat().st_size, 100 * 1024)
        self.assertIn('not a JSON object', log.read_text())

    def test_a_usage_error_never_exits_2(self):
        r = subprocess.run(['python3', '-I', str(GATE)], input='{}', capture_output=True, text=True, env=self.env)
        self.assertEqual(r.returncode, 1)

    def test_the_toast_is_detached_and_its_failure_changes_nothing(self):
        self.herd({'notification show': [{'out': 'boom', 'code': 1, 'sleep': 3}]})
        self.make_lead()
        self.recs = [usage(600_000, 1, model='claude-sonnet-5-5')]
        started = time.time()
        self.assertIsNone(self.gate())
        self.assertLess(time.time() - started, 2.5)
        self.assertEqual(self.state()['toasted'], ['unknown-model'])

    def test_the_state_is_written_before_the_output(self):
        gate = load_gate()
        self.make_lead()
        self.at(52)
        path = write_transcript(self.projects, SID, self.recs)
        state_path = self.project / 'relay' / 'gate' / (SID + '.json')
        seen = []

        class Out(io.StringIO):
            def write(self, text):
                seen.append(state_path.exists() and json.loads(state_path.read_text())['asked'] is not None)
                return super().write(text)

        inp = json.dumps({'session_id': SID, 'transcript_path': str(path), 'cwd': str(self.repo),
                          'background_tasks': []})
        with mock.patch.dict(os.environ, self.env, clear=True), mock.patch.object(sys, 'stdin', io.StringIO(inp)), \
                mock.patch.object(sys, 'stdout', Out()):
            self.assertEqual(gate.main(['stop']), 0)
        self.assertEqual(seen, [True])


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run them to make sure they fail**

Run: `python3 -m unittest discover -s tests -p test_relay_gate.py -v`
Expected: FAIL, output contains `can't open file`

- [ ] **Step 3: Write the hook**

Create `private_dot_claude/skills/session-handoff/scripts/relay-gate.py`:

```python
#!/usr/bin/env python3
"""Relay gate: fire /relay when a herdr lead reaches 50% context. A Claude Code hook.

  stop   Stop hook: at the first safe turn end at or above the threshold, block with "run /relay now"
  tool   PostToolUse hook: once per band, tell the lead a relay is due

Reads the hook's JSON on stdin and prints a hook decision, or nothing. It never fails closed: an error is
logged to <project>/relay/gate/errors.log, toasted once per session, and the call exits 0 with no output.
Only a lead (herdr name lead-*, or the session in <project>/relay/lead.json) is gated, and only a lead gets
a state file, <project>/relay/gate/<session-id>.json. Design: docs/superpowers/specs/2026-10-13-relay-gate-design.md.

Test-only overrides: RELAY_GATE_THRESHOLD, RELAY_GATE_CAP, RELAY_GATE_STEP, RELAY_GATE_BACKOFF_S,
RELAY_GATE_THROTTLE_S, RELAY_GATE_OWNER_S, RELAY_GATE_WINDOW (tokens).
"""
import datetime
import glob
import json
import math
import os
import subprocess
import sys
import time
import traceback

# In development this dir is chezmoi source: bytecode written beside the script would be deployed.
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import relaylib  # noqa: E402
import transcript  # noqa: E402

HERDR_BOUND = 2            # seconds, any one herdr call
BUDGET = {'stop': 7, 'tool': 3}   # seconds of gathering, inside the 10 s and 5 s hook timeouts
PRUNE_AFTER = 7 * 24 * 3600
LOG_KEEP = 100 * 1024
HANDOVER_ALERT_AFTER = 30 * 60
OWNER_RECENT = 10 * 60
MAX_ASKS = 3
STATE_TYPES = {'version': int, 'meter': (dict, type(None)), 'nudged': list, 'drain_owed': bool, 'alerted': list,
               'asked': (dict, type(None)), 'given_up': bool, 'handover_alerted': list, 'toasted': list}


class Late(Exception):
    """The call ran past its budget: exit silently and let the next call decide."""


class Config:
    def __init__(self, env):
        self.threshold = number(env, 'RELAY_GATE_THRESHOLD', 50)
        self.cap = number(env, 'RELAY_GATE_CAP', 60)
        self.step = number(env, 'RELAY_GATE_STEP', 10)
        self.backoff = number(env, 'RELAY_GATE_BACKOFF_S', 1800)
        self.throttle = number(env, 'RELAY_GATE_THROTTLE_S', 60)
        self.owner = number(env, 'RELAY_GATE_OWNER_S', OWNER_RECENT)
        self.window = int(number(env, 'RELAY_GATE_WINDOW', 0)) or None


def number(env, name, default):
    """A positive number from the environment (an int when whole), else the default."""
    try:
        value = float(env.get(name, ''))
    except ValueError:
        return default
    if not value > 0 or math.isinf(value):
        return default
    return int(value) if value.is_integer() else value


class Clock:
    def __init__(self, budget):
        self.end = time.monotonic() + budget

    def left(self, cap):
        """Seconds a call may take: at most cap; Late once the budget is spent."""
        remaining = self.end - time.monotonic()
        if remaining <= 0:
            raise Late()
        return min(cap, remaining)


def utc_now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace('+00:00', 'Z')


def band_of(pct, cfg):
    """The band of a fill at or above the threshold: T + S * floor((F - T) / S)."""
    band = cfg.threshold + cfg.step * math.floor((pct - cfg.threshold) / cfg.step)
    return int(band) if float(band).is_integer() else band


def fresh():
    return {'version': 1, 'meter': None, 'nudged': [], 'drain_owed': False, 'alerted': [], 'asked': None,
            'given_up': False, 'handover_alerted': [], 'toasted': []}


def _shape_ok(state):
    for key, kind in STATE_TYPES.items():
        if not isinstance(state[key], kind) or (kind is int and isinstance(state[key], bool)):
            return False
    meter, asked = state['meter'], state['asked']
    if meter is not None and not (isinstance(meter.get('pct'), (int, float)) and isinstance(meter.get('read_at'), str)):
        return False
    if asked is not None and not (isinstance(asked.get('band'), (int, float)) and isinstance(asked.get('attempt'), int)
                                  and isinstance(asked.get('tasks'), list) and isinstance(asked.get('count'), int)):
        return False
    return all(isinstance(b, (int, float)) for b in state['nudged'] + state['alerted'])


def load_state(path):
    """The state at path; a missing, unreadable or wrong-shaped file is a fresh state."""
    try:
        data = relaylib.read_json(path)
    except (OSError, ValueError):
        return fresh()
    if not isinstance(data, dict) or data.get('version') != 1:
        return fresh()
    state = dict(fresh(), **{k: v for k, v in data.items() if k in STATE_TYPES})
    return state if _shape_ok(state) else fresh()


def save_state(path, state):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = '%s.tmp.%d' % (path, os.getpid())
    with open(tmp, 'w') as fh:
        json.dump(state, fh)
    os.replace(tmp, path)


def prune(gate_dir, keep, now):
    """Remove other sessions' state files untouched for 7 days."""
    for path in glob.glob(os.path.join(glob.escape(gate_dir), '*.json')):
        if path != keep:
            try:
                if now - os.path.getmtime(path) > PRUNE_AFTER:
                    os.remove(path)
            except OSError:
                pass


def reset_bands(state, pct, cfg):
    """Forget the bands of a fuller context once the fill drops more than a step below them (a compaction)."""
    bands = state['nudged'] + state['alerted'] + ([state['asked']['band']] if state['asked'] else [])
    if bands and pct < min(bands) - cfg.step:
        state.update(nudged=[], alerted=[], asked=None, drain_owed=False)
        return True
    return False


def herdr_name(pane, timeout):
    """The herdr name of the agent in pane, or None (no agent, no name, herdr failed or slow)."""
    try:
        r = subprocess.run(['herdr', 'agent', 'get', pane], capture_output=True, text=True, timeout=timeout)
        agent = (json.loads(r.stdout).get('result') or {}).get('agent') or {} if r.returncode == 0 else {}
    except (OSError, ValueError, AttributeError, subprocess.TimeoutExpired):
        return None
    name = agent.get('name') if isinstance(agent, dict) else None
    return name if isinstance(name, str) else None


def is_lead(project, session, pane, clock):
    try:
        lead = relaylib.read_json(os.path.join(project, 'relay', 'lead.json'))
        if isinstance(lead, dict) and lead.get('session_id') == session:
            return True
    except (OSError, ValueError):
        pass
    name = herdr_name(pane, clock.left(HERDR_BOUND))
    return bool(name) and name.startswith('lead-')


def toast(title, body):
    """Fire and forget: the toast is never waited on, and its failure changes nothing."""
    try:
        subprocess.Popen(['herdr', 'notification', 'show', title, '--body', body, '--sound', 'request'],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
    except OSError:
        pass


def trim(path, keep):
    if os.path.getsize(path) > keep:
        with open(path, 'rb') as fh:
            fh.seek(-keep, os.SEEK_END)
            tail = fh.read()
        with open(path, 'wb') as fh:
            fh.write(tail)


def report_error(where, text):
    """Log the traceback; toast once per session (an O_EXCL marker, independent of the state)."""
    project, session = where.get('project'), where.get('session') or 'unknown'
    if project and os.path.isdir(project):
        log = os.path.join(project, 'relay', 'gate', 'errors.log')
        marker = os.path.join(project, 'relay', 'gate', session + '.error')
    else:
        log = os.path.expanduser('~/.claude/relay-gate-errors.log')
        marker = os.path.expanduser('~/.claude/relay-gate-%s.error' % session)
    try:
        os.makedirs(os.path.dirname(log), exist_ok=True)
        with open(log, 'a') as fh:
            fh.write('== %s session %s\n%s\n' % (utc_now(), session, text.rstrip()))
        trim(log, LOG_KEEP)
        os.close(os.open(marker, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
    except OSError:
        return
    toast('Relay gate: error', 'The relay gate failed in session %s; see %s' % (session[:8], log))


class Call:
    """One hook call: its input, paths, settings and the toasts to raise after the output."""

    def __init__(self, inp, cfg, clock, now):
        self.inp, self.cfg, self.clock, self.now = inp, cfg, clock, now
        self.session = inp.get('session_id')
        self.transcript = inp.get('transcript_path')
        self.project = os.path.dirname(self.transcript)
        self.state_path = os.path.join(self.project, 'relay', 'gate', '%s.json' % self.session)
        self.pane = os.environ.get('HERDR_PANE_ID')
        self.label = os.path.basename((inp.get('cwd') or self.project).rstrip('/')) or 'lead'
        self.toasts = []

    def lead(self):
        return is_lead(self.project, self.session, self.pane, self.clock)

    def alert(self, text, then):
        """An owner alert: a toast now, and a block asking the lead to push the same text."""
        self.toasts.append(('Relay gate: %s' % self.label, text))
        return {'decision': 'block', 'reason': (
            'relay-gate: %s Load the push tool with ToolSearch select:PushNotification and send the owner: "%s" '
            'Then %s.' % (text, text, then))}


def unknown_model(call):
    """A lead whose model has no known window: one tooling toast per session; otherwise inert."""
    model = transcript.last_model(call.transcript)
    if not model or call.cfg.window or model in transcript.WINDOWS or not call.lead():
        return
    state = load_state(call.state_path)
    if 'unknown-model' not in state['toasted']:
        state['toasted'].append('unknown-model')
        save_state(call.state_path, state)
        call.toasts.append(('Relay gate: %s' % call.label, 'Lead session %s runs %s, whose context window the relay '
                            'gate does not know: it will not relay this session automatically.'
                            % (call.session[:8], model)))


def below(call, pct):
    """Below the threshold: only an existing state (a lead) is touched, to forget bands after a drop."""
    if os.path.exists(call.state_path):
        state = load_state(call.state_path)
        if reset_bands(state, pct, call.cfg):
            save_state(call.state_path, state)


def stop(call):
    cfg = call.cfg
    fill = transcript.context_fill(call.transcript, cfg.window)
    if fill is None:
        unknown_model(call)
        return None
    pct = fill['pct']
    if pct < cfg.threshold:
        below(call, pct)
        return None
    if not call.lead():
        return None
    state = load_state(call.state_path)
    prune(os.path.dirname(call.state_path), call.state_path, call.now)
    band = band_of(pct, cfg)
    reset_bands(state, pct, cfg)
    state['meter'] = {'pct': round(pct, 1), 'read_at': utc_now()}
    out = decide(call, state, pct, band)
    call.clock.left(HERDR_BOUND)   # past the budget: say nothing and record nothing
    save_state(call.state_path, state)
    return out


def decide(call, state, pct, band):
    """The Stop decision for a gated lead at pct in band; mutates state."""
    state['asked'] = {'band': band, 'attempt': 1, 'tasks': [], 'count': 1}
    return {'decision': 'block', 'reason': 'relay-gate: context is %d%% (threshold %s%%). Run /relay now, '
                                           'automatic relay attempt 1 of 2.' % (pct, call.cfg.threshold)}


def tool(call):
    return None


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    mode = argv[0] if len(argv) == 1 else None
    if mode not in BUDGET:
        print('usage: relay-gate.py stop|tool (a Claude Code hook; reads the hook JSON on stdin)', file=sys.stderr)
        return 1    # a hook's exit 2 would block the session: a usage error must not
    if os.environ.get('HERDR_ENV') != '1' or not os.environ.get('HERDR_PANE_ID'):
        return 0
    where = {}
    call = None
    try:
        inp = json.loads(sys.stdin.read())
        if not isinstance(inp, dict):
            raise ValueError('the hook input is not a JSON object')
        if inp.get('agent_id'):
            return 0
        where['session'] = inp.get('session_id') if isinstance(inp.get('session_id'), str) else None
        path = inp.get('transcript_path')
        if not where['session'] or not isinstance(path, str) or not path:
            return 0
        where['project'] = os.path.dirname(path)
        call = Call(inp, Config(os.environ), Clock(BUDGET[mode]), time.time())
        out = (stop if mode == 'stop' else tool)(call)
    except Late:
        return 0
    except Exception:
        report_error(where, traceback.format_exc())
        return 0
    if out is not None:
        sys.stdout.write(json.dumps(out))
        sys.stdout.flush()
    for title, body in call.toasts:
        toast(title, body)
    return 0


if __name__ == '__main__':
    sys.exit(main())
```

- [ ] **Step 4: Run the tests to make sure they pass**

Run: `python3 -m unittest discover -s tests -p test_relay_gate.py -v`
Expected: PASS

Run: `test -z "$(find private_dot_claude -name __pycache__)"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add private_dot_claude/skills/session-handoff/scripts/relay-gate.py tests/test_relay_gate.py
git commit -m "relay-gate: the hook's identity checks, state file and fail-open errors"
```

### Task 4: Stop mode: the decision

**Files:**
- Modify: `private_dot_claude/skills/session-handoff/scripts/relay-gate.py` (replace `decide()` whole; add `failures_of()`, `unsafe()`, `owner_recent()`)
- Test: `tests/test_relay_gate.py` (a `StopTests` class)

**Interfaces:**
- Consumes: `relaylib.relays_of`, `relaylib.will_repeat`, `relaylib.blockers` (Task 1); `transcript.open_tasks`, `transcript.prompts`, `transcript.epoch`, `transcript.TERMINAL`; `Call.alert`, `Config`, `MAX_ASKS`, `HANDOVER_ALERT_AFTER` (Task 3).
- Produces: `decide(call, state, pct, band) -> dict | None` (spec "Stop mode", steps 1–6 in order), `failures_of(relays) -> list[dict]` (used by Task 5), `unsafe(call, tasks) -> list[str]`, `owner_recent(call) -> bool`.

- [ ] **Step 1: Write the failing tests**

In `tests/test_relay_gate.py`, replace:

```python
if __name__ == '__main__':
    unittest.main()
```

with:

```python
class StopTests(GateCase):
    def setUp(self):
        super().setUp()
        self.make_lead()

    def test_below_the_threshold(self):
        self.at(49)
        self.assertIsNone(self.gate())

    def test_safe_lead_is_asked_with_its_tasks_listed(self):
        self.at(52)
        out = self.gate(tasks=[shell('b1', 'Wait for the slice 13 report')])
        self.assertEqual(out['reason'], (
            "relay-gate: context is 52% (threshold 50%). Run /relay now, automatic relay attempt 1 of 2. Open "
            "background tasks: b1 'Wait for the slice 13 report' (shell). The successor re-arms waiters. If one of "
            "them is long work that must finish first, end your turn instead: the gate asks again when a listed "
            "task closes or the next band starts."))
        self.assertEqual(self.state()['asked'], {'band': 50, 'attempt': 1, 'tasks': ['b1'], 'count': 1})

    def test_a_relay_in_progress_silences_the_gate(self):
        make_relay(self.project, 'R1', SID, files=['launch.json'])
        self.at(55)
        self.assertIsNone(self.gate())

    def test_a_frozen_relay_is_silent_then_alerts_once_after_30_minutes(self):
        rdir = make_relay(self.project, 'R1', SID, files=['launch.json', 'receipt.json', 'handover.md'])
        self.at(55)
        self.assertIsNone(self.gate())
        old = time.time() - 31 * 60
        os.utime(rdir / 'handover.md', (old, old))
        out = self.gate()
        self.assertIn('hand-over of relay R1 is not closed', out['reason'])
        self.assertIn('select:PushNotification', out['reason'])
        self.assertIsNone(self.gate())
        self.assertEqual(len(self.toasts(1)), 1)

    def test_two_failures_give_up_with_one_alert(self):
        make_relay(self.project, 'R1', SID, files=[('failed.json', {'stage': 'receipt'})], age=3 * 3600)
        make_relay(self.project, 'R2', SID, files=[('failed.json', {'stage': 'launch'})], age=3600)
        self.at(55)
        out = self.gate()
        self.assertIn('failed (R1, R2) and will not be retried', out['reason'])
        self.assertIsNone(self.gate())
        self.assertTrue(self.state()['given_up'])
        self.assertEqual(len(self.toasts(1)), 1)

    def test_a_failure_that_will_repeat_gives_up_at_once(self):
        make_relay(self.project, 'R1', SID, files=[('failed.json', {
            'stage': 'check', 'reason': "FAIL identity: successor permission_mode 'default', predecessor "
                                        "'bypassPermissions'"})], age=3600)
        self.at(55)
        self.assertIn('will not be retried', self.gate()['reason'])

    def test_a_handover_stage_failure_is_never_retried(self):
        make_relay(self.project, 'R1', SID, files=['handover.md', ('failed.json', {'stage': 'handover'})],
                   age=3600)
        self.at(55)
        self.assertIsNone(self.gate())

    def test_one_failure_waits_out_the_back_off_then_asks_attempt_2(self):
        rdir = make_relay(self.project, 'R1', SID, files=[('failed.json', {'stage': 'receipt'})], age=60)
        self.at(52)
        self.assertIsNone(self.gate(tasks=[shell('b1')]))
        gate_dir = self.project / 'relay' / 'gate'
        (gate_dir / (SID + '.json')).write_text(json.dumps(dict(load_gate().fresh(), asked={
            'band': 50, 'attempt': 1, 'tasks': ['b1'], 'count': 1})))
        old = time.time() - 31 * 60
        os.utime(rdir / 'failed.json', (old, old))
        self.assertAsk(self.gate(tasks=[shell('b1')]), attempt=2)

    def test_an_abandoned_relay_counts_as_a_failure(self):
        make_relay(self.project, 'R1', SID, files=['launch.json'], age=26 * 60)
        self.at(52)
        self.assertIsNone(self.gate(env={'RELAY_GATE_BACKOFF_S': '3600'}))
        self.assertAsk(self.gate(env={'RELAY_GATE_BACKOFF_S': '60'}), attempt=2)

    def test_not_safe_below_the_cap_owes_a_drain_nudge(self):
        self.at(52)
        self.assertIsNone(self.gate(tasks=[{'id': 'a1', 'type': 'subagent', 'status': 'running'}]))
        self.assertTrue(self.state()['drain_owed'])

    def test_not_safe_at_the_cap_alerts_once_per_band(self):
        running = [{'id': 'a1', 'type': 'subagent', 'status': 'running', 'description': 'review'}]
        self.at(61)
        out = self.gate(tasks=running)
        self.assertIn('cannot relay yet: subagent a1 is running (review)', out['reason'])
        self.assertIn('keep draining', out['reason'])
        self.assertNotIn('Run /relay now', out['reason'])
        self.assertIsNone(self.gate(tasks=running))
        self.at(71)
        self.assertIn('is at 71%', self.gate(tasks=running)['reason'])
        self.assertEqual(len(self.toasts(2)), 2)

    def test_an_alert_toast_that_fails_changes_nothing(self):
        self.herd({'notification show': [{'out': 'boom', 'code': 1, 'sleep': 3}]})
        self.make_lead()
        self.at(61)
        started = time.time()
        out = self.gate(tasks=[{'id': 'a1', 'type': 'subagent', 'status': 'running', 'description': 'review'}])
        self.assertLess(time.time() - started, 2.5)
        self.assertIn('cannot relay yet', out['reason'])

    def test_a_missing_task_list_an_unknown_type_and_a_teammate_are_not_safe(self):
        self.at(52)
        self.assertIsNone(self.gate(background_tasks=None))
        self.assertIsNone(self.gate(tasks=[{'id': 'w1', 'type': 'workflow', 'status': 'running'}]))
        self.assertIsNone(self.gate(tasks=[{'id': 't1', 'type': 'teammate', 'status': 'running'}]))
        self.assertIsNone(self.state()['asked'])
        self.at(61)
        self.assertIn('workflow w1 is running', self.gate(tasks=[{'id': 'w1', 'type': 'workflow',
                                                                   'status': 'running'}])['reason'])

    def test_a_finished_subagent_does_not_block(self):
        self.at(52)
        self.assertAsk(self.gate(tasks=[{'id': 'a1', 'type': 'subagent', 'status': 'completed'}]))

    def test_a_workflow_open_in_the_transcript_is_not_safe(self):
        self.at(52, tool_use('w', 'Workflow', {'script': 'export const meta = {}'}, 2),
                tool_result('w', 'Workflow launched in background. Task ID: wf0001', 2,
                            tool_use_result={'status': 'async_launched', 'taskId': 'wf0001'}))
        self.assertIsNone(self.gate())
        self.at(61, *self.recs[:-1])
        self.assertIn('workflow wf0001 is running inside this session', self.gate()['reason'])

    def test_git_mid_merge_is_not_safe(self):
        (self.repo / '.git' / 'MERGE_HEAD').write_text('0' * 40 + '\n')
        self.at(52)
        self.assertIsNone(self.gate())

    def test_a_recent_owner_prompt_defers_below_the_cap_only(self):
        typed = dict(prompt('how is it going?'), timestamp=iso(300))
        self.at(52, typed)
        self.assertIsNone(self.gate())
        self.assertAsk(self.gate(env={'RELAY_GATE_OWNER_S': '60'}))   # the test-only window (live e2e)
        (self.project / 'relay' / 'gate' / (SID + '.json')).unlink()
        self.at(61, typed)
        self.assertAsk(self.gate())

    def test_a_prompt_without_a_readable_time_does_not_defer(self):
        self.at(52, dict(prompt('hi'), timestamp='yesterday'))
        self.assertAsk(self.gate())

    def test_an_owner_prompt_older_than_10_minutes_does_not_defer(self):
        self.at(52, dict(prompt('earlier'), timestamp=iso(900)))
        self.assertAsk(self.gate())

    def test_the_same_band_attempt_and_tasks_are_asked_once(self):
        self.at(52)
        self.assertAsk(self.gate(tasks=[shell('b1')]))
        self.assertIsNone(self.gate(tasks=[shell('b1')]))

    def test_an_added_task_does_not_ask_again(self):
        self.at(52)
        self.assertAsk(self.gate(tasks=[shell('b1')]))
        self.assertIsNone(self.gate(tasks=[shell('b1'), shell('b2')]))

    def test_a_listed_task_closing_asks_again(self):
        self.at(52)
        self.assertAsk(self.gate(tasks=[shell('b1'), shell('b2')]))
        self.assertAsk(self.gate(tasks=[shell('b2')]))
        self.assertEqual(self.state()['asked']['count'], 2)

    def test_a_band_rise_asks_again_with_the_owner_alert(self):
        self.at(52)
        self.assertAsk(self.gate(tasks=[shell('b1')]))
        self.at(61)
        out = self.gate(tasks=[shell('b1')])
        self.assertAsk(out)
        self.assertIn('select:PushNotification', out['reason'])
        self.assertEqual(len(self.toasts(1)), 1)

    def test_a_fourth_ask_in_a_band_is_silent(self):
        self.at(52)
        gate_dir = self.project / 'relay' / 'gate'
        gate_dir.mkdir(parents=True)
        (gate_dir / (SID + '.json')).write_text(json.dumps(dict(load_gate().fresh(), asked={
            'band': 50, 'attempt': 1, 'tasks': ['b1'], 'count': 3})))
        self.assertIsNone(self.gate(tasks=[]))

    def test_a_drop_of_more_than_a_step_forgets_the_bands(self):
        self.at(52)
        self.assertAsk(self.gate(tasks=[shell('b1')]))
        self.assertIsNone(self.gate(tasks=[shell('b1')]))
        self.at(15)
        self.assertIsNone(self.gate(tasks=[shell('b1')]))
        self.assertIsNone(self.state()['asked'])
        self.at(52)
        self.assertAsk(self.gate(tasks=[shell('b1')]))

    def test_a_relay_never_loops_after_a_failure(self):
        """T13: 40 Stops with notification turns, new prompt ids and churning waiters around two failures."""
        blocks = []

        def stop(n, tag):
            out = self.gate(tasks=[shell('w%d' % n)])
            if out:
                blocks.append((tag, n, out['reason']))

        first = make_relay(self.project, 'R1', SID, files=[('failed.json', {'stage': 'receipt'})])
        self.at(52)
        for n in range(20):
            stop(n, 'back-off')
        old = time.time() - 31 * 60
        os.utime(first / 'failed.json', (old, old))
        stop(20, 'retry')
        second = make_relay(self.project, 'R2', SID, files=['launch.json'])
        for n in range(21, 26):
            stop(n, 'relaying')
        (second / 'failed.json').write_text(json.dumps({'stage': 'receipt'}))
        for n in range(26, 40):
            stop(n, 'after')
        self.assertEqual([(tag, n) for tag, n, _ in blocks], [('retry', 20), ('after', 26)], blocks)
        self.assertIn('attempt 2 of 2', blocks[0][2])
        self.assertIn('will not be retried', blocks[1][2])


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run them to make sure they fail**

Run: `python3 -m unittest discover -s tests -p test_relay_gate.py -k StopTests -v`
Expected: FAIL, output contains `AssertionError`

Expected detail: 22 of the 26 StopTests fail. Four pass already because Task 3's stub `decide()` asks unconditionally and these four expect an ask (or, below the threshold, silence before `decide()` runs): `test_a_finished_subagent_does_not_block`, `test_a_prompt_without_a_readable_time_does_not_defer`, `test_an_owner_prompt_older_than_10_minutes_does_not_defer`, `test_below_the_threshold`. They are guards: each fails if the full `decide()` wrongly stays silent in its case.

- [ ] **Step 3: Write the decision**

In `private_dot_claude/skills/session-handoff/scripts/relay-gate.py`, replace:

```python
def decide(call, state, pct, band):
    """The Stop decision for a gated lead at pct in band; mutates state."""
    state['asked'] = {'band': band, 'attempt': 1, 'tasks': [], 'count': 1}
    return {'decision': 'block', 'reason': 'relay-gate: context is %d%% (threshold %s%%). Run /relay now, '
                                           'automatic relay attempt 1 of 2.' % (pct, call.cfg.threshold)}
```

with:

```python
def decide(call, state, pct, band):
    """The Stop decision for a gated lead at pct in band; mutates state."""
    cfg, now = call.cfg, call.now
    relays = relaylib.relays_of(call.project, call.session, now)
    if any(r['state'] == 'in_progress' for r in relays):
        return None
    for r in relays:
        if r['state'] == 'frozen' and now - r['handover_at'] >= HANDOVER_ALERT_AFTER \
                and r['id'] not in state['handover_alerted']:
            state['handover_alerted'].append(r['id'])
            return call.alert('The hand-over of relay %s is not closed after %d minutes: the successor never '
                              'closed this session.' % (r['id'], (now - r['handover_at']) // 60), 'end your turn')
    if any(r['state'] == 'frozen' for r in relays):
        return None
    failures = failures_of(relays)
    if any(r['stage'] == 'handover' for r in failures):
        return None
    attempt = 1 + len(failures)
    if len(failures) >= 2 or any(relaylib.will_repeat(r) for r in failures):
        if state['given_up']:
            return None
        state['given_up'] = True
        return call.alert('Automatic relays of lead %s failed (%s) and will not be retried; run /relay by hand.'
                          % (call.label, ', '.join(r['id'] for r in failures)), 'end your turn')
    if failures and now - failures[0]['failed_at'] < cfg.backoff:
        return None
    tasks = call.inp.get('background_tasks')
    reasons = unsafe(call, tasks)
    if reasons:
        if band < cfg.cap:
            if band not in state['nudged']:
                state['drain_owed'] = True
            return None
        if band in state['alerted']:
            return None
        state['alerted'].append(band)
        return call.alert('Lead %s is at %d%% and cannot relay yet: %s.' % (call.label, pct, '; '.join(reasons)),
                          'keep draining (start nothing new in-session) and end your turn; do not run /relay yet')
    if band < cfg.cap and owner_recent(call):
        return None
    open_tasks = [t for t in tasks if isinstance(t, dict) and t.get('status') not in transcript.TERMINAL]
    ids = sorted(str(t.get('id')) for t in open_tasks)
    asked = state['asked']
    count = 1
    if asked and asked['band'] == band and asked['attempt'] == attempt:
        if asked['count'] >= MAX_ASKS or all(i in ids for i in asked['tasks']):
            return None
        count = asked['count'] + 1
    state['asked'] = {'band': band, 'attempt': attempt, 'tasks': ids, 'count': count}
    listing = '; '.join("%s '%s' (%s)" % (t.get('id'), t.get('description') or t.get('command') or '', t.get('type'))
                        for t in open_tasks) or 'none'
    reason = ('relay-gate: context is %d%% (threshold %s%%). Run /relay now, automatic relay attempt %d of 2. '
              'Open background tasks: %s. The successor re-arms waiters. If one of them is long work that must '
              'finish first, end your turn instead: the gate asks again when a listed task closes or the next band '
              'starts.' % (pct, cfg.threshold, attempt, listing))
    if band >= cfg.cap and band not in state['alerted']:
        state['alerted'].append(band)
        text = 'Lead %s is at %d%% and has not relayed yet; the gate asked it to run /relay.' % (call.label, pct)
        call.toasts.append(('Relay gate: %s' % call.label, text))
        reason += (' Also load the push tool with ToolSearch select:PushNotification and send the owner: "%s"'
                   % text)
    return {'decision': 'block', 'reason': reason}


def failures_of(relays):
    return [r for r in relays if r['state'] in ('failed', 'abandoned')]


def unsafe(call, tasks):
    """Why a relay cannot start now, or []: the same rules as relay-check.py checklist, plus the live task list."""
    if not isinstance(tasks, list):
        return ['the hook input carries no background task list']
    out = ['%s %s is running (%s)' % (t.get('type'), t.get('id'), t.get('description') or '')
           for t in tasks if isinstance(t, dict) and t.get('status') not in transcript.TERMINAL
           and t.get('type') != 'shell']
    repo = call.inp.get('cwd') or call.project
    return out + relaylib.blockers(repo, transcript.open_tasks([call.transcript]))


def owner_recent(call):
    for p in transcript.prompts(call.transcript):
        when = transcript.epoch(p['timestamp'])
        if when is not None and call.now - when < call.cfg.owner:
            return True
    return False
```

- [ ] **Step 4: Run the tests to make sure they pass**

Run: `python3 -m unittest discover -s tests -p test_relay_gate.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add private_dot_claude/skills/session-handoff/scripts/relay-gate.py tests/test_relay_gate.py
git commit -m "relay-gate: the Stop decision (relays, back-off, safe point, dedupe, alerts)"
```

### Task 5: Tool mode: the nudge

**Files:**
- Modify: `private_dot_claude/skills/session-handoff/scripts/relay-gate.py` (replace `tool()` whole; add `nudge()`)
- Test: `tests/test_relay_gate.py` (a `ToolTests` class)

**Interfaces:**
- Consumes: `failures_of` (Task 4); `load_state`, `save_state`, `fresh`, `reset_bands`, `band_of`, `utc_now`, `Call.lead` (Task 3); `relaylib.relays_of`, `relaylib.will_repeat`.
- Produces: `tool(call) -> dict | None` and `nudge(call, state, pct, band) -> dict | None` (spec "Tool mode").

- [ ] **Step 1: Write the failing tests**

In `tests/test_relay_gate.py`, replace:

```python
if __name__ == '__main__':
    unittest.main()
```

with:

```python
class ToolTests(GateCase):
    def setUp(self):
        super().setUp()
        self.make_lead()
        self.extra_env = {'RELAY_GATE_THROTTLE_S': '0.001'}

    def assertNudge(self, out, pct):
        self.assertEqual(out['hookSpecificOutput']['hookEventName'], 'PostToolUse')
        self.assertTrue(out['hookSpecificOutput']['additionalContext'].startswith(
            'relay-gate: context is %d%%. A relay is due.' % pct))

    def test_once_per_band(self):
        self.at(52)
        self.assertNudge(self.gate('tool'), 52)
        self.assertIsNone(self.gate('tool'))
        self.at(61)
        self.assertNudge(self.gate('tool'), 61)
        self.assertEqual(self.state()['nudged'], [50, 60])

    def test_a_drain_owed_by_stop_is_delivered_past_the_throttle(self):
        self.at(52)
        self.assertNudge(self.gate('tool'), 52)
        self.assertIsNone(self.gate(tasks=[{'id': 'a1', 'type': 'subagent', 'status': 'running'}]))
        self.assertFalse(self.state()['drain_owed'])   # band 50 was already nudged: nothing owed
        state_path = self.project / 'relay' / 'gate' / (SID + '.json')
        state_path.write_text(json.dumps(dict(self.state(), drain_owed=True, nudged=[],
                                              meter={'pct': 52.0, 'read_at': iso(0)})))
        self.assertNudge(self.gate('tool', env={'RELAY_GATE_THROTTLE_S': '3600'}), 52)
        self.assertFalse(self.state()['drain_owed'])

    def test_the_throttle_skips_the_meter(self):
        self.at(52)
        state_path = self.project / 'relay' / 'gate' / (SID + '.json')
        state_path.parent.mkdir(parents=True)
        state_path.write_text(json.dumps(dict(load_gate().fresh(), meter={'pct': 40.0, 'read_at': iso(10)})))
        self.assertIsNone(self.gate('tool', env={'RELAY_GATE_THROTTLE_S': '60'}))
        state_path.write_text(json.dumps(dict(load_gate().fresh(), meter={'pct': 40.0, 'read_at': iso(120)})))
        self.assertNudge(self.gate('tool', env={'RELAY_GATE_THROTTLE_S': '60'}), 52)

    def test_silent_while_relaying_frozen_backing_off_or_given_up(self):
        self.at(52)
        cases = {'in progress': [('R1', ['launch.json'], 0)],
                 'frozen': [('R1', ['handover.md'], 0)],
                 'back-off': [('R1', [('failed.json', {'stage': 'receipt'})], 60)],
                 'given up': [('R1', [('failed.json', {'stage': 'receipt'})], 7200),
                              ('R2', [('failed.json', {'stage': 'launch'})], 3600)]}
        for label, relays in cases.items():
            with self.subTest(label):
                relay_dir = self.project / 'relay'
                for child in list(relay_dir.iterdir()):
                    if child.is_dir():
                        for path in sorted(child.rglob('*'), reverse=True):
                            path.rmdir() if path.is_dir() else path.unlink()
                        child.rmdir()
                for rid, files, age in relays:
                    make_relay(self.project, rid, SID, files=files, age=age)
                self.assertIsNone(self.gate('tool'))

    def test_parallel_tool_calls_leave_a_valid_state(self):
        self.at(52)
        path = write_transcript(self.projects, SID, self.recs)
        inp = json.dumps({'session_id': SID, 'transcript_path': str(path), 'cwd': str(self.repo), 'tool_name': 'Bash'})
        env = dict(self.env, RELAY_GATE_THROTTLE_S='0.001')
        procs = [subprocess.Popen(['python3', '-I', str(GATE), 'tool'], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True, env=env) for _ in range(6)]
        outs = [p.communicate(inp, timeout=30) for p in procs]
        self.assertEqual([p.returncode for p in procs], [0] * 6, [e for _, e in outs])
        self.assertGreaterEqual(sum(1 for out, _ in outs if out.strip()), 1)
        self.assertEqual(self.state()['nudged'], [50])

    def test_a_subagent_tool_call_is_ignored(self):
        self.at(52)
        self.assertIsNone(self.gate('tool', agent_id='a962fa2df48cd277c'))

    def test_a_non_lead_writes_nothing(self):
        (self.project / 'relay' / 'lead.json').unlink()
        self.at(52)
        self.assertIsNone(self.gate('tool'))
        self.assertIsNone(self.state())


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run them to make sure they fail**

Run: `python3 -m unittest discover -s tests -p test_relay_gate.py -k ToolTests -v`
Expected: FAIL, output contains `FAILED`

Expected detail: 4 of the 7 ToolTests fail. Three pass already because Task 3's stub `tool()` is always silent and these three expect silence: `test_a_non_lead_writes_nothing`, `test_a_subagent_tool_call_is_ignored`, `test_silent_while_relaying_frozen_backing_off_or_given_up`. They are guards: each fails if the full `tool()` nudges where it must not.

- [ ] **Step 3: Write the nudge**

In `private_dot_claude/skills/session-handoff/scripts/relay-gate.py`, replace:

```python
def tool(call):
    return None
```

with:

```python
def tool(call):
    cfg = call.cfg
    known = os.path.exists(call.state_path)
    state = load_state(call.state_path) if known else None
    if state and not state['drain_owed'] and state['meter']:
        read = transcript.epoch(state['meter']['read_at'])
        if read is not None and call.now - read < cfg.throttle:
            return None
    fill = transcript.context_fill(call.transcript, cfg.window)
    if fill is None:
        return None
    pct = fill['pct']
    if pct < cfg.threshold:
        if state is not None:
            reset_bands(state, pct, cfg)
            state['meter'] = {'pct': round(pct, 1), 'read_at': utc_now()}
            save_state(call.state_path, state)
        return None
    if state is None:
        if not call.lead():
            return None
        state = fresh()
    band = band_of(pct, cfg)
    reset_bands(state, pct, cfg)
    state['meter'] = {'pct': round(pct, 1), 'read_at': utc_now()}
    out = nudge(call, state, pct, band)
    call.clock.left(HERDR_BOUND)
    save_state(call.state_path, state)
    return out


def nudge(call, state, pct, band):
    relays = relaylib.relays_of(call.project, call.session, call.now)
    if any(r['state'] in ('in_progress', 'frozen') for r in relays) or state['given_up']:
        return None
    failures = failures_of(relays)
    if any(r['stage'] == 'handover' for r in failures) or len(failures) >= 2 \
            or any(relaylib.will_repeat(r) for r in failures):
        return None
    if failures and call.now - failures[0]['failed_at'] < call.cfg.backoff:
        return None
    if band in state['nudged'] and not state['drain_owed']:
        return None
    if band not in state['nudged']:
        state['nudged'].append(band)
    state['drain_owed'] = False
    return {'hookSpecificOutput': {'hookEventName': 'PostToolUse', 'additionalContext': (
        'relay-gate: context is %d%%. A relay is due. Finish the current step, start nothing new in-session (no '
        'subagents, no attached runs), then end your turn; the gate runs /relay at turn end.' % pct)}}
```

- [ ] **Step 4: Run the tests to make sure they pass**

Run: `python3 -m unittest discover -s tests -p test_relay_gate.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add private_dot_claude/skills/session-handoff/scripts/relay-gate.py tests/test_relay_gate.py
git commit -m "relay-gate: the mid-turn nudge"
```

### Task 6: Docs: automatic relays, and naming the coordinator

**Files:**
- Modify: `private_dot_claude/skills/session-handoff/references/relay.md` (a section before `## Failure table`, one failure-table row)
- Modify: `private_dot_claude/skills/session-handoff/SKILL.md` (the Discipline line, a pointer after the RELAY mode outline)
- Modify: `private_dot_claude/CLAUDE.md` (the `/relay` authority line, a "Name the coordinator" bullet in "Herd layout"; this is the chezmoi source of `~/.claude/CLAUDE.md`)
- Test: `tests/test_handoff_docs.py`

**Interfaces:**
- Consumes: the registration lines in the spec ("Registration"); the test pins them identical.
- Produces: doc text only.

- [ ] **Step 1: Write the failing test**

In `tests/test_handoff_docs.py`, replace:

```python
    def test_no_pgrep_check_of_the_successors_waiters(self):
```

with:

```python
    def test_automatic_relays_are_documented_where_a_lead_looks(self):
        # The gate is switched on by hand: relay.md must carry the exact registration the spec designs, and a
        # coordinator must learn to name itself lead-<project>, or the gate never sees it.
        relay = (SKILL / 'references/relay.md').read_text()
        spec = (SOURCE / 'docs/superpowers/specs/2026-10-13-relay-gate-design.md').read_text()
        registration = [line.strip() for line in relay.splitlines() if 'relay-gate.py' in line and '"command"' in line]
        self.assertEqual(len(registration), 2, registration)
        for line in registration:
            self.assertIn(line, spec)
        flat = ' '.join(relay.split())
        for needle in ('## Automatic relays (the relay gate)', 'Run /relay now, automatic relay attempt k of 2',
                       'retried once, after 30 minutes', '`select:PushNotification`', 'One lead per project'):
            self.assertIn(needle, flat)
        skill = ' '.join((SKILL / 'SKILL.md').read_text().split())
        self.assertIn('`references/relay.md` § Automatic relays', skill)
        claude = ' '.join((SOURCE / 'private_dot_claude/CLAUDE.md').read_text().split())
        self.assertIn('**Name the coordinator.**', claude)
        self.assertIn('relay-check.py name --repo <repo>', claude)

    def test_no_pgrep_check_of_the_successors_waiters(self):
```

- [ ] **Step 2: Run it to make sure it fails**

Run: `python3 -m unittest discover -s tests -p test_handoff_docs.py -v`
Expected: FAIL, output contains `AssertionError`

- [ ] **Step 3: Write the docs**

In `private_dot_claude/skills/session-handoff/references/relay.md`, replace:

```markdown
## Failure table
```

with:

```markdown
## Automatic relays (the relay gate)

`scripts/relay-gate.py` is a Claude Code hook that has a lead run `/relay` at
50% context. It acts only once the owner registers it in
`~/.claude/settings.json`:

    "Stop":        [{"hooks": [{"type": "command", "command": "python3 -I ~/.claude/skills/session-handoff/scripts/relay-gate.py stop", "timeout": 10}]}]
    "PostToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": "python3 -I ~/.claude/skills/session-handoff/scripts/relay-gate.py tool", "timeout": 5}]}]

- **Who.** Only a lead: a herdr session whose name starts with `lead-`, or the
  session in `relay/lead.json`. Name a coordinator `lead-<project>` at start
  (`relay-check.py name --repo <repo>` prints the name). One lead per project:
  successors are named `lead-<slug>-next`, then `lead-<slug>`. Workers,
  subagents and teammates are never gated.
- **When.** At the end of a turn at or above 50%, once it is safe: no subagent,
  teammate or workflow running and git not mid-operation (the rules `checklist`
  refuses on). Below 60%, a prompt typed in the last 10 minutes defers it. The
  turn is blocked with "relay-gate: context is N% (threshold 50%). Run /relay
  now, automatic relay attempt k of 2." and the open background tasks: run
  `/relay`. If a listed task is long work that must finish first, end your turn
  instead: the gate asks again when a listed task closes or the next 10% band
  starts, at most 3 times per band.
- **Nudge.** After a tool call past 50%, once per band, the gate adds a line: a
  relay is due, finish the current step, start nothing new in-session (no
  subagents, no attached runs), end your turn.
- **Not safe at 60%,** and at each later band, the gate alerts the owner: a herdr
  toast, and the block asks you to load PushNotification (ToolSearch
  `select:PushNotification`) and push the same text. Keep draining.
- **Back-off.** A failed relay (`failed.json`, or a relay dir with no activity
  for 25 minutes) is retried once, after 30 minutes. A second failure, or one
  that would repeat (an identity mismatch, a taken agent name), stops the gate
  for this session with one owner alert; the owner relays by hand. A
  `handover`-stage failure is never retried. A predecessor the owner resumes
  after a hand-over is never gated again: the owner relays it by hand.
- **State.** `relay/gate/<session-id>.json`, for leads only; errors go to
  `relay/gate/errors.log`. The gate never fails closed: an error is logged and
  toasted once, and the turn ends normally.

## Failure table
```

In `private_dot_claude/skills/session-handoff/references/relay.md`, replace:

```markdown
| Memory index over the cap | the relay proceeds; debt in the note; the successor's first job |
```

with:

```markdown
| Memory index over the cap | the relay proceeds; debt in the note; the successor's first job |
| An automatic relay fails | the gate retries once after 30 minutes; a second failure stops it for this session with one owner alert |
```

In `private_dot_claude/skills/session-handoff/SKILL.md`, replace:

```markdown
Discipline: hand off at 50% of the context meter, not at the wire. Inside
herdr, relay to a new session (`/relay`); outside it, `/handoff`, then `/clear`,
then `/pickup`. A lead never compacts instead.
```

with:

```markdown
Discipline: hand off at 50% of the context meter, not at the wire. Inside
herdr, relay to a new session (`/relay`; the relay gate asks a lead to, once
switched on); outside it, `/handoff`, then `/clear`, then `/pickup`. A lead
never compacts instead.
```

In `private_dot_claude/skills/session-handoff/SKILL.md`, replace:

```markdown
   and tell the owner. Never close your own pane: the successor does, with
   `bash ~/.claude/skills/session-handoff/scripts/relay-close.sh <relay-dir>`.
```

with:

```markdown
   and tell the owner. Never close your own pane: the successor does, with
   `bash ~/.claude/skills/session-handoff/scripts/relay-close.sh <relay-dir>`.

**Automatic relays.** Once the owner registers `scripts/relay-gate.py` as a
Stop and PostToolUse hook, a lead (named `lead-…`) is blocked at its first safe
turn end at or above 50% with "Run /relay now": run it, or end your turn if a
listed task is long work that must finish first. Details:
`references/relay.md` § Automatic relays.
```

In `private_dot_claude/CLAUDE.md`, replace:

```markdown
- **hand the lead to a new session** (at 50% context, or when asked) → `/relay`
```

with:

```markdown
- **hand the lead to a new session** (at 50% context, or when asked; the relay gate asks a lead at 50% once switched on) → `/relay`
```

In `private_dot_claude/CLAUDE.md`, replace:

```markdown
- **Launch and verify.** Claude workers spawn at **high** effort: `herdr agent start <role>-high --kind claude --pane <id> -- --model <id> --effort high --dangerously-skip-permissions`. The name says role and effort (`cs-review-high`, `runkit-v10-high`). Pass model and effort explicitly (another effort only when I name one for the task), then read the pane's banner (`herdr pane read <id> --source visible`) and confirm both before the first brief.
```

with:

```markdown
- **Name the coordinator.** At start, name the coordinator `lead-<project>`: `herdr agent rename $HERDR_PANE_ID $(python3 -I ~/.claude/skills/session-handoff/scripts/relay-check.py name --repo <repo>)`. The relay gate relays only a session named `lead-…` or recorded in the project's `relay/lead.json`, so an unnamed coordinator is never relayed automatically. One lead per project.
- **Launch and verify.** Claude workers spawn at **high** effort: `herdr agent start <role>-high --kind claude --pane <id> -- --model <id> --effort high --dangerously-skip-permissions`. The name says role and effort (`cs-review-high`, `runkit-v10-high`). Pass model and effort explicitly (another effort only when I name one for the task), then read the pane's banner (`herdr pane read <id> --source visible`) and confirm both before the first brief.
```

- [ ] **Step 4: Run the whole suite**

Run: `python3 -m unittest discover -s tests -v`
Expected: PASS

Run: `test -z "$(find private_dot_claude -name __pycache__)"`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add private_dot_claude/skills/session-handoff/references/relay.md private_dot_claude/skills/session-handoff/SKILL.md private_dot_claude/CLAUDE.md tests/test_handoff_docs.py
git commit -m "relay-gate: document automatic relays and naming the coordinator"
```

### Task 7: Live end to end (orchestrator-run, definition of done)

Run by the coordinator, not delegated: it drives herdr and real Claude sessions. Nothing here edits `~/.claude`
or `settings.json`: the gate under test is the **worktree's** `relay-gate.py`, registered per session with
`--settings`. Evidence goes to `$E/E2E-REPORT.md`, each command beside its output.

**Files:** none in the repo.

**How the overrides reach the hook.** Hook commands run through a shell (the plugin hooks' `${CLAUDE_PLUGIN_ROOT}`
expands), so the test overrides are written inline in each hook command (`RELAY_GATE_…=… python3 -I …`). They
reach the gate whatever Claude Code does with a settings `env` block, and nothing else in the session sees them.
Step 2 verifies it before any scenario.

**Bands without reading half a megabyte.** `RELAY_GATE_WINDOW=120000` keeps the production threshold, cap and
step (50, 60, 10) and production texts: an Opus 5.5 session of this owner starts near 53k tokens (the probe's
second call read 52,929), which is 44% of 120k, and each ~25 KB file read adds about 5 points. Back-off 120 s,
throttle 1 s, and `RELAY_GATE_OWNER_S=1`: every scenario turn is started by `herdr agent prompt`, which the
transcript records as a typed prompt, so the production 10-minute owner window would defer every ask below the cap.

**The successor runs without the gate.** `relay-launch.sh` (unchanged) starts the successor with model, effort,
session id and the bypass flag only, not this `--settings` file, and the deployed hooks do not include the gate
yet. So a successor is never gated during this run. That is enough here: every scenario judges the predecessor's
gate, and the successor only has to pick up and close it as in piece 1.

**Pushes are not sent.** Each scenario lead is told to write any push text a hook asks for to `tmp/push.txt`
instead of sending it, so the run never pings the owner's phone; the gate's output (the block reason) is what is
judged.

**No directory is deleted** (the no-unattended-deletes rule): every run gets a fresh `$E`.

- [ ] **Step 1: Gates and the scratch front**

```bash
cd $HOME/code/claude/tmp/wt-relay-gate && python3 -m unittest discover -s tests 2>&1 | tail -3   # Ran N tests ... OK
E=$HOME/code/claude/tmp/gate-e2e-$(date -u +%Y%m%dT%H%M%SZ); mkdir -p "$E"
G=$HOME/code/claude/tmp/wt-relay-gate/private_dot_claude/skills/session-handoff/scripts/relay-gate.py
SCRIPTS=$HOME/code/claude/tmp/wt-relay-gate/private_dot_claude/skills/session-handoff/scripts
ENVS='RELAY_GATE_WINDOW=120000 RELAY_GATE_BACKOFF_S=120 RELAY_GATE_THROTTLE_S=1 RELAY_GATE_OWNER_S=1'
python3 -I - "$E/settings.json" "$G" "$ENVS" <<'EOF'
import json, sys
path, gate, envs = sys.argv[1:]
hook = lambda mode, t: [{"matcher": "*", "hooks": [{"type": "command", "timeout": t,
                         "command": "%s python3 -I %s %s" % (envs, gate, mode)}]}]
json.dump({"hooks": {"Stop": hook("stop", 10), "PostToolUse": hook("tool", 5)}}, open(path, "w"), indent=1)
EOF
cat > "$E/observe.py" <<'EOF'
"""Print the gate's traces in a transcript: BLOCK (Stop blocks), NUDGE (additionalContext), NOTICE (task notices)."""
import json, sys
for line in open(sys.argv[1]):
    try:
        r = json.loads(line)
    except ValueError:
        continue
    a = r.get('attachment') or {}
    if a.get('type') == 'hook_blocking_error':
        text = (a.get('blockingError') or {}).get('blockingError', '')
        if text.startswith('relay-gate:'):
            print('BLOCK ', r.get('timestamp'), text[:150])
    elif a.get('type') == 'hook_additional_context':
        text = ' '.join(a.get('content') or [])
        if 'relay-gate:' in text:
            print('NUDGE ', r.get('timestamp'), text[:90])
    elif r.get('type') == 'user' and (r.get('origin') or {}).get('kind') == 'task-notification':
        print('NOTICE', r.get('timestamp'))
EOF
scenario() {   # scenario <slug>: a scratch repo, its project dir, a lead named lead-<slug> in a new tab
  local R="$E/$1"; mkdir -p "$R/tmp"
  (cd "$R" && git init -q && echo e2e > README.md && printf 'tmp/\n' > .gitignore && git add . \
     && git -c user.name=E2E -c user.email=e2e@example.invalid commit -qm init)
  P=$HOME/.claude/projects/$(printf '%s' "$R" | sed 's#[^A-Za-z0-9]#-#g')
  NAME=$(python3 -I "$SCRIPTS/relay-check.py" name --repo "$R")
  TAB=$(herdr tab create --cwd "$R" --label "gate-$1" --no-focus)
  PANE=$(printf '%s' "$TAB" | python3 -I -c 'import json,sys; print(json.load(sys.stdin)["result"]["root_pane"]["pane_id"])')
  herdr agent start "$NAME" --kind claude --pane "$PANE" --timeout 90000 -- --model claude-opus-5-5 --effort high \
    --dangerously-skip-permissions --settings "$E/settings.json"
  herdr pane read "$PANE" --source visible | grep -c 'Opus 5.5 with high effort'   # 1
}
transcript_of() {   # the lead's transcript path, from herdr's session id
  local sid=$(herdr agent get "$NAME" | python3 -I -c 'import json,sys; print(json.load(sys.stdin)["result"]["agent"]["agent_session"]["value"])')
  printf '%s/%s.jsonl\n' "$P" "$sid"
}
fill() { python3 -I -c 'import sys; sys.path.insert(0, sys.argv[1]); import transcript; f = transcript.context_fill(sys.argv[2], 120000); print(f and round(f["pct"], 1))' "$SCRIPTS" "$1"; }
PRE='This is a relay-gate test session. If a hook ever asks you to send a push notification, do not send it: append its text to tmp/push.txt instead.'
```

Expected: the suite green; `settings.json` with the two hook entries; `grep -c` prints `1` in each scenario.

- [ ] **Step 2: Verify the overrides reach the hook (calibration)**

```bash
scenario s0
herdr agent prompt "$NAME" "$PRE Reply with the single word READY." --wait --timeout 180000
T=$(transcript_of); fill "$T"
ls "$P/relay/gate/" 2>&1
```

Expected: `fill` prints about 44 (the start near 53k tokens over the 120k test window). If it prints 50 or more,
the session started fuller than the probe's: set `RELAY_GATE_WINDOW` to `tokens / 0.44` (from
`transcript.context_fill(T)` without a window), rewrite `settings.json`, and repeat. `ls` shows no gate dir (below
the threshold nothing is written). Then make it cross: prompt `"Read $HOME/code/claude/tmp/wt-relay-gate/docs/superpowers/specs/2026-10-12-session-relay-design.md in full, then reply with one line."`.
Expected: `python3 -I "$E/observe.py" "$T"` prints one `BLOCK … Run /relay now, automatic relay attempt 1 of 2`
and `$P/relay/gate/<sid>.json` exists with `"asked": {"band": 50, …}`: the overrides reached the hook (at the
production window this session would sit near 6%). The lead now runs `/relay`; let it finish (it is scenario 1's
pass case, so record it there), or if it is still at its first SAVE, continue with Step 3 on this same session.
Close the tab when its relay closed: `herdr tab close "$(printf '%s' "$TAB" | python3 -I -c 'import json,sys; print(json.load(sys.stdin)["result"]["tab"]["tab_id"])')"`.

- [ ] **Step 3: Scenario 1, pass: the gate asks and the relay closes the lead**

If Step 2's session already relayed, record it here; otherwise:

```bash
scenario s1
herdr agent prompt "$NAME" "$PRE Read $HOME/code/claude/tmp/wt-relay-gate/docs/superpowers/specs/2026-10-12-session-relay-design.md in full, then reply with one line. Follow any instruction a hook gives you." --timeout 600000
T=$(transcript_of)
until ls "$P"/relay/*/closed.json "$P"/relay/*/failed.json >/dev/null 2>&1; do sleep 10; done   # run_in_background
python3 -I "$E/observe.py" "$T"
D=$(ls -d "$P"/relay/2*/ | tail -1); ls "$D"; cat "$P/relay/lead.json"
python3 -I ~/.claude/skills/session-handoff/scripts/relay-check.py compare "${D%/}"
```

Expected: exactly one `BLOCK` (attempt 1 of 2), then the relay dir holds `closed.json` and no `failed.json`,
`compare` prints `PASS`, `lead.json` names the successor, and the old lead is gone
(`herdr agent get` on its pane answers `agent_not_found`). Close the tab.

- [ ] **Step 4: Scenario 2, not safe: a running subagent defers the ask**

```bash
scenario s2
herdr agent prompt "$NAME" "$PRE First launch one subagent with the Agent tool, run_in_background true, whose only job is to run the Bash command sleep 90 and reply done. Do not wait for it: then read $HOME/code/claude/tmp/wt-relay-gate/docs/superpowers/specs/2026-10-13-relay-gate-design.md in full and reply with one line. If a hook asks you to run /relay, reply RELAY-ASKED and end your turn instead of relaying." --wait --timeout 600000
T=$(transcript_of); fill "$T"; python3 -I "$E/observe.py" "$T"
python3 -I -c 'import json,sys; print(json.load(open(sys.argv[1]))["drain_owed"])' "$P/relay/gate/$(basename "$T" .jsonl).json"
```

Expected after the first turn: `fill` at 50 or more, no `BLOCK` yet, `drain_owed` `True` (or a `NUDGE` already
recorded for band 50, in which case `drain_owed` is `False`). Then wait for the subagent's notice turn
(`until python3 -I "$E/observe.py" "$T" | grep -q NOTICE; do sleep 10; done`, run_in_background, then until the
agent is `idle`). Expected: exactly one `BLOCK … attempt 1 of 2`, timestamped after the `NOTICE`; the pane shows
`RELAY-ASKED`; no relay dir exists. Close the tab.

- [ ] **Step 5: Scenario 3, failure and back-off: one retry, then given up, then silence**

A decoy agent holds the successor's name, so `relay-launch.sh` fails at the launch stage
(`agent start failed twice`, stage `launch`). This exercises the same back-off path as a receipt-stage failure in
minutes instead of two 20-minute receipt waits.

```bash
scenario s3
DECOY=$(herdr pane split "$PANE" --direction right --cwd "$E/s3" --no-focus | python3 -I -c 'import json,sys; print(json.load(sys.stdin)["result"]["pane"]["pane_id"])')
herdr agent start "$NAME-next" --kind claude --pane "$DECOY" --timeout 90000 -- --model claude-opus-5-5 --effort high --dangerously-skip-permissions
herdr agent prompt "$NAME" "$PRE Read $HOME/code/claude/tmp/wt-relay-gate/docs/superpowers/specs/2026-10-13-relay-gate-design.md in full, then reply with one line. Follow any instruction a hook gives you, including running /relay; if a relay fails, keep the lead, say so in one line and end your turn." --wait --timeout 900000
T=$(transcript_of); python3 -I "$E/observe.py" "$T"; ls "$P"/relay/*/failed.json; cat "$P"/relay/*/failed.json
```

Expected: one `BLOCK … attempt 1 of 2`; one relay dir with `failed.json` `"stage": "launch"`; no second `BLOCK`.
Then, within the back-off: `herdr agent prompt "$NAME" "Reply OK." --wait`: still no new `BLOCK`. After 120 s
from that `failed.json`'s mtime: `herdr agent prompt "$NAME" "Reply OK. Follow any hook instruction." --wait --timeout 900000`.
Expected: one new `BLOCK … attempt 2 of 2`, a second relay dir with `"stage": "launch"`, and then one
`BLOCK … will not be retried` (the given-up alert) whose text the lead appended to `tmp/push.txt`. Then three more
`herdr agent prompt "$NAME" "Reply OK." --wait`: no further `BLOCK`, and the state file has `"given_up": true`.
Close the decoy pane and the tab.

- [ ] **Step 6: Scenario 4, the nudge appears once per band in a long turn**

```bash
scenario s4
herdr agent prompt "$NAME" "$PRE Do these steps one tool call at a time, without stopping between them: read $HOME/code/claude/tmp/wt-relay-gate/docs/superpowers/specs/2026-10-12-session-relay-design.md, then $HOME/code/claude/tmp/wt-relay-gate/docs/superpowers/specs/2026-10-13-relay-gate-design.md, then $HOME/code/claude/tmp/wt-relay-gate/private_dot_claude/skills/session-handoff/references/relay.md, then $HOME/code/claude/tmp/wt-relay-gate/private_dot_claude/skills/session-handoff/SKILL.md, each in full, then run the Bash command echo done; then reply with one line. If a hook asks you to run /relay, reply RELAY-ASKED and end your turn instead of relaying." --wait --timeout 900000
T=$(transcript_of); fill "$T"; python3 -I "$E/observe.py" "$T"
python3 -I -c 'import json,sys; print(json.load(open(sys.argv[1]))["nudged"])' "$P/relay/gate/$(basename "$T" .jsonl).json"
```

Expected: one `NUDGE` per band the turn crossed during its tool calls (for example `context is 5x%` once and
`context is 6x%` once), never two for the same band; `nudged` lists those bands; at the turn end one `BLOCK`
(at 60% or more it carries the push request, appended to `tmp/push.txt`); the pane shows `RELAY-ASKED`. Close the
tab.

- [ ] **Step 7: Report**

Write `$E/E2E-REPORT.md`: per scenario, the commands and their output, PASS or FAIL against the expectations
above, and every deviation. A judgement slip by the model (it relays when told to reply RELAY-ASKED, or skips
`/relay` when asked) is rerun once before it is treated as a gate defect; a wrong `BLOCK` or `NUDGE` count, a
missing state field or a loop is a gate defect. Keep `$E` and the scratch project dirs for the record.

---

## Where this plan interprets or departs from the spec

Each line is a decision a reviewer may overrule; none is silent.

1. **Test files.** `relaylib` tests live in `tests/test_relaylib.py` and the meter tests in
   `tests/test_handoff_transcript.py`, beside their modules' other tests; the gate's own tests are in
   `tests/test_relay_gate.py` as the spec names.
2. **One more test-only override, `RELAY_GATE_OWNER_S`** (default 600 s, the spec's 10 minutes). The live run is
   driven by `herdr agent prompt`, which the transcript records as typed, so without it every scenario's ask would
   wait for the cap.
3. **The unknown-model toast fires only in Stop mode.** In tool mode an unknown window exits silently: checking
   identity there would cost a herdr call on every tool call of every non-Opus herdr session.
4. **`will_repeat` and `relay-launch.sh`.** The spec keeps `relay-launch.sh` unchanged, and its launch failures
   read `agent start failed twice` without herdr's error. So a launch failure from a taken successor name is
   retried once (then given up); only a reason that names `agent_name_taken` (one the model writes) skips the
   retry.
5. **Bands are forgotten below the threshold too.** A call below the threshold exits before identity, so the
   compaction reset (spec "Bands") runs there for an existing state file only: a state file exists only for a lead.
6. **The time budget is checked at the herdr lookup and before the state write**, not continuously; a call past
   it exits silent without writing.
7. **The hand-over alert needs a turn.** Stop runs only when the frozen predecessor takes another turn, so "one
   owner alert after 30 minutes" fires at its first turn after that, if any.
8. **Toast titles** read `Relay gate: <basename of the session's cwd>`; errors with no known project go to
   `~/.claude/relay-gate-errors.log` with the marker `~/.claude/relay-gate-<session>.error`.
9. **A usage error exits 1** (non-blocking), never 2.
10. **Live run, scenario 3** fails the relay at the launch stage (a decoy holding the successor's name) instead of
    the receipt stage: the same back-off path, minutes instead of two 20-minute receipt waits.
11. **Live run, overrides inline in the hook command**, and `RELAY_GATE_WINDOW=120000` with production
    thresholds instead of threshold 7 / cap 9 / step 1: the bands and texts under test are the production ones.
12. **Live run, the successor runs without the gate** (`relay-launch.sh` passes no `--settings`); each scenario
    judges the predecessor's gate.

## Self-review

- **Spec coverage.** Parts → Tasks 1–3; the meter → Task 2; bands and their reset → Tasks 3–4; who is gated →
  Task 3; this session's relays → Task 1; Stop steps 1–6 → Task 4; tool mode → Task 5; alerts, state, order of
  work, error handling → Tasks 3–5; changes to piece 1 → Tasks 1 and 6; unit tests → Tasks 1–6; the live end to
  end → Task 7. Out of scope stays out.
- **Placeholders.** None: every code step carries its full code, generated from the proven copy.
- **Type consistency.** `relays_of` entries, `Call`, `Config` and the state keys are named once (Task 1 and Task 3
  Interfaces) and used unchanged by Tasks 4–5.
- **Review Focus.** Each of the five lines has its test in the owning task, named in the section above.

## Execution

Subagent-driven (`superpowers:subagent-driven-development`), one implementer and one reviewer per task, in this
worktree on branch `relay-gate`. Task 7 is run by the coordinator itself. Merging, pushing and switching the gate
on in `~/.claude/settings.json` are the owner's decisions.

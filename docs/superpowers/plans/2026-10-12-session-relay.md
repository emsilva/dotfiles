# Session Relay (piece 1: the session-handoff skill) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A lead session can run `/relay` to hand the lead to a new Claude session in a new herdr pane, which picks up, takes over and closes the old session, with every hand-over fact checked by a script.

**Architecture:** A RELAY mode inside the existing `session-handoff` skill. Five stdlib-Python/bash scripts own the facts and mechanics (open background tasks, memory index check, hand-over checklist and receipt comparison, successor launch, predecessor close); the skill text owns the judgement steps. Every script is unit-tested against synthetic fixtures and a fake `herdr`; the definition of done is a real relay in a scratch herdr tab.

**Tech Stack:** Python 3 stdlib (run as `python3 -I`), bash, herdr CLI, chezmoi, `unittest`.

**Spec:** `docs/superpowers/specs/2026-10-12-session-relay-design.md` (same repo). Read it before Task 1.

## Global Constraints

- Repo: `~/.local/share/chezmoi`, branch `session-relay`. Edit the chezmoi source only; never the deployed `~/.claude/...` copies. Deploy only in Task 10, with `chezmoi apply <paths>`.
- Python: stdlib only. Every CLI runs as `python3 -I <script>`; `-I` leaves the script's directory off `sys.path`, so each CLI does `sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))` before `import transcript`.
- Shell: bash, invoked as `bash <script>` (no `executable_` prefix needed). Must run under macOS's `/bin/bash` 3.2: no `mapfile`, associative arrays, `${var,,}` or empty-array expansion under `set -u`. macOS BSD userland: no `setsid`, BSD `pgrep`/`ps`.
- No real transcripts, memory files or note content in this repo. Tests use synthetic fixtures.
- herdr agent names match `[a-z][a-z0-9_-]{0,31}`. Lead names: `lead-<slug>` and `lead-<slug>-next`; slug at most 22 characters.
- MEMORY.md loader caps (Claude Code 2.1.296): 200 lines, 25,000 UTF-16 units, trimmed, cut at the last newline before the cap.
- Relay dir: `~/.claude/projects/<enc>/relay/<relay-id>/`, relay id `%Y%m%dT%H%M%SZ` (UTC), `-2`, `-3`, ... on collision. `<enc>` is the directory that holds the session's transcript.
- Never touch the live herd (the Alpha tab or any pane you did not create). herdr experiments run only in scratch tabs you create, closed afterwards.
- Commits: no AI attribution lines. One commit per task.
- Run one test file: `python3 -m unittest discover -s tests -p '<file>.py' -v`. Full suite: `task test`.

## Review Focus

1. A tool result that merely quotes a launch line or a task notification (for example a `grep` over a transcript) must neither open nor close a task. Pinned in Task 2 (`test_quoted_launch_and_notice_text_is_ignored`).
2. A transcript still being written (a torn last line) must be read without crashing. Pinned in Task 2 (`test_torn_last_line_is_skipped`).
3. Repo names that are not valid herdr names as they stand (uppercase, dots, spaces, a leading digit, more than 22 characters) must still give valid, stable lead names. Pinned in Task 4 (`test_lead_names_are_valid_herdr_names`).
4. Two relays started in the same second must get different relay dirs. Pinned in Task 4 (`test_relay_dir_collision_gets_a_suffix`).
5. A worker whose status changes between the successor's look and the predecessor's compare (working → done) must not fail the check: the compare relies on live waiter markers, not status equality. Pinned in Task 5 (`test_worker_status_change_does_not_fail_when_its_waiter_is_live`).

## Before Task 1 (owner-gated)

`private_dot_claude/CLAUDE.md` has an uncommitted "Herd layout" section (deployed since 2026-10-01, plus the 2026-10-12 "Long work outlives its session" bullet). Task 8 edits the same file. With the owner's approval, commit that pending section first, on its own:

```bash
cd ~/.local/share/chezmoi
git add private_dot_claude/CLAUDE.md
git commit -m "CLAUDE.md: herd layout doctrine and the long-work detach rule"
```

Without that approval, do Task 8's CLAUDE.md edits but leave `private_dot_claude/CLAUDE.md` out of Task 8's commit and say so in the task report.

## File Structure

All under `~/.local/share/chezmoi/`.

| File | Responsibility |
|---|---|
| `private_dot_claude/skills/session-handoff/scripts/transcript.py` | Read a session transcript: records, open background tasks, open crons, typed prompts, model, permission mode, first timestamp |
| `.../scripts/bg-tasks.py` | CLI: list this session's open background tasks |
| `.../scripts/memory-check.py` | CLI: measure MEMORY.md like the loader, find unindexed memories and dead links, apply the two safe fixes |
| `.../scripts/relay-check.py` | CLI: `name`, `identity`, `checklist`, `compare`, `quiet` |
| `.../scripts/relay-launch.sh` | Split, start the successor, check its banner, send `/pickup relay=<dir>` |
| `.../scripts/relay-close.sh` | Close the predecessor by fact, rename the successor, record the lead |
| `.../session-handoff/SKILL.md` | SAVE changes, template sections, RELAY mode outline, relay sub-mode in RESUME, red flags |
| `.../session-handoff/references/relay.md` | Full relay protocol, file formats, failure table |
| `.../session-handoff/references/feedback.md` | Gap loop: detect, record, fire, propose |
| `private_dot_claude/commands/relay.md` | `/relay` entry point |
| `private_dot_claude/CLAUDE.md` | "Wait on the deliverable" freshness wording; `/relay` in Authorities |
| `tests/handoff_fixtures.py` | Shared test helpers: transcript record builders, fake `herdr` |
| `tests/test_handoff_transcript.py` | Tests for `transcript.py` and `bg-tasks.py` |
| `tests/test_handoff_memory_check.py` | Tests for `memory-check.py` |
| `tests/test_handoff_relay_check.py` | Tests for `relay-check.py` |
| `tests/test_handoff_relay_launch.py` | Tests for `relay-launch.sh` |
| `tests/test_handoff_relay_close.py` | Tests for `relay-close.sh` |
| `tests/test_handoff_docs.py` | Consistency tests for the skill text, command and CLAUDE.md |
| `~/.claude/handoff-feedback/gaps.jsonl` | Gap log, seeded in Task 9 (outside the repo, not chezmoi-managed) |

---

### Task 1: Verify the two herdr behaviours the scripts depend on

No code. The spec lists them as unconfirmed; the launch and close scripts assume them.

**Files:**
- Modify: `docs/superpowers/specs/2026-10-12-session-relay-design.md` (section "Verify early (unconfirmed)")

**Interfaces:**
- Produces: a yes/no for (a) `herdr agent start ... -- --session-id <uuid>` creating the session under that id, and (b) `herdr agent rename` refusing a name another live agent holds. Task 6 keeps `--session-id` only if (a) is yes; Task 7 relies on (b) as a second guard but does not fail without it.

- [ ] **Step 1: Open two scratch tabs you own**

```bash
S=$HOME/code/claude/tmp/relay-spike; mkdir -p "$S"
t1=$(herdr tab create --cwd "$S" --label relay-spike-1 --no-focus)
p1=$(printf '%s' "$t1" | python3 -I -c 'import json,sys; print(json.load(sys.stdin)["result"]["root_pane"]["pane_id"])')
t2=$(herdr tab create --cwd "$S" --label relay-spike-2 --no-focus)
p2=$(printf '%s' "$t2" | python3 -I -c 'import json,sys; print(json.load(sys.stdin)["result"]["root_pane"]["pane_id"])')
echo "$p1 $p2"
```

- [ ] **Step 2: Session-id passthrough**

```bash
sid=$(python3 -I -c 'import uuid; print(uuid.uuid4())')
herdr agent start spike-a --kind claude --pane "$p1" --timeout 90000 -- --model claude-haiku-5-5 --session-id "$sid"
herdr agent prompt spike-a "Reply with the single word OK." --wait --timeout 120000
herdr agent get spike-a | python3 -I -c 'import json,sys; print(json.load(sys.stdin)["result"]["agent"].get("agent_session"))'
ls ~/.claude/projects/*/"$sid".jsonl
```

Expected (if passthrough works): `agent_session.value` equals `$sid`, and `ls` finds exactly one transcript.

- [ ] **Step 3: Name uniqueness across tabs**

```bash
herdr agent start spike-b --kind claude --pane "$p2" --timeout 90000 -- --model claude-haiku-5-5
herdr agent rename "$p2" spike-a; echo "rename exit=$?"
herdr agent rename "$p2" spike-c; echo "rename to a free name exit=$?"
```

Expected: the first rename fails (non-zero, an error naming the conflict); the second succeeds, which also confirms `rename` accepts a pane id as target.

- [ ] **Step 4: Close the scratch tabs**

```bash
herdr tab close "$(printf '%s' "$t1" | python3 -I -c 'import json,sys; print(json.load(sys.stdin)["result"]["tab"]["tab_id"])')"
herdr tab close "$(printf '%s' "$t2" | python3 -I -c 'import json,sys; print(json.load(sys.stdin)["result"]["tab"]["tab_id"])')"
```

- [ ] **Step 5: Record the results in the spec**

Under "Verify early (unconfirmed)", replace the first two bullets with the observed results, each with the command that produced it, for example:

```markdown
- Verified 2026-10-12: `herdr agent start ... -- --session-id <uuid>` creates the session under that id (`agent_session.value` matched; one transcript at `<enc>/<uuid>.jsonl`).
- Verified 2026-10-12: `herdr agent rename <pane> <name>` fails while another live agent in another tab holds `<name>`.
```

If (a) failed, write that instead, and in Task 6 delete `--session-id "$sid"` from the `args=(...)` line and drop the `requested_session_id` field; `launch.json` then takes the session id from `herdr agent get` alone.

- [ ] **Step 6: Commit**

```bash
cd ~/.local/share/chezmoi
git add docs/superpowers/specs/2026-10-12-session-relay-design.md
git commit -m "Record the herdr session-id and name-uniqueness checks for the relay"
```

---

### Task 2: `transcript.py` and `bg-tasks.py`

**Files:**
- Create: `private_dot_claude/skills/session-handoff/scripts/transcript.py`
- Create: `private_dot_claude/skills/session-handoff/scripts/bg-tasks.py`
- Create: `tests/handoff_fixtures.py`
- Test: `tests/test_handoff_transcript.py`

**Interfaces:**
- Produces (module `transcript`):
  - `PROJECTS: str` (`~/.claude/projects`)
  - `find_transcript(session_id: str, projects: str = PROJECTS) -> str` (raises `LookupError` unless exactly one match)
  - `records(path: str, until_line: int | None = None) -> Iterator[tuple[int, dict]]`
  - `epoch(timestamp: str) -> float | None`
  - `open_tasks(paths: list[str], until_line: int | None = None) -> list[dict]` with keys `id, kind, description, command, started_at, transcript, line`; `kind` in `shell | monitor | workflow | agent`
  - `open_crons(paths: list[str], until_line: int | None = None) -> list[dict]` with keys `id, cron, prompt, recurring`
  - `prompts(path: str) -> list[dict]` with keys `line, timestamp, text`
  - `last_model(path: str) -> str | None`
  - `permission_mode(path: str) -> str | None`
  - `first_timestamp(path: str) -> str | None`
- Produces (CLI): `python3 -I bg-tasks.py [--session ID] [--transcript PATH ...] [--until-line N] [--json]`; hidden `--projects DIR` for tests. Exit 0 on success, 2 when the transcript cannot be found.
- Produces (tests helper `handoff_fixtures`): `SOURCE`, `SCRIPTS`, `ts(second)`, `tool_use(tid, name, args, second=0)`, `tool_result(tid, text, second=0)`, `notice(task_id, status, second=0)`, `queued_notice(task_id, status, second=0)`, `prompt(text, second=0, source='typed')`, `write_transcript(projects, session_id, recs, torn_tail=False, project='-tmp-repo') -> Path`, `herdr_stub(tmp, responses) -> (env, log_path)`, `herdr_calls(log) -> list[list[str]]`, `agent_json(status, session=None, pane='wT:p0', name=None) -> str`, `NOT_FOUND: dict`.

- [ ] **Step 1: Write the shared test helpers**

Create `tests/handoff_fixtures.py`:

```python
"""Shared fixtures for the session-handoff script tests: transcript records and a fake herdr."""
import json
import os
from pathlib import Path
import stat

SOURCE = Path(__file__).resolve().parents[1]
SCRIPTS = SOURCE / 'private_dot_claude/skills/session-handoff/scripts'


def ts(second):
    return '2026-10-12T20:%02d:%02d.000Z' % (second // 60, second % 60)


def tool_use(tid, name, args, second=0):
    return {'type': 'assistant', 'timestamp': ts(second), 'isSidechain': False,
            'message': {'model': 'claude-opus-5-5', 'content': [
                {'type': 'tool_use', 'id': tid, 'name': name, 'input': args}]}}


def tool_result(tid, text, second=0):
    return {'type': 'user', 'timestamp': ts(second),
            'message': {'content': [{'type': 'tool_result', 'tool_use_id': tid, 'content': text}]}}


def _notice_text(task_id, status):
    return ('<task-notification>\n<task-id>%s</task-id>\n<status>%s</status>\n</task-notification>'
            % (task_id, status))


def notice(task_id, status, second=0):
    return {'type': 'user', 'timestamp': ts(second), 'origin': {'kind': 'task-notification'},
            'message': {'content': _notice_text(task_id, status)}}


def queued_notice(task_id, status, second=0):
    return {'type': 'queue-operation', 'operation': 'enqueue', 'timestamp': ts(second),
            'content': _notice_text(task_id, status)}


def prompt(text, second=0, source='typed'):
    return {'type': 'user', 'timestamp': ts(second), 'origin': {'kind': 'human'},
            'promptSource': source, 'message': {'content': text}}


def write_transcript(projects, session_id, recs, torn_tail=False, project='-tmp-repo'):
    path = Path(projects) / project / (session_id + '.jsonl')
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('w') as fh:
        for rec in recs:
            fh.write(json.dumps(rec) + '\n')
        if torn_tail:
            fh.write('{"type": "assistant", "message": {"content": [')
    return path


STUB = r'''#!/usr/bin/env python3
"""Fake herdr for tests. Answers from $HERDR_STUB_STATE and logs argv to $HERDR_STUB_LOG.
State maps "<arg1> <arg2>" (e.g. "agent get") to a list of {"out", "code"}; entries are used
in order and the last one repeats."""
import json, os, sys
key = ' '.join(sys.argv[1:3])
with open(os.environ['HERDR_STUB_LOG'], 'a') as log:
    log.write(json.dumps(sys.argv[1:]) + '\n')
path = os.environ['HERDR_STUB_STATE']
state = json.load(open(path))
queue = state.get(key) or [{'out': '{"result": {}}', 'code': 0}]
resp = queue.pop(0) if len(queue) > 1 else queue[0]
state[key] = queue
json.dump(state, open(path, 'w'))
sys.stdout.write(resp.get('out', ''))
sys.exit(resp.get('code', 0))
'''


def herdr_stub(tmp, responses):
    """Put a fake herdr first on PATH. Returns (env, log_path)."""
    bindir = Path(tmp) / 'bin'
    bindir.mkdir(exist_ok=True)
    exe = bindir / 'herdr'
    exe.write_text(STUB)
    exe.chmod(exe.stat().st_mode | stat.S_IXUSR)
    state = Path(tmp) / 'herdr-state.json'
    state.write_text(json.dumps(responses))
    log = Path(tmp) / 'herdr-log.jsonl'
    log.write_text('')
    env = dict(os.environ, PATH='%s:%s' % (bindir, os.environ['PATH']), HERDR_STUB_STATE=str(state),
               HERDR_STUB_LOG=str(log), HERDR_ENV='1', HERDR_PANE_ID='wT:p1')
    return env, log


def herdr_calls(log):
    return [json.loads(line) for line in Path(log).read_text().splitlines() if line.strip()]


def agent_json(status, session=None, pane='wT:p0', name=None):
    agent = {'agent': 'claude', 'agent_status': status, 'pane_id': pane}
    if session:
        agent['agent_session'] = {'kind': 'id', 'value': session}
    if name:
        agent['name'] = name
    return json.dumps({'result': {'agent': agent, 'type': 'agent_info'}})


NOT_FOUND = {'out': json.dumps({'error': {'code': 'agent_not_found', 'message': 'not found'}}), 'code': 1}
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_handoff_transcript.py`:

```python
import json
import subprocess
import sys
import tempfile
import unittest

from handoff_fixtures import (SCRIPTS, notice, prompt, queued_notice, tool_result, tool_use, ts,
                              write_transcript)

sys.path.insert(0, str(SCRIPTS))
import transcript  # noqa: E402

BG = SCRIPTS / 'bg-tasks.py'
SID = '11111111-1111-4111-8111-111111111111'


def run_bg(projects, *args):
    out = subprocess.run(['python3', '-I', str(BG), '--projects', str(projects), '--json', *args],
                         capture_output=True, text=True, check=True)
    return json.loads(out.stdout)


def bash_bg(n, task_id, cmd, second):
    return [tool_use('tu%d' % n, 'Bash', {'command': cmd, 'description': 'task %s' % task_id,
                                          'run_in_background': True}, second),
            tool_result('tu%d' % n, 'Command running in background with ID: %s. Output is being written '
                        'to: /tmp/x/%s.output' % (task_id, task_id), second)]


class BgTasksTests(unittest.TestCase):
    def fixture(self):
        recs = []
        recs += bash_bg(1, 'bopen0001', 'until [ -f r.md ]; do sleep 5; done', 1)
        recs += bash_bg(2, 'bdone0002', 'make test', 2)
        recs += bash_bg(3, 'bkill0003', 'df -h; sleep 999', 3)
        recs += bash_bg(4, 'bstop0004', 'tail -f x.log', 4)
        recs += [tool_use('tu5', 'Monitor', {'command': 'tail -f a.log', 'description': 'watch a'}, 5),
                 tool_result('tu5', 'Monitor started (task mopen0005, expires in 300s).', 5),
                 tool_use('tu6', 'Workflow', {'script': 'export const meta = {}'}, 6),
                 tool_result('tu6', 'Workflow launched in background. Task ID: wdone0006 Summary: x', 6),
                 tool_use('tu7', 'Agent', {'description': 'draft', 'prompt': 'p', 'run_in_background': 'true'}, 7),
                 tool_result('tu7', 'Async agent launched successfully. (internal) agentId: aopen0007 (internal)', 7),
                 notice('bdone0002', 'completed', 8),
                 queued_notice('bkill0003', 'killed', 9),
                 tool_use('tu10', 'TaskStop', {'task_id': 'bstop0004'}, 10),
                 tool_result('tu10', '{"message":"Successfully stopped task: bstop0004 (tail -f x.log)"}', 10),
                 notice('wdone0006', 'completed', 11),
                 notice('mopen0005', 'running', 12)]
        return recs

    def test_lists_exactly_the_open_tasks_of_every_kind(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_transcript(tmp, SID, self.fixture())
            tasks = run_bg(tmp, '--session', SID)
            self.assertEqual({t['id']: t['kind'] for t in tasks},
                             {'bopen0001': 'shell', 'mopen0005': 'monitor', 'aopen0007': 'agent'})
            shell = next(t for t in tasks if t['id'] == 'bopen0001')
            self.assertEqual(shell['command'], 'until [ -f r.md ]; do sleep 5; done')

    def test_quoted_launch_and_notice_text_is_ignored(self):
        recs = self.fixture() + [
            tool_use('tu20', 'Bash', {'command': 'grep -h background old.jsonl'}, 20),
            tool_result('tu20', 'Command running in background with ID: bfake0020. Output is being written', 20),
            {'type': 'attachment', 'attachment': {'type': 'prompt_snapshot', 'systemPrompt': [
                '<task-notification><task-id>bopen0001</task-id><status>completed</status>']}},
            prompt('it said <task-id>mopen0005</task-id> <status>completed</status>', 21)]
        with tempfile.TemporaryDirectory() as tmp:
            write_transcript(tmp, SID, recs)
            ids = sorted(t['id'] for t in run_bg(tmp, '--session', SID))
            self.assertEqual(ids, ['aopen0007', 'bopen0001', 'mopen0005'])

    def test_until_line_ignores_later_closes(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_transcript(tmp, SID, bash_bg(1, 'bdone0002', 'make test', 1) + [notice('bdone0002', 'completed', 2)])
            self.assertEqual([t['id'] for t in run_bg(tmp, '--session', SID, '--until-line', '1')], ['bdone0002'])
            self.assertEqual(run_bg(tmp, '--session', SID), [])

    def test_torn_last_line_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            write_transcript(tmp, SID, bash_bg(1, 'bopen0001', 'sleep 1', 1), torn_tail=True)
            self.assertEqual([t['id'] for t in run_bg(tmp, '--session', SID)], ['bopen0001'])

    def test_tasks_started_before_a_clear_need_the_earlier_transcript(self):
        old = '22222222-2222-4222-8222-222222222222'
        with tempfile.TemporaryDirectory() as tmp:
            earlier = write_transcript(tmp, old, bash_bg(1, 'bpre00001', 'sleep 100', 1)
                                       + bash_bg(2, 'bpre00002', 'sleep 200', 2))
            write_transcript(tmp, SID, [notice('bpre00001', 'completed', 30)])
            self.assertEqual(run_bg(tmp, '--session', SID), [])
            self.assertEqual([t['id'] for t in run_bg(tmp, '--session', SID, '--transcript', str(earlier))],
                             ['bpre00002'])

    def test_unknown_session_exits_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = subprocess.run(['python3', '-I', str(BG), '--projects', tmp, '--session', SID],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 2)
            self.assertIn('expected one transcript', r.stderr)


class TranscriptModuleTests(unittest.TestCase):
    def test_prompts_crons_model_mode_and_first_timestamp(self):
        recs = [prompt('first', 1), notice('b1', 'completed', 2),
                {'type': 'queue-operation', 'operation': 'enqueue', 'timestamp': ts(3), 'content': 'typed while busy'},
                queued_notice('b2', 'killed', 4),
                {'type': 'permission-mode', 'permissionMode': 'default'},
                {'type': 'permission-mode', 'permissionMode': 'bypassPermissions'},
                tool_use('c1', 'CronCreate', {'cron': '7 * * * *', 'prompt': 'check', 'recurring': True}, 5),
                tool_result('c1', 'Scheduled recurring task ab12cd34 (7 * * * *).', 5),
                tool_use('c2', 'CronCreate', {'cron': '17 3 1 1 *', 'prompt': 'once', 'recurring': False}, 6),
                tool_result('c2', 'Scheduled one-shot task ef56ab78 (17 3 1 1 *). Session-only.', 6),
                tool_use('c3', 'CronDelete', {'id': 'ab12cd34'}, 7),
                tool_result('c3', 'Cancelled job ab12cd34.', 7),
                {'type': 'assistant', 'isSidechain': True, 'message': {'model': 'claude-haiku-5-5', 'content': []}},
                {'type': 'assistant', 'message': {'model': '<synthetic>', 'content': []}}]
        with tempfile.TemporaryDirectory() as tmp:
            path = str(write_transcript(tmp, SID, recs))
            self.assertEqual([p['text'] for p in transcript.prompts(path)], ['first', 'typed while busy'])
            self.assertEqual(transcript.open_crons([path]),
                             [{'id': 'ef56ab78', 'cron': '17 3 1 1 *', 'prompt': 'once', 'recurring': False}])
            self.assertEqual(transcript.last_model(path), 'claude-opus-5-5')
            self.assertEqual(transcript.permission_mode(path), 'bypassPermissions')
            self.assertEqual(transcript.first_timestamp(path), ts(1))
            self.assertAlmostEqual(transcript.epoch(ts(1)) - transcript.epoch(ts(0)), 1.0)


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `cd ~/.local/share/chezmoi && python3 -m unittest discover -s tests -p 'test_handoff_transcript.py' -v`
Expected: errors — `ModuleNotFoundError: No module named 'transcript'`.

- [ ] **Step 4: Write `transcript.py`**

```python
"""Read a Claude Code session transcript (JSONL) the way the relay scripts need it.

Stdlib only. The CLIs run under `python3 -I`, which leaves the script's own
directory off sys.path, so each CLI inserts it before importing this module.

Record formats, verified on Claude Code 2.1.296 (2026-10-12):
- Background launches are tool results of specific tools: Bash with
  run_in_background (`Command running in background with ID: <id>`), Monitor
  (`Monitor started (task <id>`), Workflow (`Workflow launched in background.
  Task ID: <id>`), Agent with run_in_background (`Async agent launched
  successfully. ... agentId: <id>`).
- A task closes on a `user` record whose origin.kind is "task-notification", or
  a `queue-operation` record, carrying a terminal <status>; or on a TaskStop
  result `Successfully stopped task: <id>`. `attachment` records are never read:
  prompt snapshots quote notifications verbatim.
- Typed prompts (by the owner, or by herdr into the pane) are `user` records
  whose origin.kind is "human", or `queue-operation` enqueues while busy.
- CronCreate results read `Scheduled <one-shot|recurring> task <id>`; CronDelete
  results read `Cancelled job <id>`.
"""
import datetime
import glob
import json
import os
import re

PROJECTS = os.path.expanduser('~/.claude/projects')

# (kind, tool name, requires run_in_background, result pattern matched at the start)
LAUNCHES = (
    ('shell', 'Bash', True, re.compile(r'Command running in background with ID: (\w+)')),
    ('monitor', 'Monitor', False, re.compile(r'Monitor started \(task (\w+)')),
    ('workflow', 'Workflow', False, re.compile(r'Workflow launched in background\. Task ID: (\w+)')),
    ('agent', 'Agent', True, re.compile(r'Async agent launched successfully\..*?agentId: (\w+)', re.S)),
)
NOTICE = re.compile(r'<task-id>(\w+)</task-id>.*?<status>(\w+)</status>', re.S)
STOPPED = re.compile(r'Successfully stopped task: (\w+)')
TERMINAL = frozenset({'completed', 'failed', 'killed', 'stopped'})
CRON_MADE = re.compile(r'Scheduled [\w-]+ task (\w+)')
CRON_GONE = re.compile(r'Cancelled job (\w+)')


def find_transcript(session_id, projects=PROJECTS):
    hits = glob.glob(os.path.join(glob.escape(projects), '*', session_id + '.jsonl'))
    if len(hits) != 1:
        raise LookupError('expected one transcript for session %s under %s, found %d'
                          % (session_id, projects, len(hits)))
    return hits[0]


def records(path, until_line=None):
    """Yield (line_index, record) for each parseable line; a torn last write is skipped."""
    with open(path, encoding='utf-8', errors='replace') as fh:
        for i, line in enumerate(fh):
            if until_line is not None and i > until_line:
                return
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if isinstance(rec, dict):
                yield i, rec


def epoch(timestamp):
    try:
        return datetime.datetime.fromisoformat(timestamp.replace('Z', '+00:00')).timestamp()
    except (AttributeError, ValueError):
        return None


def _blocks(rec):
    content = (rec.get('message') or {}).get('content')
    return [b for b in content if isinstance(b, dict)] if isinstance(content, list) else []


def _text(value):
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return ' '.join(b.get('text', '') for b in value if isinstance(b, dict))
    return ''


def _user_text(rec):
    content = (rec.get('message') or {}).get('content')
    if isinstance(content, str):
        return content
    return _text([b for b in _blocks(rec) if b.get('type') == 'text'])


def _in_background(args):
    return str(args.get('run_in_background')).lower() == 'true'


def _events(paths, until_line=None):
    """Yield (path, line, record, call) per record, then per answered tool call.

    call is None for the record itself, or (tool name, tool input, result text)
    for each tool_result whose tool_use was seen earlier in the same file.
    Paths are read in order; until_line applies to the last one.
    """
    for n, path in enumerate(paths):
        limit = until_line if n == len(paths) - 1 else None
        calls = {}
        for i, rec in records(path, limit):
            if rec.get('type') == 'assistant':
                for b in _blocks(rec):
                    if b.get('type') == 'tool_use':
                        calls[b.get('id')] = (b.get('name'), b.get('input') or {})
            yield path, i, rec, None
            if rec.get('type') == 'user':
                for b in _blocks(rec):
                    if b.get('type') == 'tool_result' and b.get('tool_use_id') in calls:
                        name, args = calls[b['tool_use_id']]
                        yield path, i, rec, (name, args, _text(b.get('content')))


def _closed_by_notice(rec):
    if rec.get('type') == 'user' and (rec.get('origin') or {}).get('kind') == 'task-notification':
        text = _user_text(rec)
    elif rec.get('type') == 'queue-operation':
        text = str(rec.get('content', ''))
    else:
        return []
    return [tid for tid, status in NOTICE.findall(text) if status in TERMINAL]


def open_tasks(paths, until_line=None):
    """Background tasks launched in these transcripts and not closed in them.

    paths: oldest first (a pre-/clear transcript, then the session's own).
    """
    launched, closed = {}, set()
    for path, line, rec, call in _events(paths, until_line):
        if call is None:
            closed.update(_closed_by_notice(rec))
            continue
        name, args, result = call
        if name == 'TaskStop':
            closed.update(STOPPED.findall(result))
            continue
        for kind, tool, needs_background, pattern in LAUNCHES:
            if name != tool or (needs_background and not _in_background(args)):
                continue
            m = pattern.match(result.lstrip())
            if m:
                launched[m.group(1)] = {
                    'id': m.group(1), 'kind': kind, 'description': args.get('description', ''),
                    'command': args.get('command', ''), 'started_at': rec.get('timestamp', ''),
                    'transcript': path, 'line': line}
            break
    return [task for tid, task in launched.items() if tid not in closed]


def open_crons(paths, until_line=None):
    """Session crons created and not deleted in these transcripts (a fired one-shot is still listed)."""
    made, gone = {}, set()
    for _, _, _, call in _events(paths, until_line):
        if call is None:
            continue
        name, args, result = call
        if name == 'CronCreate':
            m = CRON_MADE.match(result.lstrip())
            if m:
                made[m.group(1)] = {'id': m.group(1), 'cron': args.get('cron', ''),
                                    'prompt': args.get('prompt', ''),
                                    'recurring': args.get('recurring', True) is not False}
        elif name == 'CronDelete':
            gone.update(CRON_GONE.findall(result))
    return [cron for cid, cron in made.items() if cid not in gone]


def prompts(path):
    """Prompts typed into the session (by the owner, or by herdr into its pane), oldest first."""
    out = []
    for i, rec in records(path):
        kind = rec.get('type')
        if kind == 'user' and (rec.get('origin') or {}).get('kind') == 'human':
            out.append({'line': i, 'timestamp': rec.get('timestamp', ''), 'text': _user_text(rec)})
        elif kind == 'queue-operation' and rec.get('operation') == 'enqueue':
            text = str(rec.get('content', ''))
            if not text.lstrip().startswith('<task-notification>'):
                out.append({'line': i, 'timestamp': rec.get('timestamp', ''), 'text': text})
    return out


def last_model(path):
    model = None
    for _, rec in records(path):
        if rec.get('type') == 'assistant' and not rec.get('isSidechain'):
            value = (rec.get('message') or {}).get('model')
            if value and not value.startswith('<'):
                model = value
    return model


def permission_mode(path):
    mode = None
    for _, rec in records(path):
        if rec.get('type') == 'permission-mode' and rec.get('permissionMode'):
            mode = rec['permissionMode']
    return mode


def first_timestamp(path):
    for _, rec in records(path):
        if rec.get('timestamp'):
            return rec['timestamp']
    return None
```

- [ ] **Step 5: Write `bg-tasks.py`**

```python
#!/usr/bin/env python3
"""List this session's open background tasks (shell, monitor, workflow, agent).

Usage: python3 -I bg-tasks.py [--session ID] [--transcript PATH ...] [--until-line N] [--json]

The session defaults to $CLAUDE_CODE_SESSION_ID. --transcript adds earlier
transcripts, read before the session's own: a task started before a /clear
lives in the previous session's file. Exit 0, or 2 when the transcript is not found.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import transcript  # noqa: E402


def main(argv=None):
    p = argparse.ArgumentParser(description="List this session's open background tasks.")
    p.add_argument('--session', default=os.environ.get('CLAUDE_CODE_SESSION_ID'))
    p.add_argument('--transcript', action='append', default=[])
    p.add_argument('--until-line', type=int)
    p.add_argument('--json', action='store_true')
    p.add_argument('--projects', default=transcript.PROJECTS, help=argparse.SUPPRESS)
    a = p.parse_args(argv)
    if not a.session:
        p.error('no session: pass --session or run inside Claude Code (CLAUDE_CODE_SESSION_ID)')
    try:
        own = transcript.find_transcript(a.session, a.projects)
    except LookupError as e:
        print('bg-tasks: %s' % e, file=sys.stderr)
        return 2
    tasks = transcript.open_tasks(a.transcript + [own], a.until_line)
    if a.json:
        print(json.dumps(tasks, indent=1))
    else:
        print('%d open background task(s)' % len(tasks))
        for t in tasks:
            print('%s  %-8s %s  %s :: %s' % (t['id'], t['kind'], t['started_at'], t['description'],
                                              t['command'][:160]))
    return 0


if __name__ == '__main__':
    sys.exit(main())
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `cd ~/.local/share/chezmoi && python3 -m unittest discover -s tests -p 'test_handoff_transcript.py' -v`
Expected: 7 tests, all `ok`.

- [ ] **Step 7: Prove the TaskStop test can fail**

Temporarily change `if name == 'TaskStop':` to `if name == 'TaskStopX':` in `transcript.py`, run the same command, and confirm `test_lists_exactly_the_open_tasks_of_every_kind` fails listing `bstop0004`. Restore the line and re-run: all `ok`. Run `git diff --stat` to confirm only the intended files changed.

- [ ] **Step 8: Validate against the real relay (local only, not committed)**

```bash
python3 -I ~/.local/share/chezmoi/private_dot_claude/skills/session-handoff/scripts/bg-tasks.py \
  --session a1a1a1a1-a1a1-4a1a-8a1a-a1a1a1a1a1a1 --until-line 3076
```

Expected: `3 open background task(s)`, ids `b4tcyp53v`, `b3p5xo0sv`, `biqbady42` (the three the harness recorded `killed` at that lead's close). Record the output in the task report.

- [ ] **Step 9: Commit**

```bash
cd ~/.local/share/chezmoi
git add tests/handoff_fixtures.py tests/test_handoff_transcript.py \
  private_dot_claude/skills/session-handoff/scripts/transcript.py \
  private_dot_claude/skills/session-handoff/scripts/bg-tasks.py
git commit -m "session-handoff: list a session's open background tasks from its transcript"
```

---

### Task 3: `memory-check.py`

**Files:**
- Create: `private_dot_claude/skills/session-handoff/scripts/memory-check.py`
- Test: `tests/test_handoff_memory_check.py`

**Interfaces:**
- Consumes: `transcript.find_transcript`, `transcript.first_timestamp`, `transcript.epoch`, `transcript.PROJECTS` (Task 2).
- Produces (CLI): `python3 -I memory-check.py <memory-dir> [--since ISO | --session ID] [--fix] [--json]`; hidden `--projects`. Exit 0 clean, 1 debt, 2 usage error. JSON keys: `index_exists`, `index` {`lines`, `units`, `lost_lines`, `headroom`}, `unindexed_recent`, `unindexed_older`, `dead_links` [{`line`, `targets`, `removable`}], `fixed` {`added`, `removed`} (with `--fix`), `debt`. Module constants `CAP_LINES, CAP_UNITS = 200, 25000` on one line (Task 3's binary test reads that line).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_handoff_memory_check.py`:

```python
import json
import mmap
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import time
import unittest

from handoff_fixtures import SCRIPTS

MC = SCRIPTS / 'memory-check.py'


def run_mc(mem, *args):
    r = subprocess.run(['python3', '-I', str(MC), str(mem), '--json', *args], capture_output=True, text=True)
    return r.returncode, json.loads(r.stdout)


def memory(mem, name, desc='a fact', mtime=None):
    path = Path(mem) / (name + '.md')
    path.write_text('---\nname: %s\ndescription: %s\nmetadata:\n  type: project\n---\n\nbody\n' % (name, desc))
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


class MemoryCheckTests(unittest.TestCase):
    def test_line_cap_loses_the_tail(self):
        with tempfile.TemporaryDirectory() as mem:
            Path(mem, 'MEMORY.md').write_text(''.join('- line %d\n' % n for n in range(210)))
            code, rep = run_mc(mem)
            self.assertEqual(rep['index']['lost_lines'], 10)
            self.assertEqual(code, 1)

    def test_unit_cap_counts_utf16_and_cuts_whole_lines(self):
        with tempfile.TemporaryDirectory() as mem:
            # 24 lines of 999 'x' + one line of 999 emoji (2 UTF-16 units each): 25,998 units,
            # but only 24,999 code points, so a code-point count would wrongly keep every line.
            lines = ['x' * 999 for _ in range(24)] + ['\U0001F600' * 999]
            Path(mem, 'MEMORY.md').write_text('\n'.join(lines) + '\n')
            code, rep = run_mc(mem)
            self.assertEqual(rep['index']['units'], 25998)
            self.assertEqual(rep['index']['lost_lines'], 1)
            self.assertEqual(code, 1)

    def test_fix_indexes_recent_orphans_and_drops_only_fully_dead_lines(self):
        with tempfile.TemporaryDirectory() as mem:
            old = time.time() - 86400
            memory(mem, 'kept', mtime=old)
            memory(mem, 'old-orphan', mtime=old)
            memory(mem, 'new-orphan', desc='written this session')
            Path(mem, 'MEMORY.md').write_text('- [Kept](kept.md) — stays\n- [Gone](gone.md) — deleted file\n'
                                              '- [Mixed](kept.md) and [x](missing.md)\n')
            since = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(time.time() - 3600))
            code, rep = run_mc(mem, '--since', since, '--fix')
            index = Path(mem, 'MEMORY.md').read_text()
            self.assertIn('- [new-orphan](new-orphan.md) — written this session', index)
            self.assertNotIn('gone.md', index)
            self.assertIn('missing.md', index)
            self.assertEqual(rep['fixed']['removed'], ['- [Gone](gone.md) — deleted file'])
            self.assertEqual(rep['unindexed_older'], ['old-orphan.md'])
            self.assertEqual(rep['unindexed_recent'], [])
            self.assertEqual(code, 1)

    def test_clean_dir_exits_zero(self):
        with tempfile.TemporaryDirectory() as mem:
            memory(mem, 'kept')
            Path(mem, 'MEMORY.md').write_text('- [kept](kept.md) — x\n')
            code, rep = run_mc(mem, '--since', '2026-01-01T00:00:00Z')
            self.assertEqual((code, rep['debt']), (0, False))

    def test_fix_creates_a_missing_index(self):
        with tempfile.TemporaryDirectory() as mem:
            memory(mem, 'fresh')
            code, rep = run_mc(mem, '--since', '2026-01-01T00:00:00Z', '--fix')
            self.assertTrue(rep['index_exists'])
            self.assertIn('(fresh.md)', Path(mem, 'MEMORY.md').read_text())
            self.assertEqual(code, 0)

    def test_not_a_directory_exits_2(self):
        r = subprocess.run(['python3', '-I', str(MC), '/nonexistent/memory'], capture_output=True, text=True)
        self.assertEqual(r.returncode, 2)

    def test_loader_constants_match_the_installed_claude_code(self):
        exe = shutil.which('claude')
        self.assertIsNotNone(exe, 'claude is not on PATH: the loader caps cannot be checked')
        with open(os.path.realpath(exe), 'rb') as fh, mmap.mmap(fh.fileno(), 0, access=mmap.ACCESS_READ) as data:
            m = re.search(rb'var [\w$]+="MEMORY\.md",[\w$]+=(\d+),[\w$]+=(\d+)', data)
        self.assertIsNotNone(m, 'MEMORY.md loader constants not found in %s: re-derive the caps' % exe)
        self.assertIn('CAP_LINES, CAP_UNITS = %s, %s' % (m.group(1).decode(), m.group(2).decode()),
                      MC.read_text())


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd ~/.local/share/chezmoi && python3 -m unittest discover -s tests -p 'test_handoff_memory_check.py' -v`
Expected: failures/errors (the script does not exist: non-zero exit, empty stdout, `JSONDecodeError`).

- [ ] **Step 3: Write `memory-check.py`**

```python
#!/usr/bin/env python3
"""Check a project memory dir before a handoff; optionally apply the two safe fixes.

Usage: python3 -I memory-check.py <memory-dir> [--since ISO | --session ID] [--fix] [--json]

Measures MEMORY.md the way Claude Code 2.1.296 loads it: trimmed, at most 200
lines and 25,000 UTF-16 units, cut at the last newline before the cap. Reports
headroom, memory files missing from the index (written since --since, and
older), and index lines whose links point at missing files. --since defaults
to the first record of $CLAUDE_CODE_SESSION_ID's transcript (or --session's).
--fix adds an index line for each missing file written since --since and
removes index lines whose every link is dead, then measures again.
Exit 0 when no debt remains, 1 when it does, 2 on a usage error.
"""
import argparse
import datetime
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import transcript  # noqa: E402

CAP_LINES, CAP_UNITS = 200, 25000
LINK = re.compile(r'\]\(([^)\s]+)\)')


def units(text):
    return len(text.encode('utf-16-le')) // 2


def measure(text):
    body = text.strip()
    lines = body.split('\n') if body else []
    kept = total = 0
    for n, line in enumerate(lines[:CAP_LINES]):
        cost = units(line) + (1 if n else 0)
        if total + cost > CAP_UNITS:
            break
        total += cost
        kept += 1
    return {'lines': len(lines), 'units': units(body), 'lost_lines': len(lines) - kept,
            'headroom': CAP_UNITS - units(body)}


def frontmatter(path):
    text = open(path, encoding='utf-8', errors='replace').read()
    if not text.startswith('---\n'):
        return {}
    end = text.find('\n---', 4)
    block = text[4:end] if end > 0 else ''
    out = {}
    for key in ('name', 'description'):
        m = re.search(r'^%s:\s*(.+)$' % key, block, re.M)
        if m:
            out[key] = m.group(1).strip().strip('"\'')
    return out


def read_index(mem):
    path = os.path.join(mem, 'MEMORY.md')
    return (open(path, encoding='utf-8').read(), True) if os.path.exists(path) else ('', False)


def check(mem, since):
    text, exists = read_index(mem)
    lines = text.split('\n')
    linked = {target for line in lines for target in LINK.findall(line)}
    files = sorted(f for f in os.listdir(mem) if f.endswith('.md') and f != 'MEMORY.md')
    missing = [f for f in files if f not in linked]
    recent = [f for f in missing if since is not None and os.path.getmtime(os.path.join(mem, f)) >= since]
    dead = []
    for n, line in enumerate(lines, 1):
        targets = LINK.findall(line)
        gone = [t for t in targets if not os.path.exists(os.path.join(mem, t))]
        if gone:
            dead.append({'line': n, 'targets': gone, 'removable': len(gone) == len(targets)})
    return {'index_exists': exists, 'index': measure(text), 'unindexed_recent': recent,
            'unindexed_older': [f for f in missing if f not in recent], 'dead_links': dead}


def fix(mem, report):
    text, _ = read_index(mem)
    lines = text.split('\n')
    drop = {d['line'] for d in report['dead_links'] if d['removable']}
    removed = [lines[n - 1] for n in sorted(drop)]
    kept = [line for n, line in enumerate(lines, 1) if n not in drop]
    added = []
    for f in report['unindexed_recent']:
        fm = frontmatter(os.path.join(mem, f))
        added.append('- [%s](%s) — %s' % (fm.get('name', f[:-3]), f, fm.get('description', '(no description)')))
    body = '\n'.join(kept).rstrip('\n')
    body = (body + '\n' if body else '') + ''.join(line + '\n' for line in added)
    with open(os.path.join(mem, 'MEMORY.md'), 'w', encoding='utf-8') as fh:
        fh.write(body)
    return {'added': added, 'removed': removed}


def since_from(args):
    if args.since:
        return datetime.datetime.fromisoformat(args.since.replace('Z', '+00:00')).timestamp()
    session = args.session or os.environ.get('CLAUDE_CODE_SESSION_ID')
    if not session:
        return None
    try:
        first = transcript.first_timestamp(transcript.find_transcript(session, args.projects))
    except LookupError:
        return None
    return transcript.epoch(first) if first else None


def has_debt(report):
    return bool(report['index']['lost_lines'] or report['unindexed_recent'] or report['unindexed_older']
                or report['dead_links'])


def main(argv=None):
    p = argparse.ArgumentParser(description='Check a project memory dir before a handoff.')
    p.add_argument('memory_dir')
    p.add_argument('--since')
    p.add_argument('--session')
    p.add_argument('--fix', action='store_true')
    p.add_argument('--json', action='store_true')
    p.add_argument('--projects', default=transcript.PROJECTS, help=argparse.SUPPRESS)
    args = p.parse_args(argv)
    if not os.path.isdir(args.memory_dir):
        print('memory-check: no such directory: %s' % args.memory_dir, file=sys.stderr)
        return 2
    since = since_from(args)
    report = check(args.memory_dir, since)
    if args.fix:
        fixed = fix(args.memory_dir, report)
        report = check(args.memory_dir, since)
        report['fixed'] = fixed
    report['debt'] = has_debt(report)
    if args.json:
        print(json.dumps(report, indent=1, ensure_ascii=False))
    else:
        i = report['index']
        print('MEMORY.md: %d lines, %d UTF-16 units, headroom %d, %d line(s) lost at load'
              % (i['lines'], i['units'], i['headroom'], i['lost_lines']))
        for key in ('unindexed_recent', 'unindexed_older'):
            for f in report[key]:
                print('%s: %s' % (key, f))
        for d in report['dead_links']:
            print('dead link, line %d: %s%s' % (d['line'], ', '.join(d['targets']),
                                                '' if d['removable'] else ' (the line has live links too)'))
        for line in report.get('fixed', {}).get('added', []):
            print('added: %s' % line)
        for line in report.get('fixed', {}).get('removed', []):
            print('removed: %s' % line)
        print('debt' if report['debt'] else 'clean (checked)')
    return 1 if report['debt'] else 0


if __name__ == '__main__':
    sys.exit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd ~/.local/share/chezmoi && python3 -m unittest discover -s tests -p 'test_handoff_memory_check.py' -v`
Expected: 7 tests, all `ok`.

- [ ] **Step 5: Prove the UTF-16 test can fail**

Temporarily change `units()` to `return len(text)`, re-run, and confirm `test_unit_cap_counts_utf16_and_cuts_whole_lines` fails. Restore and re-run: all `ok`.

- [ ] **Step 6: Validate against the real Alpha memory (local only, read-only copy)**

```bash
T=$(mktemp -d); cp -R ~/.claude/projects/-Users-you-code-acme-consult-agent-alpha-beta/memory "$T/m"
python3 -I ~/.local/share/chezmoi/private_dot_claude/skills/session-handoff/scripts/memory-check.py "$T/m" --since 2026-10-12T00:00:00Z
wc -l < "$T/m/MEMORY.md"; wc -m < "$T/m/MEMORY.md"; rm -rf "$T"
```

Expected: the first line's line count and units agree with `wc -l` / `wc -m` (they differ only for non-BMP characters); record the output in the task report. Never run `--fix` on the live directory in this task.

- [ ] **Step 7: Commit**

```bash
cd ~/.local/share/chezmoi
git add tests/test_handoff_memory_check.py private_dot_claude/skills/session-handoff/scripts/memory-check.py
git commit -m "session-handoff: check the memory index the way the loader reads it"
```

---

### Task 4: `relay-check.py` — `name`, `identity`, `checklist`

**Files:**
- Create: `private_dot_claude/skills/session-handoff/scripts/relay-check.py`
- Modify: `docs/superpowers/specs/2026-10-12-session-relay-design.md` (checklist contract)
- Test: `tests/test_handoff_relay_check.py`

**Interfaces:**
- Consumes: `transcript.find_transcript`, `open_tasks`, `open_crons`, `prompts`, `last_model`, `permission_mode`, `PROJECTS` (Task 2); `handoff_fixtures` (Task 2).
- Produces (CLI):
  - `relay-check.py name [--repo DIR] [--suffix SUFFIX] [--slug SLUG]` → prints `lead-<slug>` or `lead-<slug>-<suffix>`.
  - `relay-check.py identity` → prints JSON `{session_id, pane_id, model, effort, permission_mode}` for the current session.
  - `relay-check.py checklist --note PATH [--extra-root DIR ...] [--transcript PATH ...]` → writes `<enc>/relay/<relay-id>/checklist.json`, prints the relay dir, exit 0; exit 3 with one stderr line per blocker (agent or workflow task open; git mid-operation) and no dir created.
  - `checklist.json` keys: `relay_id`, `created_at`, `repo`, `predecessor` {`session_id`, `transcript`, `pane_id`, `herdr_name`, `herdr_session`, `model`, `effort`, `permission_mode`, `pid`}, `git` {`head`, `branch`, `dirty`}, `note` {`path`, `sha256`}, `background_tasks`, `crons`, `workers` [{`pane_id`, `name`, `kind`, `status`, `session_id`, `cwd`}], `recent_prompts`.
  - Module functions used by Task 5: `sha256(path) -> str`, `settings_mode(repo) -> str`, `run(cmd) -> (int, str)`.
  - Hidden `--projects DIR` on every subcommand.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_handoff_relay_check.py`:

```python
import datetime
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

from handoff_fixtures import (SCRIPTS, agent_json, herdr_stub, prompt, tool_result, tool_use,
                              write_transcript)

RC = SCRIPTS / 'relay-check.py'
SID = '33333333-3333-4333-8333-333333333333'
HERDR_NAME = re.compile(r'^[a-z][a-z0-9_-]{0,31}$')


def load_module():
    spec = importlib.util.spec_from_file_location('relay_check', RC)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def rc(*args, env=None, cwd=None):
    return subprocess.run(['python3', '-I', str(RC), *args], capture_output=True, text=True, env=env, cwd=cwd)


def git_repo(root):
    repo = Path(root) / 'repo'
    repo.mkdir()
    subprocess.run(['git', 'init', '-q', str(repo)], check=True)
    (repo / 'README.md').write_text('x\n')
    subprocess.run(['git', '-C', str(repo), 'add', '.'], check=True)
    subprocess.run(['git', '-C', str(repo), '-c', 'user.name=T', '-c', 'user.email=t@example.invalid',
                    'commit', '-qm', 'init'], check=True)
    return Path(os.path.realpath(repo))


class NameTests(unittest.TestCase):
    def test_lead_names_are_valid_herdr_names(self):
        for repo, canonical in [('/x/acme-consult-agent-alpha-beta', 'lead-acme-consult-agent-alp'),
                                ('/x/9 Lives.Repo', 'lead-9-lives-repo'),
                                ('/x/UPPER_case', 'lead-upper-case'),
                                ('/x/...', 'lead-project')]:
            got = rc('name', '--repo', repo).stdout.strip()
            nxt = rc('name', '--repo', repo, '--suffix', 'next').stdout.strip()
            self.assertEqual(got, canonical)
            self.assertEqual(nxt, canonical + '-next')
            for name in (got, nxt):
                self.assertRegex(name, HERDR_NAME)
        self.assertEqual(rc('name', '--repo', '/x/anything', '--slug', 'sample').stdout.strip(), 'lead-sample')


class ChecklistTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.repo = git_repo(self.root)
        self.projects = self.root / 'projects'
        self.note = self.root / 'note.md'
        self.note.write_text('# note\n')

    def tearDown(self):
        self.tmp.cleanup()

    def env(self, recs, panes=None):
        self.transcript = write_transcript(self.projects, SID, recs)
        panes = panes if panes is not None else [
            {'pane_id': 'wT:p1', 'tab_id': 'wT:t1', 'cwd': str(self.repo), 'agent': 'claude', 'agent_status': 'working'},
            {'pane_id': 'wT:p2', 'tab_id': 'wT:t1', 'cwd': str(self.repo / 'sub'), 'agent': 'codex',
             'agent_status': 'working', 'agent_session': {'value': 'W2'}},
            {'pane_id': 'wT:p3', 'tab_id': 'wT:t9', 'cwd': '/elsewhere', 'agent': 'claude', 'agent_status': 'idle'}]
        env, self.log = herdr_stub(self.tmp.name, {
            'agent get': [{'out': agent_json('working', session='S1', pane='wT:p1', name='lead-repo')}],
            'agent list': [{'out': json.dumps({'result': {'agents': [{'pane_id': 'wT:p2', 'name': 'worker-a'}]}})}],
            'pane list': [{'out': json.dumps({'result': {'panes': panes}})}]})
        env.update(CLAUDE_CODE_SESSION_ID=SID, CLAUDE_EFFORT='xhigh', CLAUDE_PID='4242')
        return env

    def transcript_recs(self):
        return [{'type': 'permission-mode', 'permissionMode': 'bypassPermissions'},
                prompt('drive iteration 1', 1),
                tool_use('t1', 'Bash', {'command': 'until [ -f r ]; do sleep 5; done', 'description': 'wait r',
                                        'run_in_background': True}, 2),
                tool_result('t1', 'Command running in background with ID: bwait0001. Output is being written', 2),
                tool_use('c1', 'CronCreate', {'cron': '7 * * * *', 'prompt': 'status'}, 3),
                tool_result('c1', 'Scheduled recurring task cr000001 (7 * * * *).', 3)]

    def test_checklist_records_identity_tasks_crons_workers_and_prompts(self):
        env = self.env(self.transcript_recs())
        r = rc('checklist', '--note', str(self.note), '--projects', str(self.projects), env=env, cwd=self.repo)
        self.assertEqual(r.returncode, 0, r.stderr)
        rdir = Path(r.stdout.strip())
        self.assertEqual(rdir.parent, self.projects / '-tmp-repo' / 'relay')
        c = json.loads((rdir / 'checklist.json').read_text())
        self.assertEqual(c['relay_id'], rdir.name)
        self.assertEqual(c['repo'], str(self.repo))
        self.assertEqual(c['predecessor'], {
            'session_id': SID, 'transcript': str(self.transcript), 'pane_id': 'wT:p1', 'herdr_name': 'lead-repo',
            'herdr_session': 'S1', 'model': 'claude-opus-5-5', 'effort': 'xhigh',
            'permission_mode': 'bypassPermissions', 'pid': 4242})
        git = lambda *args: subprocess.run(['git', '-C', str(self.repo), *args],
                                           capture_output=True, text=True).stdout.strip()
        self.assertEqual(c['git'], {'head': git('rev-parse', '--short', 'HEAD'),
                                    'branch': git('rev-parse', '--abbrev-ref', 'HEAD'), 'dirty': []})
        self.assertEqual([t['id'] for t in c['background_tasks']], ['bwait0001'])
        self.assertEqual([x['id'] for x in c['crons']], ['cr000001'])
        self.assertEqual(c['workers'], [{'pane_id': 'wT:p2', 'name': 'worker-a', 'kind': 'codex',
                                         'status': 'working', 'session_id': 'W2', 'cwd': str(self.repo / 'sub')}])
        self.assertEqual([p['text'] for p in c['recent_prompts']], ['drive iteration 1'])
        self.assertEqual(c['note']['path'], str(self.note))
        self.assertEqual(len(c['note']['sha256']), 64)

    def test_checklist_refuses_while_a_workflow_runs(self):
        recs = self.transcript_recs() + [
            tool_use('w1', 'Workflow', {'script': 'x'}, 4),
            tool_result('w1', 'Workflow launched in background. Task ID: wrun00001 Summary: x', 4)]
        r = rc('checklist', '--note', str(self.note), '--projects', str(self.projects), env=self.env(recs),
               cwd=self.repo)
        self.assertEqual(r.returncode, 3)
        self.assertIn('workflow wrun00001', r.stderr)
        self.assertFalse((self.projects / '-tmp-repo' / 'relay').exists())

    def test_checklist_refuses_mid_merge(self):
        (self.repo / '.git' / 'MERGE_HEAD').write_text('0' * 40 + '\n')
        r = rc('checklist', '--note', str(self.note), '--projects', str(self.projects),
               env=self.env(self.transcript_recs()), cwd=self.repo)
        self.assertEqual(r.returncode, 3)
        self.assertIn('MERGE_HEAD', r.stderr)

    def test_relay_dir_collision_gets_a_suffix(self):
        module = load_module()
        now = datetime.datetime(2026, 10, 12, 20, 24, 23, tzinfo=datetime.timezone.utc)
        first = module.new_relay_dir(str(self.root / 'proj'), now)
        second = module.new_relay_dir(str(self.root / 'proj'), now)
        self.assertEqual(os.path.basename(first), '20261012T202423Z')
        self.assertEqual(os.path.basename(second), '20261012T202423Z-2')

    def test_identity_reads_the_current_session(self):
        env = self.env(self.transcript_recs())
        r = rc('identity', '--projects', str(self.projects), env=env, cwd=self.repo)
        self.assertEqual(json.loads(r.stdout), {'session_id': SID, 'pane_id': 'wT:p1', 'model': 'claude-opus-5-5',
                                                'effort': 'xhigh', 'permission_mode': 'bypassPermissions'})


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd ~/.local/share/chezmoi && python3 -m unittest discover -s tests -p 'test_handoff_relay_check.py' -v`
Expected: failures (`relay-check.py` does not exist).

- [ ] **Step 3: Write `relay-check.py` (name, identity, checklist)**

```python
#!/usr/bin/env python3
"""Relay checklist, receipt comparison, quiet check and lead names.

  name      [--repo DIR] [--suffix S] [--slug SLUG]   print lead-<slug>[-<S>]
  identity                                          this session's identity, as JSON
  checklist --note PATH [--extra-root DIR ...] [--transcript PATH ...]
                                                    write <enc>/relay/<id>/checklist.json; print the dir
  compare   <relay-dir>                             receipt.json vs checklist.json: PASS or one FAIL per line
  quiet     <relay-dir>                             exit 1 if a prompt reached the predecessor after handover.md

Run as python3 -I. checklist and identity read $CLAUDE_CODE_SESSION_ID, $CLAUDE_EFFORT,
$CLAUDE_PID and $HERDR_PANE_ID of the session that runs them.
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import transcript  # noqa: E402

NAME_ROOM = 32 - len('lead-') - len('-next')   # herdr names are at most 32 characters
GIT_BUSY = ('MERGE_HEAD', 'CHERRY_PICK_HEAD', 'REVERT_HEAD', 'rebase-merge', 'rebase-apply')


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, r.stdout.strip()


def slug(repo, override=None):
    text = override or os.path.basename(os.path.abspath(repo).rstrip('/'))
    return re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-') or 'project'


def lead_name(repo, suffix=None, override=None):
    base = 'lead-' + slug(repo, override)[:NAME_ROOM].rstrip('-')
    return base + ('-' + suffix if suffix else '')


def sha256(path):
    with open(path, 'rb') as fh:
        return hashlib.file_digest(fh, 'sha256').hexdigest()


def settings_mode(repo):
    for path in (os.path.join(repo, '.claude', 'settings.local.json'), os.path.join(repo, '.claude', 'settings.json'),
                 os.path.expanduser('~/.claude/settings.json')):
        try:
            mode = json.load(open(path)).get('permissions', {}).get('defaultMode')
        except (OSError, ValueError, AttributeError):
            continue
        if mode:
            return mode
    return 'default'


def herdr_json(*args):
    code, out = run(['herdr', *args])
    if code != 0:
        return {}
    try:
        return json.loads(out)
    except ValueError:
        return {}


def repo_root():
    code, top = run(['git', 'rev-parse', '--show-toplevel'])
    return top if code == 0 and top else os.getcwd()


def git_state(repo):
    _, head = run(['git', '-C', repo, 'rev-parse', '--short', 'HEAD'])
    _, branch = run(['git', '-C', repo, 'rev-parse', '--abbrev-ref', 'HEAD'])
    _, porcelain = run(['git', '-C', repo, 'status', '--porcelain'])
    return {'head': head, 'branch': branch, 'dirty': [line[3:] for line in porcelain.splitlines() if line]}


def blockers(repo, tasks):
    out = ['%s %s is running inside this session (%s)' % (t['kind'], t['id'], t['description'] or t['command'][:60])
           for t in tasks if t['kind'] in ('agent', 'workflow')]
    code, gitdir = run(['git', '-C', repo, 'rev-parse', '--absolute-git-dir'])
    if code == 0:
        out += ['git is mid-operation (%s present)' % name for name in GIT_BUSY
                if os.path.exists(os.path.join(gitdir, name))]
    return out


def workers(repo, extra_roots, self_pane):
    _, listing = run(['git', '-C', repo, 'worktree', 'list', '--porcelain'])
    roots = [line[len('worktree '):] for line in listing.splitlines() if line.startswith('worktree ')] or [repo]
    roots = [os.path.realpath(r).rstrip('/') for r in roots + list(extra_roots)]
    names = {a.get('pane_id'): a.get('name') for a in herdr_json('agent', 'list').get('result', {}).get('agents', [])}
    out = []
    for p in herdr_json('pane', 'list').get('result', {}).get('panes', []):
        cwd = os.path.realpath(p.get('cwd') or '/').rstrip('/')
        if p.get('pane_id') == self_pane or not any(cwd == r or cwd.startswith(r + '/') for r in roots):
            continue
        out.append({'pane_id': p['pane_id'], 'name': names.get(p['pane_id']), 'kind': p.get('agent', 'shell'),
                    'status': p.get('agent_status'), 'session_id': (p.get('agent_session') or {}).get('value'),
                    'cwd': p.get('cwd')})
    return out


def new_relay_dir(project_dir, now):
    base = os.path.join(project_dir, 'relay', now.strftime('%Y%m%dT%H%M%SZ'))
    path, n = base, 1
    while True:
        try:
            os.makedirs(path)
            return path
        except FileExistsError:
            n += 1
            path = '%s-%d' % (base, n)


def own_transcript(a):
    session = os.environ.get('CLAUDE_CODE_SESSION_ID')
    if not session:
        sys.exit('relay-check: CLAUDE_CODE_SESSION_ID is not set; run this inside the Claude session')
    return session, transcript.find_transcript(session, a.projects)


def cmd_name(a):
    print(lead_name(a.repo, a.suffix, a.slug))
    return 0


def cmd_identity(a):
    session, tpath = own_transcript(a)
    print(json.dumps({'session_id': session, 'pane_id': os.environ.get('HERDR_PANE_ID'),
                      'model': transcript.last_model(tpath), 'effort': os.environ.get('CLAUDE_EFFORT'),
                      'permission_mode': transcript.permission_mode(tpath) or settings_mode(repo_root())}))
    return 0


def cmd_checklist(a):
    session, tpath = own_transcript(a)
    repo = os.path.realpath(repo_root())
    paths = a.transcript + [tpath]
    tasks = transcript.open_tasks(paths)
    blocked = blockers(repo, tasks)
    if blocked:
        for line in blocked:
            print('relay-check: not yet: %s' % line, file=sys.stderr)
        return 3
    self_pane = os.environ.get('HERDR_PANE_ID')
    me = herdr_json('agent', 'get', self_pane).get('result', {}).get('agent', {}) if self_pane else {}
    now = datetime.datetime.now(datetime.timezone.utc)
    rdir = new_relay_dir(os.path.dirname(tpath), now)
    pid = os.environ.get('CLAUDE_PID', '')
    data = {
        'relay_id': os.path.basename(rdir),
        'created_at': now.isoformat().replace('+00:00', 'Z'),
        'repo': repo,
        'predecessor': {
            'session_id': session, 'transcript': tpath, 'pane_id': self_pane, 'herdr_name': me.get('name'),
            'herdr_session': (me.get('agent_session') or {}).get('value'),
            'model': transcript.last_model(tpath), 'effort': os.environ.get('CLAUDE_EFFORT'),
            'permission_mode': transcript.permission_mode(tpath) or settings_mode(repo),
            'pid': int(pid) if pid.isdigit() else None},
        'git': git_state(repo),
        'note': {'path': os.path.abspath(a.note), 'sha256': sha256(a.note)},
        'background_tasks': tasks,
        'crons': transcript.open_crons(paths),
        'workers': workers(repo, a.extra_root, self_pane),
        'recent_prompts': transcript.prompts(tpath)[-3:],
    }
    with open(os.path.join(rdir, 'checklist.json'), 'w') as fh:
        json.dump(data, fh, indent=1)
    print(rdir)
    return 0


def main(argv=None):
    p = argparse.ArgumentParser(description='Relay checklist, receipt comparison, quiet check and lead names.')
    sub = p.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('name')
    s.add_argument('--repo', default='.')
    s.add_argument('--suffix')
    s.add_argument('--slug')
    sub.add_parser('identity')
    s = sub.add_parser('checklist')
    s.add_argument('--note', required=True)
    s.add_argument('--extra-root', action='append', default=[])
    s.add_argument('--transcript', action='append', default=[])
    for parser in sub.choices.values():
        parser.add_argument('--projects', default=transcript.PROJECTS, help=argparse.SUPPRESS)
    a = p.parse_args(argv)
    return {'name': cmd_name, 'identity': cmd_identity, 'checklist': cmd_checklist}[a.cmd](a)


if __name__ == '__main__':
    sys.exit(main())
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd ~/.local/share/chezmoi && python3 -m unittest discover -s tests -p 'test_handoff_relay_check.py' -v`
Expected: 6 tests, all `ok`.

- [ ] **Step 5: Bring the spec in line with what was built**

In `docs/superpowers/specs/2026-10-12-session-relay-design.md`, section "Script contracts", in the `relay-check.py checklist` bullet replace

```markdown
(from `herd-snapshot.sh`: name, pane, session, status); `crons`; `owner_prompts` (the last 3 prompts the
  owner typed, verbatim, with times).
```

with

```markdown
(herdr panes whose cwd is the repo, a worktree of it, or an `--extra-root`, minus this pane: name, pane,
  kind, status, session); `crons`; `recent_prompts` (the last 3 prompts typed into the session, by the owner or
  through herdr, verbatim, with times: the transcript cannot tell the two apart). It refuses (exit 3, no dir)
  while an agent or workflow task is open in the session or git is mid-operation. A `relay-check.py identity`
  subcommand prints the running session's identity for the successor's receipt.
```

- [ ] **Step 6: Commit**

```bash
cd ~/.local/share/chezmoi
git add tests/test_handoff_relay_check.py private_dot_claude/skills/session-handoff/scripts/relay-check.py \
  docs/superpowers/specs/2026-10-12-session-relay-design.md
git commit -m "session-handoff: write the relay hand-over checklist from instruments"
```

---

### Task 5: `relay-check.py` — `compare` and `quiet`

**Files:**
- Modify: `private_dot_claude/skills/session-handoff/scripts/relay-check.py`
- Modify: `docs/superpowers/specs/2026-10-12-session-relay-design.md` (compare contract)
- Test: `tests/test_handoff_relay_check.py` (append)

**Interfaces:**
- Consumes: `sha256`, `run` (Task 4); `transcript.prompts`, `transcript.epoch` (Task 2).
- Produces (CLI): `relay-check.py compare <relay-dir>` → prints `PASS` (exit 0) or one `FAIL <reason>` line per failure (exit 1). `relay-check.py quiet <relay-dir>` → exit 0 when no prompt reached the predecessor after `handover.md`'s mtime, 1 (listing them) when one did, 2 when `handover.md` is missing.
- Receipt contract (written by the successor, see `references/relay.md`): `relay_id`, `successor` {`model`, `effort`, `permission_mode`, ...}, `note` {`path`, `sha256`}, `tier`, `drift` [{`item`, `explanation`}], `tasks` [{`id`, `action`, `marker`, `reason`}], `workers` [{`pane_id`, `status_seen`, `waiter_marker`, `reason`}], `crons` [{`id`, `action`, `reason`}], `disagreements`, `questions`, `gaps`.

- [ ] **Step 1: Append the failing tests**

Append to `tests/test_handoff_relay_check.py` (before the `if __name__` block):

```python
class CompareTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name) / 'relay' / 'R1'
        self.dir.mkdir(parents=True)
        self.note = Path(self.tmp.name) / 'note.md'
        self.note.write_text('# note\n')
        self.marker = 'relay-test%d-w' % os.getpid()
        self.procs = [subprocess.Popen(['bash', '-c', ': %s%d; sleep 60' % (self.marker, k)]) for k in (1, 2)]
        identity = {'model': 'claude-opus-5-5', 'effort': 'xhigh', 'permission_mode': 'bypassPermissions'}
        self.checklist = {
            'relay_id': 'R1', 'predecessor': dict(identity, session_id='P', transcript='/dev/null'),
            'note': {'path': str(self.note), 'sha256': load_module().sha256(str(self.note))},
            'background_tasks': [{'id': 'b4tcyp53v', 'kind': 'shell', 'description': 'Watch free disk', 'command': 'df'}],
            'crons': [{'id': 'cr1', 'cron': '7 * * * *', 'prompt': 'status', 'recurring': True}],
            'workers': [{'pane_id': 'wT:p2', 'name': 'worker-a', 'kind': 'codex', 'status': 'working'}]}
        self.receipt = {
            'relay_id': 'R1', 'successor': dict(identity, session_id='N'),
            'note': {'path': str(self.note), 'sha256': self.checklist['note']['sha256']},
            'tier': 'clean', 'drift': [],
            'tasks': [{'id': 'b4tcyp53v', 'action': 'rearmed', 'marker': self.marker + '1'}],
            'workers': [{'pane_id': 'wT:p2', 'status_seen': 'working', 'waiter_marker': self.marker + '2'}],
            'crons': [{'id': 'cr1', 'action': 'rearmed'}],
            'disagreements': [], 'questions': [], 'gaps': []}

    def tearDown(self):
        for proc in self.procs:
            proc.kill()
            proc.wait()
        self.tmp.cleanup()

    def compare(self):
        (self.dir / 'checklist.json').write_text(json.dumps(self.checklist))
        (self.dir / 'receipt.json').write_text(json.dumps(self.receipt))
        return rc('compare', str(self.dir))

    def test_complete_receipt_passes(self):
        r = self.compare()
        self.assertEqual((r.returncode, r.stdout.strip()), (0, 'PASS'), r.stdout)

    def test_dropped_disk_watcher_fails(self):
        self.receipt['tasks'] = []
        r = self.compare()
        self.assertEqual(r.returncode, 1)
        self.assertIn('FAIL task b4tcyp53v (Watch free disk) is not in the receipt', r.stdout)

    def test_identity_mismatch_fails(self):
        self.receipt['successor']['effort'] = 'high'
        self.assertIn("identity: successor effort 'high', predecessor 'xhigh'", self.compare().stdout)

    def test_note_changed_after_the_successor_read_it_fails(self):
        self.note.write_text('# note\n## Relay Q&A\nanswer\n')
        self.assertIn('re-read it', self.compare().stdout)

    def test_dead_marker_fails(self):
        self.receipt['tasks'][0]['marker'] = 'relay-nobody-w9'
        self.assertIn("no live process carries marker 'relay-nobody-w9'", self.compare().stdout)

    def test_drop_needs_a_reason(self):
        self.receipt['tasks'] = [{'id': 'b4tcyp53v', 'action': 'drop', 'reason': ''}]
        self.assertIn('dropped without a reason', self.compare().stdout)
        self.receipt['tasks'] = [{'id': 'b4tcyp53v', 'action': 'drop', 'reason': 'disk is 60 GiB free'}]
        self.assertEqual(self.compare().returncode, 0)

    def test_missing_worker_cron_question_and_unexplained_drift_fail(self):
        self.receipt.update(workers=[], crons=[], questions=['what is the walkthrough headline?'],
                            tier='drift', drift=[{'item': 'HEAD moved', 'explanation': ''}])
        out = self.compare().stdout
        for text in ('worker wT:p2 (worker-a) is not in the receipt', 'cron cr1', 'open question: what is',
                     'unexplained drift: HEAD moved'):
            self.assertIn(text, out)

    def test_worker_status_change_does_not_fail_when_its_waiter_is_live(self):
        self.receipt['workers'][0]['status_seen'] = 'done'
        self.assertEqual(self.compare().returncode, 0)

    def test_unreadable_receipt_fails(self):
        (self.dir / 'checklist.json').write_text(json.dumps(self.checklist))
        r = rc('compare', str(self.dir))
        self.assertEqual(r.returncode, 1)
        self.assertIn('FAIL receipt.json unreadable', r.stdout)


class QuietTests(unittest.TestCase):
    def run_quiet(self, prompt_seconds, handover_second):
        from handoff_fixtures import ts
        with tempfile.TemporaryDirectory() as tmp:
            path = write_transcript(tmp, SID, [prompt('p%d' % s, s) for s in prompt_seconds])
            rdir = Path(tmp) / 'relay' / 'R1'
            rdir.mkdir(parents=True)
            (rdir / 'checklist.json').write_text(json.dumps({'predecessor': {'transcript': str(path)}}))
            if handover_second is not None:
                (rdir / 'handover.md').write_text('# Hand-over R1\n')
                when = datetime.datetime.fromisoformat(ts(handover_second).replace('Z', '+00:00')).timestamp()
                os.utime(rdir / 'handover.md', (when, when))
            return rc('quiet', str(rdir))

    def test_no_prompt_after_the_handover_is_quiet(self):
        self.assertEqual(self.run_quiet([10], 30).returncode, 0)

    def test_a_prompt_after_the_handover_is_not_quiet(self):
        r = self.run_quiet([10, 40], 30)
        self.assertEqual(r.returncode, 1)
        self.assertIn('p40', r.stdout)

    def test_no_handover_yet_exits_2(self):
        self.assertEqual(self.run_quiet([10], None).returncode, 2)
```

- [ ] **Step 2: Run the tests to verify the new ones fail**

Run: `cd ~/.local/share/chezmoi && python3 -m unittest discover -s tests -p 'test_handoff_relay_check.py' -v`
Expected: the 12 new tests fail (`invalid choice: 'compare'` / `'quiet'`); the 6 from Task 4 still pass.

- [ ] **Step 3: Add `compare` and `quiet` to `relay-check.py`**

Add these functions above `main`:

```python
def live(marker):
    return bool(marker) and subprocess.run(['pgrep', '-f', marker], capture_output=True).returncode == 0


def _reason(entry):
    return bool((entry.get('reason') or '').strip())


def cmd_compare(a):
    chk = json.load(open(os.path.join(a.relay_dir, 'checklist.json')))
    try:
        rec = json.load(open(os.path.join(a.relay_dir, 'receipt.json')))
    except (OSError, ValueError) as e:
        print('FAIL receipt.json unreadable: %s' % e)
        return 1
    fails = []
    if rec.get('relay_id') != chk.get('relay_id'):
        fails.append('relay_id %r is not %r' % (rec.get('relay_id'), chk.get('relay_id')))
    for key in ('model', 'effort', 'permission_mode'):
        want, got = chk['predecessor'].get(key), (rec.get('successor') or {}).get(key)
        if want != got:
            fails.append('identity: successor %s %r, predecessor %r' % (key, got, want))
    note = rec.get('note') or {}
    if note.get('path') != chk['note']['path']:
        fails.append('note: the successor read %r, the checklist names %r' % (note.get('path'), chk['note']['path']))
    else:
        on_disk = sha256(chk['note']['path'])
        if note.get('sha256') != on_disk:
            fails.append('note: the successor read sha256 %s, the note on disk is %s (re-read it)'
                         % (note.get('sha256'), on_disk))
    tasks = {t.get('id'): t for t in rec.get('tasks') or []}
    for t in chk.get('background_tasks', []):
        got = tasks.get(t['id'])
        label = t.get('description') or t.get('command', '')[:60]
        if not got:
            fails.append('task %s (%s) is not in the receipt' % (t['id'], label))
        elif got.get('action') == 'drop':
            if not _reason(got):
                fails.append('task %s dropped without a reason' % t['id'])
        elif got.get('action') in ('rearmed', 'watching-exit-file'):
            if not live(got.get('marker')):
                fails.append('task %s: no live process carries marker %r' % (t['id'], got.get('marker')))
        else:
            fails.append('task %s: unknown action %r' % (t['id'], got.get('action')))
    seen = {w.get('pane_id'): w for w in rec.get('workers') or []}
    for w in chk.get('workers', []):
        got = seen.get(w['pane_id'])
        if not got:
            fails.append('worker %s (%s) is not in the receipt' % (w['pane_id'], w.get('name') or w.get('kind')))
        elif got.get('waiter_marker'):
            if not live(got['waiter_marker']):
                fails.append('worker %s: no live process carries marker %r' % (w['pane_id'], got['waiter_marker']))
        elif not _reason(got):
            fails.append('worker %s has neither a waiter nor a reason' % w['pane_id'])
    crons = {c.get('id'): c for c in rec.get('crons') or []}
    for c in chk.get('crons', []):
        got = crons.get(c['id'], {})
        if got.get('action') != 'rearmed' and not (got.get('action') == 'drop' and _reason(got)):
            fails.append('cron %s (%s) is neither re-armed nor dropped with a reason' % (c['id'], c.get('cron')))
    fails += ['open question: %s' % q for q in rec.get('questions') or []]
    fails += ['open disagreement: %s' % d for d in rec.get('disagreements') or []]
    if rec.get('tier') not in ('clean', 'drift'):
        fails.append('tier %r is neither clean nor drift' % rec.get('tier'))
    fails += ['unexplained drift: %s' % d.get('item') for d in rec.get('drift') or []
              if not (d.get('explanation') or '').strip()]
    for line in fails:
        print('FAIL ' + line)
    if not fails:
        print('PASS')
    return 1 if fails else 0


def cmd_quiet(a):
    chk = json.load(open(os.path.join(a.relay_dir, 'checklist.json')))
    handover = os.path.join(a.relay_dir, 'handover.md')
    if not os.path.exists(handover):
        print('relay-check: no handover.md in %s yet' % a.relay_dir, file=sys.stderr)
        return 2
    after = os.path.getmtime(handover)
    late = [p for p in transcript.prompts(chk['predecessor']['transcript'])
            if (transcript.epoch(p['timestamp']) or 0) > after]
    for p in late:
        print('prompt at %s: %s' % (p['timestamp'], p['text'][:120]))
    return 1 if late else 0
```

In `main`, after the `checklist` parser, add:

```python
    for name in ('compare', 'quiet'):
        sub.add_parser(name).add_argument('relay_dir')
```

and extend the dispatch dict:

```python
    return {'name': cmd_name, 'identity': cmd_identity, 'checklist': cmd_checklist,
            'compare': cmd_compare, 'quiet': cmd_quiet}[a.cmd](a)
```

(The `for parser in sub.choices.values()` loop that adds `--projects` must stay after these parsers are created.)

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd ~/.local/share/chezmoi && python3 -m unittest discover -s tests -p 'test_handoff_relay_check.py' -v`
Expected: 18 tests, all `ok`.

- [ ] **Step 5: Bring the spec in line with what was built**

In the spec's `relay-check.py compare` bullet, replace

```markdown
a worker missing or
  its status differing from live `herdr agent get`;
```

with

```markdown
a worker missing, or
  with neither a live waiter marker nor a reason (status equality is not checked: a worker can finish between
  the successor's look and the compare);
```

- [ ] **Step 6: Commit**

```bash
cd ~/.local/share/chezmoi
git add tests/test_handoff_relay_check.py private_dot_claude/skills/session-handoff/scripts/relay-check.py \
  docs/superpowers/specs/2026-10-12-session-relay-design.md
git commit -m "session-handoff: compare the successor's receipt with the checklist"
```

---

### Task 6: `relay-launch.sh`

**Files:**
- Create: `private_dot_claude/skills/session-handoff/scripts/relay-launch.sh`
- Test: `tests/test_handoff_relay_launch.py`

**Interfaces:**
- Consumes: `checklist.json` fields `predecessor.model`, `predecessor.effort`, `predecessor.permission_mode`, `repo` (Task 4); `relay-check.py name` (Task 4); Task 1's result on `--session-id`.
- Produces: `bash relay-launch.sh <relay-dir> [--slug SLUG]` → prints the new pane id and writes `launch.json` {`pane_id`, `name`, `session_id`, `requested_session_id`, `model`, `effort`, `permission_mode`, `at`}, exit 0; on two failed starts, a failed split, a banner mismatch or a failed `/pickup` send: closes the pane it created, writes `failed.json` {`stage`: `launch`, `reason`, `attempts`, `at`}, exit 1; exit 2 outside herdr or without `checklist.json`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_handoff_relay_launch.py`:

```python
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from handoff_fixtures import SCRIPTS, agent_json, herdr_calls, herdr_stub

LAUNCH = SCRIPTS / 'relay-launch.sh'
SPLIT = {'out': json.dumps({'result': {'pane': {'pane_id': 'wT:p9'}}})}
BANNER = {'out': ' Claude Code v2.1.296\n Opus 5.5 with xhigh effort · Claude Max\n ~/code/repo\n'}


class LaunchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name) / 'relay' / 'R1'
        self.dir.mkdir(parents=True)

    def tearDown(self):
        self.tmp.cleanup()

    def launch(self, responses, mode='bypassPermissions', with_env=True):
        (self.dir / 'checklist.json').write_text(json.dumps({
            'relay_id': 'R1', 'repo': '/x/repo',
            'predecessor': {'model': 'claude-opus-5-5', 'effort': 'xhigh', 'permission_mode': mode}}))
        env, self.log = herdr_stub(self.tmp.name, responses)
        if not with_env:
            env.pop('HERDR_ENV')
        return subprocess.run(['bash', str(LAUNCH), str(self.dir)], capture_output=True, text=True, env=env)

    def call(self, verb):
        return [c for c in herdr_calls(self.log) if c[:2] == verb]

    def test_starts_the_successor_with_matching_identity_and_sends_pickup(self):
        r = self.launch({'pane split': [SPLIT], 'pane read': [BANNER],
                         'agent get': [{'out': agent_json('idle', session='S2', pane='wT:p9')}]})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), 'wT:p9')
        start = self.call(['agent', 'start'])[0]
        self.assertEqual(start[2:7], ['lead-repo-next', '--kind', 'claude', '--pane', 'wT:p9'])
        tail = start[start.index('--', 7) + 1:]
        self.assertEqual(tail[:2], ['--model', 'claude-opus-5-5'])
        self.assertIn('--session-id', tail)
        self.assertEqual(tail[tail.index('--effort') + 1], 'xhigh')
        self.assertIn('--dangerously-skip-permissions', tail)
        self.assertEqual(self.call(['agent', 'prompt'])[0][2:], ['lead-repo-next', '/pickup relay=%s' % self.dir])
        launch = json.loads((self.dir / 'launch.json').read_text())
        self.assertEqual((launch['pane_id'], launch['name'], launch['session_id']), ('wT:p9', 'lead-repo-next', 'S2'))

    def test_default_permission_mode_adds_no_bypass_flag(self):
        r = self.launch({'pane split': [SPLIT], 'pane read': [BANNER]}, mode='default')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertNotIn('--dangerously-skip-permissions', self.call(['agent', 'start'])[0])

    def test_two_failed_starts_close_the_pane_and_record_failure(self):
        r = self.launch({'pane split': [SPLIT], 'agent start': [{'out': 'boom', 'code': 1}]})
        self.assertEqual(r.returncode, 1)
        self.assertEqual(len(self.call(['agent', 'start'])), 2)
        self.assertEqual(self.call(['pane', 'close']), [['pane', 'close', 'wT:p9']])
        failed = json.loads((self.dir / 'failed.json').read_text())
        self.assertEqual((failed['stage'], failed['reason'], failed['attempts']), ('launch', 'agent start failed twice', 2))
        self.assertFalse((self.dir / 'launch.json').exists())

    def test_banner_without_the_model_fails(self):
        r = self.launch({'pane split': [SPLIT], 'pane read': [{'out': ' Haiku 5.5 with xhigh effort\n'}]})
        self.assertEqual(r.returncode, 1)
        self.assertIn("banner does not show model 'Opus 5.5'", json.loads((self.dir / 'failed.json').read_text())['reason'])
        self.assertEqual(self.call(['pane', 'close']), [['pane', 'close', 'wT:p9']])
        self.assertEqual(self.call(['agent', 'prompt']), [])

    def test_outside_herdr_exits_2(self):
        self.assertEqual(self.launch({}, with_env=False).returncode, 2)


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd ~/.local/share/chezmoi && python3 -m unittest discover -s tests -p 'test_handoff_relay_launch.py' -v`
Expected: failures (`bash: .../relay-launch.sh: No such file or directory`, exit 127).

- [ ] **Step 3: Write `relay-launch.sh`**

```bash
#!/usr/bin/env bash
# Start a relay's successor: split this pane down, launch Claude with the
# predecessor's model, effort and permission mode, check the banner, and send
# /pickup relay=<dir>.
# Usage: bash relay-launch.sh <relay-dir> [--slug SLUG]
# Success: prints the new pane id and writes <relay-dir>/launch.json.
# Failure (split failed, two failed starts, a banner without the model or
# effort, /pickup not sent): closes the pane it created, writes
# <relay-dir>/failed.json and exits 1. Exit 2 outside herdr or without a checklist.
set -uo pipefail
dir=${1:?usage: relay-launch.sh <relay-dir> [--slug SLUG]}
shift
here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
[ "${HERDR_ENV:-}" = 1 ] || { echo "relay-launch: not inside herdr" >&2; exit 2; }
[ -f "$dir/checklist.json" ] || { echo "relay-launch: no checklist.json in $dir" >&2; exit 2; }

field() {
  python3 -I -c 'import json, sys
d = json.load(open(sys.argv[1]))
for key in sys.argv[2].split("."):
    d = d.get(key) if isinstance(d, dict) else None
print("" if d is None else d)' "$dir/checklist.json" "$1"
}

pane=""
attempt=0
fail() {
  echo "relay-launch: $1" >&2
  [ -n "$pane" ] && herdr pane close "$pane" >/dev/null 2>&1
  python3 -I -c 'import datetime, json, sys
json.dump({"stage": "launch", "reason": sys.argv[2], "attempts": int(sys.argv[3]),
           "at": datetime.datetime.now(datetime.timezone.utc).isoformat()}, open(sys.argv[1], "w"), indent=1)' \
    "$dir/failed.json" "$1" "$attempt"
  exit 1
}

model=$(field predecessor.model)
effort=$(field predecessor.effort)
mode=$(field predecessor.permission_mode)
repo=$(field repo)
[ -n "$model" ] || { echo "relay-launch: the checklist names no model" >&2; exit 2; }
name=$(python3 -I "$here/relay-check.py" name --repo "$repo" --suffix next "$@")
sid=$(python3 -I -c 'import uuid; print(uuid.uuid4())')
args=(--model "$model" --session-id "$sid")
[ -n "$effort" ] && args+=(--effort "$effort")
[ "$mode" = bypassPermissions ] && args+=(--dangerously-skip-permissions)

pane=$(herdr pane split "$HERDR_PANE_ID" --direction down --cwd "$repo" --no-focus 2>/dev/null \
  | python3 -I -c 'import json, sys; print(json.load(sys.stdin)["result"]["pane"]["pane_id"])' 2>/dev/null) || pane=""
[ -n "$pane" ] || fail "pane split failed"

started=""
while [ "$attempt" -lt 2 ]; do
  attempt=$((attempt + 1))
  if out=$(herdr agent start "$name" --kind claude --pane "$pane" --timeout 90000 -- "${args[@]}" 2>&1); then
    started=1
    break
  fi
  echo "relay-launch: start attempt $attempt failed: $out" >&2
done
[ -n "$started" ] || fail "agent start failed twice"

want=$(python3 -I -c 'import sys
parts = sys.argv[1].removeprefix("claude-").split("-")
print(parts[0].capitalize() + " " + ".".join(parts[1:]))' "$model")
banner=$(herdr pane read "$pane" --source visible 2>&1)
case "$banner" in *"$want"*) ;; *) fail "banner does not show model '$want'" ;; esac
if [ -n "$effort" ]; then
  case "$banner" in *"$effort"*) ;; *) fail "banner does not show effort '$effort'" ;; esac
fi

session=$(herdr agent get "$name" 2>/dev/null | python3 -I -c 'import json, sys
agent = (json.load(sys.stdin).get("result") or {}).get("agent") or {}
print((agent.get("agent_session") or {}).get("value", ""))' 2>/dev/null)
herdr agent prompt "$name" "/pickup relay=$dir" >/dev/null 2>&1 || fail "could not send /pickup"

python3 -I -c 'import datetime, json, sys
keys = ["pane_id", "name", "session_id", "requested_session_id", "model", "effort", "permission_mode"]
data = dict(zip(keys, sys.argv[2:]))
data["session_id"] = data["session_id"] or data["requested_session_id"]
data["at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
json.dump(data, open(sys.argv[1], "w"), indent=1)' \
  "$dir/launch.json" "$pane" "$name" "$session" "$sid" "$model" "$effort" "$mode"
echo "$pane"
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd ~/.local/share/chezmoi && python3 -m unittest discover -s tests -p 'test_handoff_relay_launch.py' -v`
Expected: 5 tests, all `ok`.

- [ ] **Step 5: Commit**

```bash
cd ~/.local/share/chezmoi
git add tests/test_handoff_relay_launch.py private_dot_claude/skills/session-handoff/scripts/relay-launch.sh
git commit -m "session-handoff: launch a relay successor with the predecessor's identity"
```

---

### Task 7: `relay-close.sh`

**Files:**
- Create: `private_dot_claude/skills/session-handoff/scripts/relay-close.sh`
- Test: `tests/test_handoff_relay_close.py`

**Interfaces:**
- Consumes: `checklist.json` fields `predecessor.pane_id`, `predecessor.herdr_session`, `predecessor.pid`, `predecessor.transcript`, `repo`, `relay_id` (Task 4); `relay-check.py quiet` and `name` (Tasks 4–5).
- Produces: `bash relay-close.sh <relay-dir> [--slug SLUG]` → exit 0 after closing the predecessor's pane, confirming it gone, renaming `$HERDR_PANE_ID` to `lead-<slug>`, and writing `<relay-dir>/closed.json` {`closed_at`, `predecessor` {`pane_id`, `session_id`}, `successor` {`pane_id`, `session_id`, `name`}} and `<relay-dir>/../lead.json` {`session_id`, `pane_id`, `name`, `since`, `relay_id`}; exit 1 on a refusal (message names the failed check; the pane is left open) or when the pane or pid outlives the close; exit 2 outside herdr. `RELAY_CLOSE_WAIT` (seconds, default 10) bounds the post-close polling.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_handoff_relay_close.py`:

```python
import datetime
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from handoff_fixtures import (NOT_FOUND, SCRIPTS, agent_json, herdr_calls, herdr_stub, prompt, ts,
                              write_transcript)

CLOSE = SCRIPTS / 'relay-close.sh'
PRED = '44444444-4444-4444-8444-444444444444'


def dead_pid():
    proc = subprocess.Popen(['true'])
    proc.wait()
    return proc.pid


class CloseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.dir = self.root / 'relay' / 'R1'
        self.dir.mkdir(parents=True)
        self.sleeper = None

    def tearDown(self):
        if self.sleeper:
            self.sleeper.kill()
            self.sleeper.wait()
        self.tmp.cleanup()

    def close(self, responses, prompts=(10,), handover_at=30, pid=None):
        path = write_transcript(self.root / 'projects', PRED, [prompt('p%d' % s, s) for s in prompts])
        (self.dir / 'checklist.json').write_text(json.dumps({
            'relay_id': 'R1', 'repo': '/x/repo',
            'predecessor': {'pane_id': 'wT:p0', 'herdr_session': 'S0', 'session_id': PRED,
                            'pid': pid if pid is not None else dead_pid(), 'transcript': str(path)}}))
        if handover_at is not None:
            (self.dir / 'handover.md').write_text('# Hand-over R1\n')
            when = datetime.datetime.fromisoformat(ts(handover_at).replace('Z', '+00:00')).timestamp()
            os.utime(self.dir / 'handover.md', (when, when))
        env, self.log = herdr_stub(self.tmp.name, responses)
        env.update(CLAUDE_CODE_SESSION_ID='N1', RELAY_CLOSE_WAIT='1')
        return subprocess.run(['bash', str(CLOSE), str(self.dir)], capture_output=True, text=True, env=env)

    def closes(self):
        return [c for c in herdr_calls(self.log) if c[:2] == ['pane', 'close']]

    def test_closes_renames_and_records(self):
        r = self.close({'agent get': [{'out': agent_json('idle', session='S0')}, NOT_FOUND]})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.closes(), [['pane', 'close', 'wT:p0']])
        self.assertIn(['agent', 'rename', 'wT:p1', 'lead-repo'], herdr_calls(self.log))
        closed = json.loads((self.dir / 'closed.json').read_text())
        self.assertEqual(closed['successor'], {'pane_id': 'wT:p1', 'session_id': 'N1', 'name': 'lead-repo'})
        lead = json.loads((self.dir.parent / 'lead.json').read_text())
        self.assertEqual((lead['session_id'], lead['name'], lead['relay_id']), ('N1', 'lead-repo', 'R1'))

    def test_refuses_while_the_predecessor_works(self):
        r = self.close({'agent get': [{'out': agent_json('working', session='S0')}]})
        self.assertEqual(r.returncode, 1)
        self.assertIn("is 'working', not idle or done", r.stderr)
        self.assertEqual(self.closes(), [])

    def test_refuses_when_the_pane_hosts_another_session(self):
        r = self.close({'agent get': [{'out': agent_json('idle', session='OTHER')}]})
        self.assertEqual(r.returncode, 1)
        self.assertIn("hosts session 'OTHER'", r.stderr)
        self.assertEqual(self.closes(), [])

    def test_refuses_after_a_prompt_reached_the_old_pane(self):
        r = self.close({'agent get': [{'out': agent_json('idle', session='S0')}]}, prompts=(10, 40))
        self.assertEqual(r.returncode, 1)
        self.assertIn('a prompt reached the predecessor after the hand-over', r.stderr)
        self.assertEqual(self.closes(), [])

    def test_refuses_without_a_handover(self):
        r = self.close({'agent get': [{'out': agent_json('idle', session='S0')}]}, handover_at=None)
        self.assertEqual(r.returncode, 1)
        self.assertIn('no handover.md', r.stderr)
        self.assertEqual(self.closes(), [])

    def test_reports_a_predecessor_pid_that_survives_the_close(self):
        self.sleeper = subprocess.Popen(['sleep', '60'])
        r = self.close({'agent get': [{'out': agent_json('idle', session='S0')}, NOT_FOUND]}, pid=self.sleeper.pid)
        self.assertEqual(r.returncode, 1)
        self.assertIn('is still alive', r.stderr)
        self.assertFalse((self.dir / 'closed.json').exists())


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `cd ~/.local/share/chezmoi && python3 -m unittest discover -s tests -p 'test_handoff_relay_close.py' -v`
Expected: failures (script missing, exit 127).

- [ ] **Step 3: Write `relay-close.sh`**

```bash
#!/usr/bin/env bash
# Close a relay's predecessor, by fact. The successor runs this after the hand-over.
# Usage: bash relay-close.sh <relay-dir> [--slug SLUG]
# Refuses (exit 1, pane left open) unless handover.md exists, the predecessor's
# pane reports idle or done, the pane still hosts the session it hosted when
# the checklist was written, and no prompt reached the predecessor after
# handover.md. Then closes the pane, confirms the pane and the predecessor's
# process are gone, renames this agent lead-<project>, and writes
# <relay-dir>/closed.json and <relay-dir>/../lead.json. Exit 2 outside herdr.
set -uo pipefail
dir=${1:?usage: relay-close.sh <relay-dir> [--slug SLUG]}
shift
here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
wait_s=${RELAY_CLOSE_WAIT:-10}
refuse() { echo "relay-close: refusing: $1 (pane left open)" >&2; exit 1; }
field() {
  python3 -I -c 'import json, sys
d = json.load(open(sys.argv[1]))
for key in sys.argv[2].split("."):
    d = d.get(key) if isinstance(d, dict) else None
print("" if d is None else d)' "$dir/checklist.json" "$1"
}

[ "${HERDR_ENV:-}" = 1 ] || { echo "relay-close: not inside herdr" >&2; exit 2; }
[ -f "$dir/checklist.json" ] || { echo "relay-close: no checklist.json in $dir" >&2; exit 2; }
[ -f "$dir/handover.md" ] || refuse "no handover.md in $dir"
pane=$(field predecessor.pane_id)
want_session=$(field predecessor.herdr_session)
old_session=$(field predecessor.session_id)
old_pid=$(field predecessor.pid)
repo=$(field repo)
relay_id=$(field relay_id)
[ -n "$pane" ] || refuse "the checklist names no predecessor pane"

state=$(herdr agent get "$pane" 2>&1 | python3 -I -c 'import json, sys
try:
    agent = (json.load(sys.stdin).get("result") or {}).get("agent") or {}
except ValueError:
    agent = {}
print(agent.get("agent_status") or "-", (agent.get("agent_session") or {}).get("value") or "")')
read -r status session <<<"$state"
case "$status" in idle|done) ;; *) refuse "predecessor pane $pane is '$status', not idle or done" ;; esac
[ "${session:-}" = "$want_session" ] || refuse "pane $pane hosts session '${session:-none}', not '${want_session:-none}'"
python3 -I "$here/relay-check.py" quiet "$dir" >&2 || refuse "a prompt reached the predecessor after the hand-over"

herdr pane close "$pane" >/dev/null 2>&1
gone=""
for _ in $(seq 1 "$wait_s"); do
  if herdr agent get "$pane" 2>&1 | grep -q agent_not_found; then gone=1; break; fi
  sleep 1
done
[ -n "$gone" ] || { echo "relay-close: pane $pane still answers after the close" >&2; exit 1; }
if [ -n "$old_pid" ]; then
  for _ in $(seq 1 "$wait_s"); do kill -0 "$old_pid" 2>/dev/null || break; sleep 1; done
  if kill -0 "$old_pid" 2>/dev/null; then echo "relay-close: predecessor pid $old_pid is still alive" >&2; exit 1; fi
fi

name=$(python3 -I "$here/relay-check.py" name --repo "$repo" "$@")
herdr agent rename "$HERDR_PANE_ID" "$name" >/dev/null 2>&1 \
  || echo "relay-close: could not rename this agent to $name; it keeps its -next name" >&2
python3 -I -c 'import datetime, json, os, sys
d, pane, old, new_pane, new_session, name, relay_id = sys.argv[1:8]
now = datetime.datetime.now(datetime.timezone.utc).isoformat()
json.dump({"closed_at": now, "predecessor": {"pane_id": pane, "session_id": old},
           "successor": {"pane_id": new_pane, "session_id": new_session, "name": name}},
          open(os.path.join(d, "closed.json"), "w"), indent=1)
json.dump({"session_id": new_session, "pane_id": new_pane, "name": name, "since": now, "relay_id": relay_id},
          open(os.path.join(os.path.dirname(os.path.abspath(d)), "lead.json"), "w"), indent=1)' \
  "$dir" "$pane" "$old_session" "$HERDR_PANE_ID" "${CLAUDE_CODE_SESSION_ID:-}" "$name" "$relay_id"
echo "relay-close: closed $pane; this agent is $name"
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `cd ~/.local/share/chezmoi && python3 -m unittest discover -s tests -p 'test_handoff_relay_close.py' -v`
Expected: 6 tests, all `ok`.

- [ ] **Step 5: Commit**

```bash
cd ~/.local/share/chezmoi
git add tests/test_handoff_relay_close.py private_dot_claude/skills/session-handoff/scripts/relay-close.sh
git commit -m "session-handoff: close a relay predecessor only when the facts allow it"
```

---

### Task 8: Skill text, `/relay` command, CLAUDE.md wording

**Files:**
- Modify: `private_dot_claude/skills/session-handoff/SKILL.md`
- Create: `private_dot_claude/skills/session-handoff/references/relay.md`
- Create: `private_dot_claude/skills/session-handoff/references/feedback.md`
- Create: `private_dot_claude/commands/relay.md`
- Modify: `private_dot_claude/CLAUDE.md` (see "Before Task 1")
- Test: `tests/test_handoff_docs.py`

**Interfaces:**
- Consumes: every script name and CLI from Tasks 2–7.
- Produces: the skill text the E2E run (Task 10) follows.

- [ ] **Step 1: Write the failing docs test**

Create `tests/test_handoff_docs.py`:

```python
import re
import unittest

from handoff_fixtures import SCRIPTS, SOURCE

SKILL = SOURCE / 'private_dot_claude/skills/session-handoff'


class HandoffDocsTests(unittest.TestCase):
    def test_every_script_the_docs_name_exists(self):
        text = ''.join((SKILL / name).read_text() for name in ('SKILL.md', 'references/relay.md', 'references/feedback.md'))
        named = set(re.findall(r'scripts/([\w.-]+\.(?:py|sh))', text))
        self.assertTrue(named >= {'bg-tasks.py', 'memory-check.py', 'relay-check.py', 'relay-launch.sh',
                                  'relay-close.sh'}, named)
        for name in named:
            self.assertTrue((SCRIPTS / name).exists(), name)

    def test_template_sections_and_the_compact_advice_is_gone(self):
        text = (SKILL / 'SKILL.md').read_text()
        for section in ('## Backlog', '## Memory', '## Relay Q&A', '## Pickup gaps', '## RELAY mode'):
            self.assertIn(section, text)
        self.assertNotIn('compact instead', text)

    def test_relay_command_routes_to_relay_mode(self):
        text = (SOURCE / 'private_dot_claude/commands/relay.md').read_text()
        self.assertIn('`session-handoff`', text)
        self.assertIn('RELAY mode', text)

    def test_claude_md_waits_on_a_fresh_report_and_routes_relay(self):
        text = (SOURCE / 'private_dot_claude/CLAUDE.md').read_text()
        self.assertNotIn('"report file exists AND', text)
        self.assertIn('written by this dispatch', text)
        self.assertIn('`/relay`', text)


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run it to verify it fails**

Run: `cd ~/.local/share/chezmoi && python3 -m unittest discover -s tests -p 'test_handoff_docs.py' -v`
Expected: 4 failures/errors (missing files and sections).

- [ ] **Step 3: Edit `SKILL.md`**

Apply these replacements in `private_dot_claude/skills/session-handoff/SKILL.md` (each "find" text is unique).

(a) In the frontmatter `description:`, find

```
"running out of context"), when resuming
```

replace with

```
"running out of context"), when handing the lead to a new session ("relay", "hand over to a new session", "/relay"), when resuming
```

(b) Find

```
then verifying it against reality. Two modes: **SAVE** (`/handoff`) and
**RESUME** (`/pickup`).
```

replace with

```
then verifying it against reality. Three modes: **SAVE** (`/handoff`),
**RESUME** (`/pickup`) and **RELAY** (`/relay`: SAVE, then a successor in a new
herdr pane RESUMEs, takes the lead and closes this session).
```

(c) Find the block from `1. **Finish the current micro-step first** — never abandon a working change` through `continuation, compact instead.` (SAVE steps 1–4 and the Discipline paragraph) and replace it with:

```
1. **Finish the current micro-step first** — never abandon a working change
   because the meter grew. Attached long work (a `run_in_background` test,
   build or paid run) must finish before this session closes: it dies with
   the session. Long work should have been started detached (global
   CLAUDE.md, "Long work outlives its session").
2. **Memory before the note.** Decide which durable facts (traps,
   preferences, recipes) are worth keeping and write them to memory files now.
   Do not ask first: this is the wrap-up, where an unanswered question is how a
   fact gets lost, and a wrong call costs one deletion. Then run
   `python3 -I ~/.claude/skills/session-handoff/scripts/memory-check.py <memory-dir> --fix`.
   It applies only two safe fixes (an index line for each memory written this
   session; removal of index lines whose every link is dead) and measures
   MEMORY.md as the loader does (200 lines, 25,000 UTF-16 units; the tail past
   the cap never loads). Exit 1 means debt remains: record it in the note's
   Memory section as the successor's first job. Never strand a durable fact in
   the note.
3. **Run the snapshots** — the note records **command output, not conversational
   memory**. Never write State / anchor / In flight from what you remember:
   - `git status --porcelain --branch` · `git log --oneline -5` ·
     `git log --oneline @{u}.. 2>/dev/null || git log --oneline HEAD --not --remotes 2>/dev/null`
     (skip silently only if there is no repo. With no upstream — or no remote at
     all — the second form IS the answer, not a failure: record it as
     `no-upstream, N commits exist nowhere else`. A branch with no upstream is the
     case where the count matters MOST, so it is never the case you skip.)
   - **Background tasks:**
     `python3 -I ~/.claude/skills/session-handoff/scripts/bg-tasks.py`
     (add `--transcript <earlier.jsonl>` for tasks started before a `/clear`).
     Never a hand-written `ps | grep` filter: it can only show what you thought
     to match. Label each open task:
     - **waiter** — record its command VERBATIM and run its condition once now;
       record the result. It must be false. A condition already true is a
       broken waiter (a stale report file passes a bare `[ -f … ]`): fix it
       before writing the note. A report condition checks the report was
       written by this dispatch (mtime after the dispatch), never bare existence.
     - **work** — its log path and exit-code file.
     Also record running workflows (each `resumeFromRunId`) and detached
     processes + the ports they hold.
   - **Herd panes**, when `HERDR_ENV=1`:
     `bash ~/.claude/skills/session-handoff/scripts/herd-snapshot.sh [extra-root …]`
     (read-only; it lists every pane whose cwd is this repo or a worktree of it, and
     you pass any dir outside the repo where this front launched panes). Record
     each line it prints and classify the pane as **self**, **worker** of this
     front, **shell** (the command it runs + its log) or **not mine**. For a
     worker, also record model + effort, worktree + branch, brief path + sha256,
     deliverable path, and its waiter command verbatim. Match on `session=`
     first: herdr resumes an agent by it after a restore, where pane ids can
     change and names clear. A `/clear` inside the pane starts a new session, so
     pane id and then name are the fallbacks.
   - Session crons — and ANY text the Next step orders re-issued (cron prompt,
     agent dispatch brief, relaunch line): VERBATIM in the note, or in a durable
     file (`./tmp/…`, never `/tmp`) whose path the note records. Includes a cron
     deleted at wrap-up. "In this session's transcript" is never a valid location
     — RESUME is forbidden to read it.
   - `gh pr status` (skip silently if no remote / no gh)
4. **Write the note** (template below). Fill every section: for In flight, write
   the finding for each class **or `none (checked)`** — a present `none` proves
   you looked; an absent section reads as "forgot to check". Backlog lists
   every plan item not done, each with what it means: an item name alone
   forces the successor to guess.

Discipline: hand off at 50% of the context meter, not at the wire. Inside
herdr, relay to a new session (`/relay`); outside it, `/handoff`, then `/clear`,
then `/pickup`. A lead never compacts instead.
```

(d) In the template, find

```
    ## Next step          (ONE concrete move)

    ## What we tried / dead ends
```

replace with

```
    ## Next step          (ONE concrete move)

    ## Backlog            (every plan item not done: deferred or not started)
    <one line each: what it means · why it waits · what unblocks it. A name
    alone is not enough: the successor must never have to guess what an item
    means.>

    ## What we tried / dead ends
```

(e) In the template, find

```
    ## In flight
    <for EACH class: the finding, or `none (checked)` — tasks/agents · workflow
```

replace with

```
    ## In flight
    <for EACH class: the finding, or `none (checked)` — background tasks from
    bg-tasks.py, one line per task id: command, waiter or work, and the
    condition result (waiter) or log + exit-code file (work) · workflow
```

(f) In the template, find

```
    ## Artifacts          (paths, branches, PRs)
```

replace with

```
    ## Artifacts          (paths, branches, PRs)

    ## Memory             (`clean (checked)`, or the debt memory-check.py left)

    ## Relay Q&A          (RELAY only: the successor's questions, answered here)

    ## Pickup gaps        (written by the successor after it takes over)
```

(g) Find

```
Core four (Summary, Decisions, State, Next step) always; the rest adapt to the
```

replace with

```
Core four (Summary, Decisions, State, Next step) plus Backlog and Memory always; the rest adapt to the
```

(h) Find

```
**The note is a claim; reality is the authority.** Distrust it structurally —
verify even when nobody told you to, even when the note "looks complete".
```

replace with

```
**The note is a claim; reality is the authority.** Distrust it structurally —
verify even when nobody told you to, even when the note "looks complete".

**Relay sub-mode.** When the arguments carry `relay=<dir>`, you are a relay
successor: follow `references/relay.md` § Successor on top of the steps below.
In short — read-only until the hand-over (no dispatch, merge or spend; do NOT
stamp the note yet), arm your own waiters marked `relay-<id>-w<k>`, write
`<dir>/receipt.json`, end your turn addressed to the predecessor. After the
hand-over, a clean pickup keeps driving under the standing instruction quoted
in `handover.md`; it does not wait for confirmation. Log anything the note
lacked per `references/feedback.md`.
```

(i) Find

```
4. **Afterwards: stamp what you consumed** on disk —
```

replace with

```
4. **Afterwards: stamp what you consumed** on disk (in relay sub-mode: only
   after the hand-over) —
```

(j) Find `## Red flags — you are about to violate this skill` and insert this section immediately before it:

```
## RELAY mode

A relay is SAVE, a successor in a new herdr pane that RESUMEs, and a hand-over.
Read `references/relay.md` before the first step: it has the full protocol, the
file formats and the failure table. Outline:

1. Outside herdr (`HERDR_ENV` unset), refuse: use `/handoff`, `/clear`, `/pickup`.
2. Wait for the preconditions: no subagent or workflow running inside this
   session, git not mid-operation, attached work finished. Answer any worker
   blocked on a question within its brief. Then **freeze**: no new dispatch,
   merge or spend.
3. SAVE (above). Then
   `python3 -I ~/.claude/skills/session-handoff/scripts/relay-check.py checklist --note <note>`
   prints the relay dir.
4. `bash ~/.claude/skills/session-handoff/scripts/relay-launch.sh <relay-dir>`.
5. Wait on `<relay-dir>/receipt.json` with a background until-loop, never on
   the screen.
6. `python3 -I ~/.claude/skills/session-handoff/scripts/relay-check.py compare <relay-dir>`.
   Fix and answer under the note's `## Relay Q&A`, at most 2 rounds; then stop
   and ask the owner.
7. Hand-over: stop your waiters once the successor's are live, write
   `<relay-dir>/handover.md`, send "Read <relay-dir>/handover.md; you have the
   lead.", end your turn. Never close your own pane: the successor does, with
   `bash ~/.claude/skills/session-handoff/scripts/relay-close.sh <relay-dir>`.

```

(k) Find

```
- Leaving a consumed note unstamped, or skipping the handoff because
  "compaction will summarize it anyway"
```

replace with

```
- Leaving a consumed note unstamped, or skipping the handoff because
  "compaction will summarize it anyway"
- Recording background tasks from a hand-written `ps | grep` instead of
  `bg-tasks.py`
- Saving a waiter whose condition is already true
- In a relay: closing your own pane, stamping the note before the hand-over,
  or acting in the old pane after it
```

- [ ] **Step 4: Write `references/relay.md`**

Create `private_dot_claude/skills/session-handoff/references/relay.md`:

```markdown
# Relay protocol

A relay hands the lead from this session (the **predecessor**) to a new Claude
session in a new herdr pane (the **successor**), which picks up, takes over and
closes the predecessor. Scripts own facts and mechanics; the model owns
judgement. Script paths are under `~/.claude/skills/session-handoff/`.

Every relay has a **relay dir**, `~/.claude/projects/<project>/relay/<relay-id>/`,
beside `memory/` and never inside it, so nothing here loads or counts against
the MEMORY.md cap. Files: `checklist.json` and `launch.json` (scripts, for the
predecessor), `receipt.json` (successor), `handover.md` (predecessor),
`closed.json` (script, for the successor), `failed.json` (scripts, on failure).
The project's current lead is recorded in `~/.claude/projects/<project>/relay/lead.json`.

## Predecessor

1. **Refuse outside herdr.** `HERDR_ENV` unset: say so and use `/handoff`,
   `/clear`, `/pickup`.
2. **Preconditions.** Wait until no subagent or workflow runs inside this
   session (they die with it), git is not mid-merge, rebase, cherry-pick or
   revert, and attached work has finished. `relay-check.py checklist` refuses
   (exit 3) on the first two and names them. If a worker is `blocked` on a
   question you can answer within its brief, answer it now; otherwise record
   it in the note.
3. **Freeze.** From here: no new dispatch, merge, spend or score. Note
   arrivals (deliveries, notifications) for `handover.md`; do not act on them.
4. **SAVE** (SKILL.md), including the memory check. From the launch on you
   write no memory: late facts go in `handover.md`.
5. **Checklist.** `python3 -I scripts/relay-check.py checklist --note <note path>`
   (add `--extra-root <dir>` for each dir outside the repo where this front
   launched panes, `--transcript <earlier.jsonl>` for tasks started before a
   `/clear`). It prints the relay dir.
6. **Launch.** `bash scripts/relay-launch.sh <relay-dir>`. It splits this pane
   down, starts `lead-<project>-next` with your model, effort and permission
   mode, checks the banner, and sends `/pickup relay=<relay-dir>`. Exit 1:
   `failed.json` is written and the new pane closed. Keep driving and tell the
   owner.
7. **Wait on the receipt**, never on the screen: a background until-loop on
   `receipt.json` newer than `launch.json` AND `herdr agent get
   lead-<project>-next` not reporting `working`.
8. **Check.** `python3 -I scripts/relay-check.py compare <relay-dir>`.
   - PASS: go to step 9.
   - FAIL: fix what each line names. Correct the note; answer the successor's
     questions and explain drift under the note's `## Relay Q&A`; then tell the
     successor: "Re-read <items> in the note and rewrite <relay-dir>/receipt.json."
     Wait and compare again. At most **2** fix rounds. Still failing, or a
     question only the owner can answer: write `failed.json`
     (`{"stage": "check", "reason": "<the FAIL lines>", "attempts": <rounds>}`),
     keep the lead, tell the owner. Close nothing.
9. **Hand-over** (make before break). The compare proved the successor's
   waiters live. Stop your own waiters (`TaskStop` each), write
   `<relay-dir>/handover.md` (format below), and send the successor exactly:
   `Read <relay-dir>/handover.md; you have the lead.` End your turn.
10. **After the hand-over** you are done. If anyone types into this pane,
    reply only: "The lead moved to pane <pane> (<name>)." Never close your own
    pane: the successor closes it.

### handover.md

    # Hand-over <relay-id>

    ## Standing instruction
    > <the owner's instruction you were driving under, verbatim>
    — given <UTC time>

    ## Arrived during the relay
    <deliveries, notifications and worker state changes since the freeze, or `none`>

    ## Late facts for memory
    <durable facts learned after the SAVE, or `none`; the successor writes them>

## Successor (`/pickup relay=<dir>`)

1. **Normal RESUME**, reality outranking the note, plus:
   - **Read-only until the hand-over**: no dispatch, merge, spend or score; do
     not stamp the note.
   - Read `<dir>/checklist.json` and verify it against reality: git, each
     worker (`herdr agent get`, read-only), deliverables, background tasks.
   - For each open background task you keep and each worker, arm your own
     waiter (a background until-loop) whose command starts with
     `: relay-<relay-id>-w<k>;` so `pgrep -f` finds it. Conditions check a
     report written by this dispatch (mtime after the dispatch), never bare
     existence. Re-arm the checklist's crons that still apply (a one-shot whose
     time has passed is dropped, with that reason).
   - Write `<dir>/receipt.json` (format below). Its `successor` block is the
     output of `python3 -I scripts/relay-check.py identity`.
   - End your turn with a summary addressed to the predecessor.
2. **On "you have the lead":** read `handover.md`, write its late facts to
   memory, stamp the note `resumed`. If the note's Memory section carries
   debt, fix it first (read MEMORY.md in full: the part past the cap never
   loaded into your context).
3. **Close the predecessor:** `bash scripts/relay-close.sh <dir>`. A refusal
   names the failed check and leaves the pane open; if a prompt reached the old
   pane, tell the owner.
4. **Drive.** A clean pickup continues under the standing instruction exactly
   as `handover.md` quotes it, no wider. Drift you cannot resolve, a mismatch
   the predecessor could not explain, or a question only the owner can answer:
   stop and ask.
5. **First message to the owner:** relay id, compare result, what is in
   flight, memory status, and any gap proposals (`references/feedback.md`).

### receipt.json

    {
      "relay_id": "<id>",
      "successor": {"...": "output of relay-check.py identity"},
      "note": {"path": "<note path>", "sha256": "<sha256 of the note as you read it>"},
      "tier": "clean",
      "drift": [{"item": "<what differs>", "explanation": "<filled once the predecessor explains it>"}],
      "tasks": [{"id": "<checklist task id>", "action": "rearmed | watching-exit-file | drop",
                 "marker": "relay-<id>-w<k>", "reason": "<required for drop>"}],
      "workers": [{"pane_id": "<pane>", "status_seen": "<status>", "waiter_marker": "relay-<id>-w<k>",
                   "reason": "<required when there is no waiter>"}],
      "crons": [{"id": "<cron id>", "action": "rearmed | drop", "reason": "<required for drop>"}],
      "disagreements": [],
      "questions": [],
      "gaps": []
    }

`compare` passes only when identity and note match, every checklist task,
worker and cron is accounted for, every marker is live, and `questions`,
`disagreements` and unexplained `drift` are empty. `tier` is `drift` when you
found any; each drift item needs the predecessor's explanation before it passes.

## Failure table

| Situation | Behaviour |
|---|---|
| Outside herdr | `/relay` refuses; manual `/handoff`, `/clear`, `/pickup` |
| Subagent or workflow running, attached work running, git mid-operation | wait; the relay does not start |
| Successor fails to start | one retry; then `failed.json`, the predecessor keeps driving and tells the owner |
| Check fails | up to 2 fix rounds, then `failed.json`, ask the owner; nothing closed |
| Worker delivers during the relay | the predecessor notes it in `handover.md`; the successor's waiter fires on it |
| Worker blocked on a question | answered before the freeze if within its brief; otherwise in the note |
| Owner types into the old pane after the hand-over | the predecessor points to the new pane; `relay-close.sh` refuses; the successor tells the owner |
| Successor dies after the hand-over | the old pane is still open (only the successor closes it); the owner resumes it |
| Memory index over the cap | the relay proceeds; debt in the note; the successor's first job |
```

- [ ] **Step 5: Write `references/feedback.md`**

Create `private_dot_claude/skills/session-handoff/references/feedback.md`:

```markdown
# Pickup gaps → owner-approved skill changes

## Detect

Whenever, as a successor (relay or plain `/pickup`), you find the note lacked
something you needed:
- 3 or more searches for something the note does not name;
- a question to the owner about knowledge from before the handoff;
- verification contradicting the note;
- re-deriving something the predecessor had already stated;
- the predecessor's tasks not matching the checklist.

During a relay these are receipt `questions` for the predecessor. After the
hand-over, log them straight away.

## Record

1. Append one JSON line to `~/.claude/handoff-feedback/gaps.jsonl`:

       {"date": "YYYY-MM-DD", "project": "<repo basename>", "relay_id": "<id or null>",
        "predecessor_session": "<id>", "successor_session": "<id>",
        "missing": "<what was missing, one sentence>",
        "cost": "<calls and tokens, or 'asked the owner'>",
        "section": "<template section that should have held it, or 'none'>",
        "kind": "no-slot | slot-empty | stale-or-wrong | check-cannot-fail | protocol",
        "severity": "serious | minor", "fixed_by": null}

2. Add one line under the consumed note's `## Pickup gaps`.

Kinds: **no-slot**, the template has no place for it; **slot-empty**, the place
exists but was left empty or incomplete; **stale-or-wrong**, present but stale
or wrong; **check-cannot-fail**, a recorded check that passes whatever happens;
**protocol**, a relay or pickup step missing or wrong.

**Serious**: an owner question the predecessor could have answered; a wrong or
duplicate action; a safety check that could not fail. Everything else is minor.

## Fire

Draft a proposal when the new gap is serious, or when `gaps.jsonl` already
holds a gap with the same `kind` and `section` from a different handoff (a
different `predecessor_session`). A recurring gap whose earlier line has
`fixed_by` set is a regression: always propose, and say so.

## Propose, never apply

1. Write `~/.claude/handoff-feedback/proposals/<YYYY-MM-DD>-<slug>.md`: the
   gap lines (evidence), the change in one sentence, and a unified diff against
   the chezmoi source `~/.local/share/chezmoi/private_dot_claude/skills/session-handoff/`
   (never the deployed copy).
2. Add a `~/TODO.md` entry tagged `#session-handoff` pointing at it, in the
   `todo` skill's format.
3. Mention it in your next report to the owner. Applying it is the owner's
   call; once approved, a separate session applies it with
   `superpowers:writing-skills` and commits it in the dotfiles repo.
```

- [ ] **Step 6: Write the command**

Create `private_dot_claude/commands/relay.md`:

```markdown
---
description: Hand the lead to a new session in a new herdr pane (session-handoff RELAY mode)
---

Use the `session-handoff` skill in **RELAY mode**. Reason: $ARGUMENTS
```

- [ ] **Step 7: Edit `CLAUDE.md`**

In `private_dot_claude/CLAUDE.md`, find

```
A background until-loop or Monitor on "report file exists AND agent status is not `working`".
```

replace with

```
A background until-loop or Monitor on "a report written by this dispatch (mtime after the dispatch) AND agent status is not `working`": a bare file-exists check passes on a stale report from an earlier run.
```

Then find

```
  `/handoff`, `/pickup` — a session-opening "where do we stand?" goes to `/pickup`.
```

and insert this line right after it:

```
- **hand the lead to a new session** (at 50% context, or when asked) → `/relay`
```

- [ ] **Step 8: Run the docs test and the whole suite**

Run: `cd ~/.local/share/chezmoi && python3 -m unittest discover -s tests -p 'test_handoff_docs.py' -v && task test`
Expected: 4 docs tests `ok`; full suite green (the pre-existing render, git-exclusion and operation tests included).

- [ ] **Step 9: Commit**

```bash
cd ~/.local/share/chezmoi
git add tests/test_handoff_docs.py private_dot_claude/skills/session-handoff/SKILL.md \
  private_dot_claude/skills/session-handoff/references/relay.md \
  private_dot_claude/skills/session-handoff/references/feedback.md \
  private_dot_claude/commands/relay.md private_dot_claude/CLAUDE.md
git commit -m "session-handoff: RELAY mode, Backlog and Memory sections, the gap loop, /relay"
```

(Leave `private_dot_claude/CLAUDE.md` out of `git add` if the owner did not approve the "Before Task 1" commit, and say so in the report.)

---

### Task 9: Seed the gap log

**Files:**
- Create: `~/.claude/handoff-feedback/gaps.jsonl` (outside the repo; not chezmoi-managed)

**Interfaces:**
- Produces: the log `references/feedback.md` appends to; 10 lines from the 2026-10-12 research (`$HOME/code/claude/tmp/relay-design/feedback-loop.md` §2–§3).

- [ ] **Step 1: Write the file (refuse to overwrite)**

```bash
mkdir -p ~/.claude/handoff-feedback/proposals
f=~/.claude/handoff-feedback/gaps.jsonl
[ -e "$f" ] && { echo "gaps.jsonl already exists; not overwriting"; exit 1; }
cat > "$f" <<'EOF'
{"date": "2026-10-12", "project": "acme-consult-agent-alpha-beta", "relay_id": null, "predecessor_session": "c3c3c3c3", "successor_session": "a1a1a1a1-a1a1-4a1a-8a1a-a1a1a1a1a1a1", "missing": "Run-layout paths were elided from the Next step (writer request path without run directories)", "cost": "up to 15 calls", "section": "Next step", "kind": "slot-empty", "severity": "minor", "fixed_by": null}
{"date": "2026-10-12", "project": "acme-consult-agent-alpha-beta", "relay_id": null, "predecessor_session": "c3c3c3c3", "successor_session": "a1a1a1a1-a1a1-4a1a-8a1a-a1a1a1a1a1a1", "missing": "Cost and cache figures were carried without the population they measure", "cost": "caught only by the owner's external audit", "section": "Summary", "kind": "stale-or-wrong", "severity": "minor", "fixed_by": null}
{"date": "2026-10-12", "project": "acme-consult-agent-alpha-beta", "relay_id": null, "predecessor_session": "c3c3c3c3", "successor_session": "a1a1a1a1-a1a1-4a1a-8a1a-a1a1a1a1a1a1", "missing": "The worker-routing and launch memories to read first were not named", "cost": "1 call", "section": "none", "kind": "no-slot", "severity": "minor", "fixed_by": null}
{"date": "2026-10-12", "project": "acme-consult-agent-alpha-beta", "relay_id": "manual-2026-10-12T2024Z", "predecessor_session": "a1a1a1a1-a1a1-4a1a-8a1a-a1a1a1a1a1a1", "successor_session": "b2b2b2b2-b2b2-4b2b-8b2b-b2b2b2b2b2b2", "missing": "A recorded waiter checked [ -f RUN-REPORT.sha256 ] while an older report was on disk, so it would pass at once", "cost": "2 calls to catch", "section": "In flight", "kind": "check-cannot-fail", "severity": "serious", "fixed_by": "2026-10-12-session-relay-design"}
{"date": "2026-10-12", "project": "acme-consult-agent-alpha-beta", "relay_id": "manual-2026-10-12T2024Z", "predecessor_session": "a1a1a1a1-a1a1-4a1a-8a1a-a1a1a1a1a1a1", "successor_session": "b2b2b2b2-b2b2-4b2b-8b2b-b2b2b2b2b2b2", "missing": "A running disk watcher (1 of 3 background tasks) was not recorded and died unreplaced", "cost": "a guard silently disappeared", "section": "In flight", "kind": "slot-empty", "severity": "minor", "fixed_by": "2026-10-12-session-relay-design"}
{"date": "2026-10-12", "project": "acme-consult-agent-alpha-beta", "relay_id": "manual-2026-10-12T2024Z", "predecessor_session": "a1a1a1a1-a1a1-4a1a-8a1a-a1a1a1a1a1a1", "successor_session": "b2b2b2b2-b2b2-4b2b-8b2b-b2b2b2b2b2b2", "missing": "Two deferred plan items (walkthrough headline, tecnico identity fix) with their meaning and trigger", "cost": "12 searches, about 13.2k tokens, and an owner question with a wrong guess", "section": "none", "kind": "no-slot", "severity": "serious", "fixed_by": "2026-10-12-session-relay-design"}
{"date": "2026-10-12", "project": "acme-consult-agent-alpha-beta", "relay_id": "manual-2026-10-12T2024Z", "predecessor_session": "a1a1a1a1-a1a1-4a1a-8a1a-a1a1a1a1a1a1", "successor_session": "b2b2b2b2-b2b2-4b2b-8b2b-b2b2b2b2b2b2", "missing": "A worker brief's sha256 was missing", "cost": "1 call", "section": "In flight", "kind": "slot-empty", "severity": "minor", "fixed_by": null}
{"date": "2026-10-12", "project": "acme-consult-agent-alpha-beta", "relay_id": "manual-2026-10-12T2024Z", "predecessor_session": "a1a1a1a1-a1a1-4a1a-8a1a-a1a1a1a1a1a1", "successor_session": "b2b2b2b2-b2b2-4b2b-8b2b-b2b2b2b2b2b2", "missing": "The worker launch line the Next step ordered re-issued was not carried verbatim", "cost": "3 calls", "section": "Next step", "kind": "slot-empty", "severity": "minor", "fixed_by": null}
{"date": "2026-10-12", "project": "acme-consult-agent-alpha-beta", "relay_id": "manual-2026-10-12T2024Z", "predecessor_session": "a1a1a1a1-a1a1-4a1a-8a1a-a1a1a1a1a1a1", "successor_session": "b2b2b2b2-b2b2-4b2b-8b2b-b2b2b2b2b2b2", "missing": "No relay protocol: the successor improvised the transfer while the predecessor was alive with live waiters", "cost": "2 calls and a double-scorer risk", "section": "none", "kind": "protocol", "severity": "minor", "fixed_by": "2026-10-12-session-relay-design"}
{"date": "2026-10-12", "project": "acme-consult-agent-alpha-beta", "relay_id": "manual-2026-10-12T2024Z", "predecessor_session": "a1a1a1a1-a1a1-4a1a-8a1a-a1a1a1a1a1a1", "successor_session": "b2b2b2b2-b2b2-4b2b-8b2b-b2b2b2b2b2b2", "missing": "The in-place rewrite of the note dropped earlier root causes and a pointer to the debug files", "cost": "unproven", "section": "Summary", "kind": "stale-or-wrong", "severity": "minor", "fixed_by": null}
EOF
```

- [ ] **Step 2: Validate**

Run: `python3 -I -c "import json,sys; rows=[json.loads(l) for l in open(sys.argv[1])]; print(len(rows), sum(1 for r in rows if r['fixed_by']))" ~/.claude/handoff-feedback/gaps.jsonl`
Expected: `10 4`.

No commit (the file lives outside the repo). Record the validation output in the task report.

---

### Task 10: Deploy and run the end-to-end relay (definition of done)

Run by the orchestrator, not delegated: it drives herdr and real Claude sessions.

**Files:** none in the repo. Evidence goes to `$HOME/code/claude/tmp/relay-e2e/E2E-REPORT.md`.

- [ ] **Step 1: Gates**

Run: `cd ~/.local/share/chezmoi && task test`
Expected: all green.

- [ ] **Step 2: Deploy only the relay paths**

```bash
cd ~/.local/share/chezmoi
chezmoi apply ~/.claude/skills/session-handoff ~/.claude/commands/relay.md ~/.claude/CLAUDE.md
chezmoi diff ~/.claude/skills/session-handoff ~/.claude/commands/relay.md ~/.claude/CLAUDE.md | wc -l
```

Expected: `0`.

- [ ] **Step 3: Build the scratch front**

```bash
E=$HOME/code/claude/tmp/relay-e2e; rm -rf "$E"; mkdir -p "$E/repo/tmp"
cd "$E/repo" && git init -q && echo e2e > README.md && printf 'tmp/\n' > .gitignore && git add . \
  && git -c user.name=E2E -c user.email=e2e@example.invalid commit -qm init
P=$HOME/.claude/projects/$(printf '%s' "$E/repo" | sed 's#[^A-Za-z0-9]#-#g')
tab=$(herdr tab create --cwd "$E/repo" --label relay-e2e --no-focus)
lead=$(printf '%s' "$tab" | python3 -I -c 'import json,sys; print(json.load(sys.stdin)["result"]["root_pane"]["pane_id"])')
worker=$(herdr pane split "$lead" --direction right --cwd "$E/repo" --no-focus | python3 -I -c 'import json,sys; print(json.load(sys.stdin)["result"]["pane"]["pane_id"])')
herdr pane run "$worker" "until [ -f $E/repo/tmp/go ]; do sleep 2; done; echo delivered > $E/repo/tmp/deliverable.md"
herdr agent start e2e-lead --kind claude --pane "$lead" --timeout 90000 -- --model claude-sonnet-5-5 --effort medium --dangerously-skip-permissions
herdr agent prompt e2e-lead "Arm a waiter with the Bash tool, run_in_background true, command exactly: until [ -f tmp/deliverable.md ]; do sleep 5; done; echo delivered. Then write PLAN.md with two lines: '1. wait for the worker deliverable' and '2. report it'. Reply ARMED." --wait --timeout 300000
```

- [ ] **Step 4: Relay (pass case)**

`herdr agent prompt e2e-lead "/relay end-to-end test of the relay protocol"` (no `--wait`). Then wait in a background until-loop (never a foreground sleep):

```bash
until ls "$P"/relay/*/closed.json "$P"/relay/*/failed.json >/dev/null 2>&1; do sleep 10; done
```

Then verify, recording every command and its output in `E2E-REPORT.md`:

```bash
R=$(ls -d "$P"/relay/2*/ | tail -1); R=${R%/}
ls "$R"                                               # checklist launch receipt handover closed .json/.md, no failed.json
python3 -I ~/.claude/skills/session-handoff/scripts/relay-check.py compare "$R"   # PASS
herdr agent get e2e-lead 2>&1 | grep -c agent_not_found                          # 1: old lead gone
herdr agent get lead-repo | python3 -I -c 'import json,sys; print(json.load(sys.stdin)["result"]["agent"]["agent_status"])'
cat "$P/relay/lead.json"
pgrep -fl "relay-$(basename "$R")-w"                                              # the successor's waiter
touch "$E/repo/tmp/go"
until ! pgrep -f "relay-$(basename "$R")-w" >/dev/null; do sleep 5; done          # background loop: waiter fires
```

Expected: every line as commented; the successor's transcript then holds a `task-notification` with `<status>completed</status>` for its waiter.

- [ ] **Step 5: Relay (fail case: a dropped task must stop the relay)**

```bash
herdr agent prompt lead-repo "Arm a waiter with the Bash tool, run_in_background true, command exactly: until [ -f tmp/deliverable2.md ]; do sleep 5; done. Reply ARMED." --wait --timeout 300000
touch "$E/tamper-start"
bash -c 'while true; do for r in '"$P"'/relay/*/receipt.json; do [ "$r" -nt '"$E"'/tamper-start ] || continue; python3 -I -c "import json,sys; p=sys.argv[1]; d=json.load(open(p)); d.get(\"tasks\") and (d.update(tasks=[]) or json.dump(d, open(p, \"w\")))" "$r"; done; sleep 0.2; done' &
tamper=$!
herdr agent prompt lead-repo "/relay end-to-end failure test"
until ls "$P"/relay/*/failed.json >/dev/null 2>&1 || [ "$(ls "$P"/relay/*/closed.json 2>/dev/null | wc -l)" -gt 1 ]; do sleep 10; done
kill "$tamper"
```

Expected: the newest relay dir has `failed.json` with `"stage": "check"` and no `closed.json`; `herdr agent get lead-repo` still answers (the predecessor kept the lead); `compare` on that dir prints `FAIL task ... is not in the receipt`. Record all of it.

If the sonnet sessions fail a judgement step (not a script), rerun Steps 3–5 with `claude-opus-5-5` before treating it as a design bug.

- [ ] **Step 6: Clean up the scratch front**

```bash
pkill -f "$E/repo/tmp/go" 2>/dev/null   # the worker loop, if still waiting
herdr tab close "$(printf '%s' "$tab" | python3 -I -c 'import json,sys; print(json.load(sys.stdin)["result"]["tab"]["tab_id"])')"
```

Keep `$E` and `$P/relay/` for the report. Then finish the branch with `superpowers:finishing-a-development-branch` (merging and pushing follow the owner's confirmation rules).

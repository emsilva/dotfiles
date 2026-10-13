# Session relay: design (piece 1 of 2, the `session-handoff` skill)

Date: 2026-10-12. Status: approved in conversation, section by section; this file is the written spec for review.

## Goal

A long-running lead session hands off to a **new session in a new herdr pane** and closes, without the owner
driving each step. That's today's manual relay, scripted and made safe. Piece 1 (this spec) is the skill:
what a handoff records, the relay protocol, the successor's pickup, and the loop that turns pickup gaps into
owner-approved skill changes. Piece 2 (separate spec, later) is the hook that fires `/relay` at 50% context.

## Background: the relay of 2026-10-12

At 82% context the owner had the Alpha lead (session a1a1a1a1, pane wZ:p42) run `/handoff`, split its pane
down, start a successor with the same model and effort, send it `/pickup`, check the result, hand over and close
itself. It worked, and the successor (b2b2b2b2) is driving. Seven read-only research agents, a synthesis and a
critic then measured what went wrong. Their reports are in `$HOME/code/claude/tmp/relay-design/` (not in
this repo). The defects this spec fixes:

| # | Defect (measured) | Fixed by |
|---|---|---|
| D1 | The note recorded 2 of 3 open background tasks; a disk watcher was dropped because SAVE used a hand-written `ps \| grep` filter that could not match it | `bg-tasks.py` (SAVE step 3) |
| D2 | A waiter checked `[ -f RUN-REPORT.sha256 ]` while an older report was on disk, so it would pass at once | condition shown false at save (SAVE step 3); CLAUDE.md wording |
| D3 | Two deferred plan items were absent from the note; 61 s after the old lead closed, the successor found them, spent 12 searches and ~13k tokens, then asked the owner with a wrong guess | Backlog section; question round while the old lead is alive |
| D4 | A memory written at 20:29 pushed MEMORY.md over the loader cap (25,000 UTF-16 units) after the successor had loaded it | memory before the note; `memory-check.py` |
| D5 | Acceptance was the old lead reading 45 lines of the successor's screen | checklist + receipt, compared by `relay-check.py` |
| D6 | The old lead closed its own pane mid-turn: the close never reached its transcript, and anything queued for it would have been lost | the successor closes it, by fact (`relay-close.sh`) |
| D7 | The note was stamped `resumed` 2 minutes before the hand-over | successor stamps only after the hand-over |
| D8 | Both leads ran waiters on the same workers for ~2.5 min ("we'd start two scorers ... and pay twice") | freeze; make-before-break; stop old waiters at hand-over |
| D9 | `ps \| grep claude` returned two processes, one from another project | identity from `CLAUDE_CODE_SESSION_ID`, `CLAUDE_EFFORT`, `CLAUDE_PID` and the transcript |
| D10 | Names did not chain (`lead-next-xhigh` cannot be reused while held) | `lead-<project>-next`, renamed to `lead-<project>` after the close |

## Owner decisions (2026-10-12)

1. No "unit of work" trigger. A relay happens at 50% context (piece 2), when the owner asks, or when the lead
   judges it wise. Measured: relaying after every unit would have fired 13 to 18 times in today's 6.6 h session.
2. Long work (tests, builds, paid runs) starts detached with an exit-code file, so it survives a relay. Already in
   `~/.claude/CLAUDE.md`, "Long work outlives its session". Tested: a `nohup`-detached process survived its
   session's pane close and wrote its exit file; a `run_in_background` one was killed.
3. The successor closes the old lead, after checking facts.
4. Memory check: fix what is safe, carry the rest as debt in the note.
5. After a clean pickup the successor keeps driving under the owner's standing instruction; drift, an
   unexplained mismatch or an owner-only question stops it and goes to the owner.
6. Gaps: log every one; draft a proposal only for a serious gap or a repeated one; never auto-apply.
7. Approach: relay mode inside `session-handoff` with five scripts (one skill owns the note contract).

## Design

### 1. SAVE changes (every `/handoff`, relay or not)

1. **Attached work first.** A test, build or paid run still attached to the session (a `run_in_background`
   command that is work, not a waiter) finishes before the session closes. SAVE records anything still running.
2. **Memory before the note** (moved up from the old step 4). Write durable facts, then run
   `memory-check.py --fix`. Safe fixes only: add an index line for each memory file written this session that
   the index lacks, and remove index lines whose target file is gone. If the index would still load cut off, or
   older orphans remain, the note's **Memory** section records it as the successor's first job.
3. **Snapshots.** Git and `herd-snapshot.sh` as today. "Background work you started" comes from `bg-tasks.py`.
   The model labels each open task:
   - **waiter**: command recorded verbatim, plus its condition run once now with the result recorded; it must
     be false. A condition that is already true is a broken waiter (D2) and is fixed before the note is written.
     Conditions on a report check that it was written by this dispatch (mtime after the dispatch), not that it
     exists.
   - **work**: its log path and exit-code file.
4. **Template additions.**
   - `## Backlog`: every plan item not done (deferred or not started), one line each: what it means, why it
     waits, what unblocks it.
   - `## Memory`: `clean (checked)` or the debt for the successor.
   - `## In flight`: background tasks come from `bg-tasks.py`, one line per task id: command, waiter or work,
     and the condition result or log path.
5. **Timing line** (SKILL.md line 60, "save at ~50-60% ... for direct continuation, compact instead") becomes:
   hand off at 50% of the context meter by relaying to a new session (`/relay`) inside herdr; outside herdr,
   `/handoff`, `/clear`, `/pickup`. A lead never compacts instead.

### 2. RELAY mode, the old lead's side (`/relay [reason]`)

1. **Start.** Typed by the owner, run by the lead itself, or fired by piece 2's hook.
2. **Preconditions.** Without `HERDR_ENV=1`, refuse and point to `/handoff`, `/clear`, `/pickup`. Inside
   herdr, wait until: no subagent or workflow runs inside this session (they die with it); git is not
   mid-operation (`MERGE_HEAD`, `CHERRY_PICK_HEAD`, `REVERT_HEAD`, `rebase-merge/`, `rebase-apply/`); attached
   work has finished. If a worker is blocked on a question the lead can answer within that worker's brief,
   answer it. Then **freeze**: no new dispatches, merges or paid runs; arrivals are noted, not acted on.
3. **Save.** Section 1's SAVE, then `relay-check.py checklist` writes `checklist.json` from instruments into the
   relay dir `~/.claude/projects/<enc>/relay/<relay-id>/` (a sibling of `memory/`, so it never loads or
   counts against the index cap).
4. **Launch.** `relay-launch.sh <relay-dir>`.
5. **Wait.** A background until-loop on: `receipt.json` exists, is newer than `launch.json`, and the successor
   is `idle` or `done` (`unknown` never counts as finished). No screen reading. The loop is bounded: it also
   ends 20 minutes after `launch.json` (15 minutes after each fix round's request), when `herdr agent get` reports
   the successor `agent_not_found`, or when its `agent_status` stays `blocked` for 8 consecutive polls (about 2
   minutes; a successor waiting on an approval to write `receipt.json` must not be failed at the first poll).
   Each fix round waits on its own anchor, `<relay-dir>/fix-<round>`, touched when the round's request is sent
   (the receipt is already newer than `launch.json`, so that anchor would pass at once). Every `herdr agent get`
   in a wait loop runs with a 10-second timeout, and a read that fails, hangs or answers no JSON counts as
   `unread` (keep waiting), so one hung herdr call cannot hold a loop past its deadline. Without a usable
   receipt the relay stops as in step 6, with `failed.json` `"stage": "receipt"`: the old lead closes the
   successor it launched (after the identity check in step 6), records `successor_closed`, keeps the lead and
   tells the owner.
6. **Check.** `relay-check.py compare <relay-dir>`. On failure, the old lead fixes the note, and in the note's
   `## Relay Q&A` answers the successor's questions and disagreements (correcting the note, or showing with
   evidence why it stands) and explains drift. It then touches `<relay-dir>/fix-<round>` and tells the successor
   to re-read only those items and rewrite the receipt, and waits as in step 5. At most 2 rounds. After that, or
   on a question only the owner can answer, the relay stops. The old lead writes `failed.json` and closes the
   successor pane it launched (the successor never received the lead and stayed read-only; a live
   `lead-<project>-next` would block the next relay's launch with `agent_name_taken`), but only after checking
   what that pane hosts now: pane ids can change (a herdr restore renumbers them), and after a successor that
   went `agent_not_found` the recorded id is least trustworthy. `herdr agent get <launch.json pane_id>` must
   report `agent_session.value` equal to `launch.json`'s `session_id`, or `name` equal to its `name` (non-empty
   either way). Then it closes the pane, confirms `herdr agent get <pane>` reports `agent_not_found`, and records
   `successor_closed: true`. Otherwise (another session and name, `agent_not_found`, a failed read) it does not
   close the pane, records `successor_closed: false` with `successor_close_reason`, and tells the owner, naming
   the successor's pane if `herdr agent get <name>` still finds it. It keeps the lead and asks the owner.
   `receipt.json` and `failed.json` stay for inspection.
7. **Hand-over (make before break).** The compare PASS proved every task and worker is covered (a live waiter,
   or one that already fired: `<relay-dir>/fired/<marker>`) and that the successor re-armed the crons that still
   apply. In this order:
   1. Delete the old lead's session crons (`CronDelete`). First, because a cron fire after `handover.md` is
      written is a prompt after the hand-over, and `relay-close.sh` would refuse to close the old pane.
   2. Write `handover.md` once; never edit it after sending (`relay-close.sh` dates the hand-over from its mtime).
   3. Send the successor one line ("Read `<relay-dir>/handover.md`; you have the lead.") with
      `herdr agent prompt` and check its exit status; retry once.
   4. Sent: stop the old lead's own waiters (`TaskStop`) and end the turn. The waiters stop only after the
      confirmed send, so a failed send never leaves the lead with no session holding it; the overlap with the
      successor's waiters lasts seconds and is harmless while the old lead is frozen.
   5. Not sent after the retry: the old lead keeps its waiters and the record, stays frozen, writes `failed.json`
      `"stage": "handover"` (`successor_closed: false`), and tells the owner that the successor holds a valid
      receipt but never got the lead. The owner decides; if the owner completes the hand-over, the successor's
      `closed.json` supersedes that `failed.json`.

   From the memory check on, the old lead writes no memory; late facts go in `handover.md`. If the owner types
   into the old pane afterwards, it only says where the lead moved.
8. **Failure.** The successor fails to start twice, writes no usable receipt, or the check fails past its
   rounds: write `failed.json`, keep driving, tell the owner. These paths close the pane the old lead launched
   (`relay-launch.sh` closes its own on a failed start; step 6, after its identity check, on a failed receipt
   or check). A failed hand-over send (step 7) closes nothing: the owner decides. The old lead is never closed on
   a failed relay.

### 3. RESUME relay sub-mode, the successor's side (`/pickup relay=<dir>`)

1. Normal RESUME (reality outranks the note), plus:
   - **Read-only until the hand-over:** no dispatches, merges or spending; the note is not stamped (D7).
   - Resume the note `checklist.json` names (`note.path`), not whichever note the sweep finds newest; a newer
     note is drift.
   - Verify `checklist.json` against reality: git, each worker's status (`herdr agent get`, read-only),
     deliverables, background tasks.
   - Arm its own waiters with the Bash tool's `run_in_background` (never `nohup` or `&`: only such a task wakes the
     session when it ends), each command prefixed `: relay-<id>-w<k>;` so compare finds it in the process list,
     and ending with `touch <relay-dir>/fired/<marker>`; re-arm crons.
   - Write `receipt.json`: what it needs answered goes in `questions`; a claim of the note or checklist that its
     evidence contradicts goes in `disagreements`; a gap it filled itself goes in `gaps`. End the turn addressed
     to the old lead. Files are the channel: it never types into the old pane (after the hand-over any prompt
     there makes `relay-close.sh` refuse).
   - On a fix round: re-read the named items, remove each settled question and disagreement from the receipt
     (anything only informational moves to `gaps`; one an answer does not settle stays), fill the drift
     explanations, rewrite the receipt, end the turn.
2. **On "you have the lead":** read `handover.md`, save its late facts to memory, stamp the note `resumed`. If
   the note carries memory debt, that is the first job.
3. **Close the old lead:** `relay-close.sh <relay-dir>`. If it refuses because the old lead is still `working`
   (it has not ended its turn), wait in a background loop for it to leave `working`, bounded at 10 minutes and
   reading as in §2 step 5 (a hung read is `unread` and keeps waiting), then run `relay-close.sh` again; a second
   refusal goes to the owner.
4. **Drive.** Clean pickup: keep going under the standing instruction from `handover.md` (quoted, with its
   time, so it is not stretched). Drift, an unexplained mismatch or an owner-only question: stop and ask.
5. **First message to the owner:** relay id, check result, what is in flight, memory status, gap proposals.

### 4. Gap loop

1. **Detection.** Whenever the successor finds the note lacked something: 3+ searches for something the note
   does not name; a question to the owner about pre-relay knowledge; verification contradicting the note;
   re-deriving what the old lead had stated; the old lead's tasks not matching the checklist. During the relay
   these become receipt questions (or disagreements, when the successor's evidence contradicts the note);
   afterwards they go straight to the log.
2. **Recording.** One JSON line per gap in `~/.claude/handoff-feedback/gaps.jsonl` (global, outside chezmoi),
   plus a short `## Pickup gaps` section in the consumed note.
3. **Firing.** A proposal is drafted at once for a **serious** gap (an owner question the old lead could have
   answered; a wrong or duplicate action; a safety check that could not fail), or when the same `kind` +
   `section` pair occurs in two different handoffs.
4. **Proposal.** A diff against the chezmoi source of the skill, saved in
   `~/.claude/handoff-feedback/proposals/<date>-<slug>.md` with its evidence, plus a `~/TODO.md` entry tagged
   `#session-handoff`, mentioned in the successor's next report. Never applied automatically; once approved, a
   separate session applies it with `superpowers:writing-skills` and commits it here.
5. **Seed.** The log starts with the 10 gaps found in today's two pickups. The 3 that would have fired
   (Backlog, scripted task list, question round) are marked `fixed_by: 2026-10-12-session-relay-design`, so a
   repeat counts as a regression.

## Components

All paths are in the chezmoi source unless noted. Python scripts are stdlib-only and run with `python3 -I`.

| File | Change |
|---|---|
| `private_dot_claude/skills/session-handoff/SKILL.md` | SAVE steps reordered and extended; template gains Backlog, Memory, Relay Q&A, Pickup gaps; timing line; short `## RELAY mode` section; relay sub-mode paragraph in RESUME; red flags; description gains relay triggers |
| `.../session-handoff/references/relay.md` | new: full protocol, file formats, failure table |
| `.../session-handoff/references/feedback.md` | new: gap kinds, severity, firing rule, proposal format |
| `.../session-handoff/scripts/bg-tasks.py` | new |
| `.../session-handoff/scripts/memory-check.py` | new |
| `.../session-handoff/scripts/relay-check.py` | new (`checklist` and `compare` modes) |
| `.../session-handoff/scripts/relay-launch.sh` | new |
| `.../session-handoff/scripts/relay-close.sh` | new |
| `private_dot_claude/commands/relay.md` | new: "Use the `session-handoff` skill in **RELAY mode**. Reason: $ARGUMENTS" |
| `private_dot_claude/CLAUDE.md` | "Wait on the deliverable": "report file exists" becomes "a report written by this dispatch (mtime after the dispatch)"; Authorities gains "relay to a new session → `/relay`" |
| `~/.claude/handoff-feedback/gaps.jsonl` | created and seeded (not chezmoi-managed) |

Prototypes for `bg-tasks.py` and `memory-check.py` exist from the research (`open_bg_tasks.py`,
`memory_precheck.py` in the research scripts folder); the implementation starts from them.

### Script contracts

- **`bg-tasks.py [--session <id>] [--transcript <path> ...] [--until-line N] [--json]`**. Finds the transcript
  as `~/.claude/projects/*/<CLAUDE_CODE_SESSION_ID>.jsonl`. A task is open when it was launched in the
  background (Bash `run_in_background`, Monitor) and has no closing `task-notification` (completed, failed or
  killed) and no `TaskStop`. Prints one line per open task: id, start time, description, command. Extra
  `--transcript` paths cover tasks started before a `/clear`.
- **`memory-check.py <memory-dir> [--since <iso>] [--fix] [--json]`**. Measures MEMORY.md as the loader does:
  UTF-16 units after trim and line count, against 25,000 units and 200 lines (constants read from the 2.1.296
  binary: `var Iu="MEMORY.md",dN=200,Moe=25000`). `--since` defaults to the timestamp of the session's first
  transcript record. Reports: headroom; memory files absent from the index (split into written since `--since`
  and older); index lines pointing at missing files. `--fix` applies only the two
  safe fixes, then re-measures. Exit 0 when clean, 1 when debt remains.
- **`relay-check.py checklist --note PATH [--extra-root DIR ...] [--transcript PATH ...]`** creates the relay dir
  `~/.claude/projects/<enc>/relay/<relay-id>/`, writes `checklist.json` into it and prints the dir. Exit 2, and no
  relay dir, when a herdr read fails (an error, an answer that is not JSON, or a listing whose `result.panes` or
  `result.agents` is not a list) or the note is unreadable. `checklist.json`:
  `relay_id`, `created_at`; `predecessor` {`session_id`, `transcript`, `pane_id`, `herdr_name`, `herdr_session`,
  `model` (last main-thread `message.model`), `effort` (`CLAUDE_EFFORT`), `permission_mode`, `pid`
  (`CLAUDE_PID`)}; `repo`; `git` {`head`, `branch`, `dirty`}; `note` {`path`, `sha256`}; `background_tasks`
  (from `bg-tasks.py`); `workers`
  (herdr panes whose cwd is the repo, a worktree of it, or an `--extra-root`, minus this pane: name, pane,
  kind, status, session); `crons`; `recent_prompts` (the last 3 prompts typed into the session, by the owner or
  through herdr, verbatim, with times: the transcript cannot tell the two apart). It refuses (exit 3, no dir)
  while an agent or workflow task is open in the session or git is mid-operation. A `relay-check.py identity`
  subcommand prints the running session's identity (with `pid` from `CLAUDE_PID`) for the successor's receipt.
- **`relay-check.py compare <relay-dir>`** validates `receipt.json` against `checklist.json`. Fails on: model,
  effort or permission mode differ; note path or sha256 differ; a checklist task id missing from the receipt,
  marked re-armed with no live process carrying its marker, or dropped without a reason; a worker missing, or
  with neither a live waiter marker nor a reason (status equality is not checked: a worker can finish between
  the successor's look and the compare); a cron not accounted for; open questions or disagreements; drift
  reported without an explanation; a `relay_id` that is not this relay's; a `tier` other than `clean` or
  `drift`. Every task and worker marker must start with `relay-<relay-id>-w` for this relay's id, so a live
  waiter of an earlier relay (the predecessor's own, alive until the hand-over) or a generic string such
  as `while` covers nothing. A marker of this relay is satisfied by the file `<relay-dir>/fired/<marker>`, which
  the successor's waiters leave when they fire between arming and the compare, or by a live process carrying it
  that descends from the receipt's `successor.pid` (one `ps` snapshot, ppid chains walked): a `run_in_background`
  task does, while a `nohup`/`&` waiter is re-parented away, cannot wake the successor, and FAILs as detached; a
  receipt without `successor.pid` FAILs. A fired file never rescues a marker with another prefix. Prints PASS or
  one line per failure; exit 0 or 1.
- **`relay-launch.sh <relay-dir>`**: `herdr pane split $HERDR_PANE_ID --direction down --cwd <repo>
  --no-focus`; `herdr agent start lead-<project>-next --kind claude --pane <new> -- --model <m> --effort <e>
  [--dangerously-skip-permissions] [--session-id <uuid>]`; retries the start once (a start answered
  `agent_pane_busy`, the new pane's shell not ready yet, is retried every second for up to 15 s before it counts
  as an attempt); asserts the banner shows the model and effort; `herdr agent prompt ... "/pickup relay=<dir>"`;
  writes `launch.json` (pane, name, session id, time). On a second failure writes `failed.json` and exits 1. `<project>` is the repo
  basename, lowercased, non-alphanumerics to `-`, cut so the name fits herdr's 32-character limit; an override
  argument exists.
- **`relay-close.sh <relay-dir>`** (run by the successor): refuses unless the predecessor's pane reports
  `idle` or `done`, its transcript has no owner-typed prompt after `handover.md`'s mtime, and the pane's
  `agent_session` is still the predecessor's session. Then `herdr pane close`, confirms `agent_not_found` and
  that the pid is gone, renames the successor `lead-<project>`, writes `closed.json` and
  `~/.claude/projects/<enc>/relay/lead.json` (current lead's session, pane, since). A refusal says which check
  failed and leaves the pane open.

### File formats (relay dir)

- `receipt.json` (successor): `relay_id`; `successor` identity (same fields as the predecessor's); `note`
  {`path`, `sha256`}; `tier` (`clean` or `drift`) and `drift` items; `tasks` [{`id`, `action`: `rearmed` |
  `watching-exit-file` | `drop`, `marker`, `reason`}]; `workers` [{`pane_id`, `status_seen`, `waiter_marker`,
  `reason`}]; `crons` [{`id`, `action`, `reason`}]; `disagreements`; `questions`; `gaps`. A **question** asks
  for something the note does not say. A **disagreement** says the note or `checklist.json` is wrong about
  reality: it quotes the claim and the evidence against it (drift, by contrast, is reality moving on after the
  save, a claim that was true when written). The old lead answers both under the note's `## Relay Q&A`; the
  successor removes each from the receipt once an answer settles it, moving anything only informational to
  `gaps`. Both block the compare while non-empty; `gaps` do not.
- `handover.md` (old lead): the standing instruction (quoted, with its time), deliveries that arrived during
  the relay, late facts for memory.
- `launch.json`, `closed.json` (scripts); `failed.json` (`relay-launch.sh`, or the old lead). `launch.json` holds
  the successor's `pane_id`, `name` and `session_id`, which step 6's identity check compares. `failed.json` holds
  `stage` (`launch` | `receipt` | `check` | `handover`), `reason`, `attempts` and `at`; after a failed receipt,
  check or hand-over send also `successor_closed`, with `successor_close_reason` when it is false. Piece 2's hook
  reads it to back off; a `closed.json` written later in the same relay dir supersedes it.
- `fix-<round>` (old lead): touched when a fix round's request is sent; the anchor of that round's wait.
- `gaps.jsonl` line: `date`, `project`, `relay_id`, `predecessor_session`, `successor_session`, `missing`,
  `cost`, `section` (template section or `none`), `kind` (`no-slot` | `slot-empty` | `stale-or-wrong` |
  `check-cannot-fail` | `protocol`), `severity` (`serious` | `minor`), `fixed_by`.

## Failure handling

| Situation | Behaviour |
|---|---|
| Outside herdr | `/relay` refuses; manual `/handoff`, `/clear`, `/pickup` |
| Subagent or workflow running in the lead, attached work running, git mid-operation | wait; the relay does not start |
| Successor fails to start | one retry; then `failed.json`, old lead keeps driving and tells the owner |
| Successor writes no usable receipt (dies, stays `blocked` for about 2 minutes, or 20 minutes pass; 15 per fix round) | `failed.json` `"stage": "receipt"`; the old lead closes the successor pane it launched if that pane still hosts it, records `successor_closed`, keeps the lead and tells the owner |
| Check fails | up to 2 fix rounds, then `failed.json`; the old lead closes the successor pane it launched if that pane still hosts it, records `successor_closed`, keeps the lead and asks the owner |
| A herdr read hangs inside a wait loop | the read times out after 10 s and counts as `unread`; the loop still ends at its bound |
| The hand-over line cannot be sent (fails twice) | the old lead keeps its waiters and the record, stays frozen, writes `failed.json` `"stage": "handover"` and tells the owner; the successor holds a valid receipt but not the lead; the owner decides |
| Worker delivers during the relay | old lead notes it in `handover.md`; successor's waiter fires on it |
| Worker blocked on a question | answered before the freeze if within its brief; otherwise in the note |
| Owner types into the old pane after the hand-over | old lead points to the new pane; `relay-close.sh` refuses; successor tells the owner |
| Successor dies after the hand-over | the old pane is still open (it is only closed by the successor); owner resumes it |
| Memory index over the cap | relay proceeds; debt in the note; successor's first job |

## Testing

Unit tests use synthetic fixtures (no real transcripts or memory in this repo) and a stub `herdr` on `PATH`.
Each test must be able to fail:

1. `bg-tasks.py` finds exactly the open tasks in a fixture that includes a completed, a killed and a
   `TaskStop`ped task (removing the `TaskStop` handling must make it fail).
2. `memory-check.py` reports debt on a fixture over 25,000 units; `--fix` adds a pointer for a session-written
   orphan and removes a dead line; an older orphan is reported, not fixed.
3. A test greps the installed Claude Code binary for the loader constants and fails if they changed.
4. `relay-check.py compare` fails on a reconstruction of today's relay (the dropped disk watcher), passes on a
   corrected receipt, fails on an identity mismatch.
5. `relay-close.sh` refuses (stub herdr) when the predecessor is working, when an owner prompt follows the
   hand-over, and when the pane hosts another session; closes and renames when all checks pass.
6. `relay-launch.sh` (stub herdr) passes the model, effort and permission flag; writes `failed.json` after a
   second start failure.

Validation against the real data, run locally and reported, not committed: `bg-tasks.py` on the a1a1a1a1
transcript cut at line 3076 lists exactly b4tcyp53v, b3p5xo0sv and biqbady42 (the three that ended `killed`);
`memory-check.py` on a copy of the Alpha memory dir.

**Definition of done:** an end-to-end relay in a scratch herdr tab. A small lead with one fake worker pane (a
shell script that writes its deliverable after a delay) and one background waiter runs `/relay`. The successor
re-arms the waiter, the check passes, the old pane is closed by the successor, the successor is renamed, and
the successor's waiter picks up the deliverable. Then the same run with a deliberately dropped task must fail
the check and leave the old lead driving.

## Verify early (unconfirmed)

- Verified 2026-10-12 (herdr 0.9.2-preview.2026-09-29): `herdr agent start ... -- --session-id <uuid>` creates the
  session under that id. `agent_session.value` matched in the `agent start` and `herdr agent get` JSON, and
  `ls ~/.claude/projects/*/<uuid>.jsonl` found exactly one transcript, `<enc-cwd>/<uuid>.jsonl`. The file appears
  only after the first prompt; right after `agent start` the project dir did not exist yet.
- Verified 2026-10-12: `herdr agent rename <pane> <name>` fails while a live agent in another tab of the same
  workspace holds `<name>` (exit 1, error `agent_name_taken`, which names the holder's pane and tab). Renaming the
  same pane to a free name succeeds, so `rename` accepts a pane id as target. Not tested across workspaces.
- Permission mode: from the transcript's `permission-mode` record, else the owner's `~/.claude/settings.json`; repo
  settings never grant bypass (security review, 2026-10-12).
- Transcript formats for background launches, task notifications, `TaskStop`, and owner-typed prompts versus
  injected ones, on the installed build.

## Out of scope

- Piece 2: the 50% hook, the context meter (must read the last `usage.iterations` entry of type `message`;
  advisor turns double the top-level figure), and back-off on `failed.json`.
- Restructuring Alpha's MEMORY.md (moving closed pointers to an unloaded archive): a project decision.
- A Claude Code mod; an in-place relay for sessions outside herdr.
- Follow-ups in Alpha memory: update `context-handoff-at-fifty-percent.md` and
  `successor-pane-handover-recipe.md` once `/relay` exists.

# Relay protocol

A relay hands the lead from this session (the **predecessor**) to a new Claude
session in a new herdr pane (the **successor**), which picks up, takes over and
closes the predecessor. Scripts own facts and mechanics; the model owns
judgement. The scripts are in `~/.claude/skills/session-handoff/scripts/`.

Every relay has a **relay dir**, `~/.claude/projects/<project>/relay/<relay-id>/`,
beside `memory/` and never inside it, so nothing here loads or counts against
the MEMORY.md cap. `<relay-id>` is the dir's basename (UTC, e.g.
`20261013T091500Z`, with `-2`, `-3` on a collision) and `checklist.json`'s
`relay_id`. Files: `checklist.json` and `launch.json` (scripts, for the
predecessor), `receipt.json` (successor), `fired/<marker>` (left by the
successor's waiters when they fire), `handover.md` (predecessor),
`closed.json` (script, for the successor), `failed.json` (a script or the
predecessor, on failure). The project's current lead is recorded in
`~/.claude/projects/<project>/relay/lead.json`.

## Predecessor

1. **Refuse outside herdr.** `HERDR_ENV` unset: say so and use `/handoff`,
   `/clear`, `/pickup`.
2. **Preconditions.** Wait until no subagent or workflow runs inside this
   session (they die with it), git is not mid-merge, rebase, cherry-pick or
   revert, and attached work has finished. `relay-check.py checklist` refuses
   (exit 3, no relay dir) on the first two and names them. If a worker is
   `blocked` on a question you can answer within its brief, answer it now;
   otherwise record it in the note.
3. **Freeze.** From here: no new dispatch, merge, spend or score. Note
   arrivals (deliveries, notifications) for `handover.md`; do not act on them.
4. **SAVE** (SKILL.md), including the memory check. From the launch on you
   write no memory: late facts go in `handover.md`.
5. **Checklist.**
   `python3 -I ~/.claude/skills/session-handoff/scripts/relay-check.py checklist --note <note path>`
   (add `--extra-root <dir>` for each dir outside the repo where this front
   launched panes, `--transcript <earlier.jsonl>` for tasks started before a
   `/clear`). Exit 0 prints the relay dir as an absolute path: pass it on
   exactly as printed. It records your identity (model, effort, permission
   mode, pid, pane, herdr session), git, the note's sha256, open background
   tasks, session crons, the worker panes and your last 3 prompts. Like
   `bg-tasks.py` it reads only the task ids Claude Code records for Bash,
   Monitor, Workflow and Agent: an MCP tool the harness moved to the background
   ("MCP tool … moved to the background as task <id>") is not listed, so record
   it in the note by hand. Exit 3: a blocker from step 2. Exit 2: a herdr read
   failed or the note is unreadable. Neither creates a relay dir: fix the cause
   and run it again.
6. **Launch.**
   `bash ~/.claude/skills/session-handoff/scripts/relay-launch.sh <relay-dir>`,
   through the Bash tool with `timeout: 300000` (two 90 s start attempts plus
   clean-up outlast the default). It splits this pane down, starts
   `lead-<project>-next` with your model and effort, checks that the new pane's
   banner shows both, sends `/pickup relay=<relay-dir>`, writes `launch.json`
   and prints the new pane id (exit 0).
   - **Permission mode.** It adds `--dangerously-skip-permissions` only when
     the checklist's `permission_mode` is `bypassPermissions`, which
     `checklist` takes from your transcript's permission-mode record, else from
     the owner's own `~/.claude/settings.json`. A repo's
     `.claude/settings*.json` never grants bypass. No other mode (acceptEdits,
     plan) is passed on: the successor starts in the owner's default mode, and
     where that differs from yours, compare FAILs on identity. No fix round
     cures that: stop this relay (step 8's failure branch) and ask the owner.
   - **Exit 1**: the launch failed (pane split failed, two failed starts, the
     banner unreadable or without the model or effort, `/pickup` not sent, or
     the script was killed: reason `interrupted`). `failed.json` is written
     and the new pane closed. Keep driving and tell the owner.
   - **Exit 2**: not inside herdr, no `checklist.json`, or a checklist that
     names no model. Nothing was started.
7. **Wait on the receipt**, never on the screen: a background until-loop on
   `[ <relay-dir>/receipt.json -nt <relay-dir>/launch.json ]` AND
   `herdr agent get <name>` (the name in `launch.json`,
   `lead-<project>-next`) not reporting `working`. A failed `herdr agent get`
   does not count as "not working".
8. **Check.**
   `python3 -I ~/.claude/skills/session-handoff/scripts/relay-check.py compare <relay-dir>`.
   - Exit 0 prints `PASS`: go to step 9.
   - Exit 1 prints one `FAIL` line per problem. Fix what each line names:
     correct the note; answer the successor's questions and explain drift
     under the note's `## Relay Q&A`. compare hashes the note on disk every
     time, so after any edit to the note the successor must re-read it and
     record the new sha256. Then `touch <relay-dir>/fix-<round>` and tell the
     successor (`herdr agent prompt <name> "…"`): "Re-read <items> in the note
     and rewrite <relay-dir>/receipt.json." Wait as in step 7 with
     `fix-<round>` in place of `launch.json` (the receipt is already newer
     than `launch.json`, so that condition would pass at once), then compare
     again. At most **2** fix rounds.
   - Still failing after 2 rounds, an identity FAIL, or a question only the
     owner can answer: write `<relay-dir>/failed.json`
     (`{"stage": "check", "reason": "<the FAIL lines>", "attempts": <rounds>, "at": "<UTC ISO time>"}`),
     keep the lead, tell the owner. Close nothing, and tell the owner that the
     successor's pane <pane> is still open and holds the name in `launch.json`
     (a later relay likely cannot start a successor under that name while it
     lives).
9. **Hand-over** (make before break). The compare PASS already proved that
   every checklist task and worker is covered by a successor waiter, live or
   fired (`<relay-dir>/fired/<marker>`): do not re-check them. Stop your own
   waiters (`TaskStop` each) and delete your session crons (`CronDelete` each:
   the successor re-armed the ones that still apply, and a cron left here
   fires a prompt into this pane). Write `<relay-dir>/handover.md` (format
   below) once and completely, then send the successor exactly
   `Read <relay-dir>/handover.md; you have the lead.` and end your turn. Never
   edit `handover.md` after sending: `relay-close.sh` dates "a prompt after the
   hand-over" from its mtime. Anything you learn later goes to the owner, not
   into that file.
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

`<dir>` is the relay dir; `<relay-id>` is its basename, also
`checklist.json`'s `relay_id`.

1. **Normal RESUME**, reality outranking the note, plus:
   - **Read-only until the hand-over**: no dispatch, merge, spend or score; do
     not stamp the note.
   - The note is the one `checklist.json` names (`note.path`), not whichever
     note the sweep finds newest: compare FAILs on any other path. A newer note
     or an unconsumed `EMERGENCY-*.md` the sweep finds is drift.
   - Read `<dir>/checklist.json` and verify it against reality: git, each
     worker (`herdr agent get`, read-only), deliverables, background tasks.
   - For each open background task you keep and each worker, arm your own
     waiter, even while the predecessor's waiter for the same item still runs
     (it stops them at the hand-over). Each is a Bash `run_in_background` loop
     of this shape:

         : relay-<relay-id>-w<k>; until <condition>; do sleep 30; done; mkdir -p <dir>/fired && touch <dir>/fired/relay-<relay-id>-w<k>

     The leading marker is how compare finds the live waiter; the closing
     `touch` leaves `<dir>/fired/<marker>` when the waiter fires before the
     compare (a worker delivering mid-relay), and compare accepts that too.
     `<relay-id>` is THIS relay's id: compare FAILs any marker that does not
     start with `relay-<relay-id>-w`, so never copy a marker from the
     predecessor's waiter commands (from an earlier relay they carry the old
     id). Keep the `until …; do sleep N; done` loop: when a single command
     follows the marker, bash 5.1 and later exec it and the marker leaves the
     process list. Conditions check a report written by this dispatch (mtime
     after the dispatch), never bare existence; a work task's waiter watches
     its exit-code file. Re-arm the checklist's crons that still apply (a
     one-shot whose time has passed is dropped, with that reason).
   - Write `<dir>/receipt.json` (format below). Its `successor` block is the
     output of
     `python3 -I ~/.claude/skills/session-handoff/scripts/relay-check.py identity`.
     What you need the predecessor to answer goes in `questions`; a gap you
     found and filled yourself goes in `gaps` (`references/feedback.md`).
     `questions` block the compare; `gaps` do not.
   - End your turn with a summary addressed to the predecessor. It stays in
     your pane: files are the channel, and the predecessor waits on
     `receipt.json`. Never type into the predecessor's pane: after the
     hand-over, any prompt there makes `relay-close.sh` refuse.
   - Told to re-read items: re-read them (and re-hash the note if it changed),
     rewrite `receipt.json`, end your turn again.
2. **On "you have the lead":** read `handover.md`, write its late facts to
   memory (then `memory-check.py --fix` as in SAVE), stamp the note `resumed`.
   If the note's Memory section carries debt, fix it first (read MEMORY.md in
   full: the part past the cap never loaded into your context).
3. **Close the predecessor:**
   `bash ~/.claude/skills/session-handoff/scripts/relay-close.sh <dir>`.
   It refuses (exit 1, pane left open, the failed check named) unless
   `handover.md` exists, the predecessor's pane reports `idle` or `done`, the
   pane still hosts the herdr session the checklist recorded, and no prompt
   reached the predecessor after `handover.md` was written (a prompt it cannot
   date counts as after). When herdr recorded no session for the predecessor's
   pane (a lead started by hand), it also requires the checklist's predecessor
   pid to be a live `claude` process. Then it closes the pane, waits up to
   `RELAY_CLOSE_WAIT` seconds (default 10) for the pane and the pid to be gone
   (exit 1 if either outlives that), renames you `lead-<project>` and writes
   `closed.json` and `relay/lead.json` (exit 1 if it cannot). Exit 0: closed;
   if the rename failed, its warning names the name you kept. Exit 2, before
   any close: not inside herdr, `CLAUDE_CODE_SESSION_ID` unset, no checklist,
   or a usage error.
   - Refused because the pane is `working`: the predecessor has not ended its
     turn yet. Wait a minute and run it again.
   - Refused because a prompt reached the old pane: tell the owner; the pane
     stays open for them.
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
      "workers": [{"pane_id": "<checklist pane id>", "status_seen": "<status>", "waiter_marker": "relay-<id>-w<k>",
                   "reason": "<required when there is no waiter_marker>"}],
      "crons": [{"id": "<checklist cron id>", "action": "rearmed | drop", "reason": "<required for drop>"}],
      "disagreements": [],
      "questions": [],
      "gaps": []
    }

`compare` passes only when all of these hold:
- `relay_id` is this relay's, and `tier` is `clean` or `drift`;
- the successor's model, effort and permission mode equal the predecessor's;
- `note.path` is the checklist's and `note.sha256` matches the note on disk now;
- every checklist task is `rearmed` or `watching-exit-file` with a `marker`
  of this relay that is live or fired, or `drop` with a reason;
- every checklist worker, matched by `pane_id`, has such a `waiter_marker` or
  a reason (its status is not compared: a worker can finish between your look
  and the compare);
- every checklist cron is `rearmed`, or `drop` with a reason;
- `questions` and `disagreements` are empty, and every `drift` item has an
  explanation.

`tier` is `drift` when you found any; each drift item needs the predecessor's
explanation (in the note's `## Relay Q&A`, copied into the receipt) before it
passes.

## Failure table

| Situation | Behaviour |
|---|---|
| Outside herdr | `/relay` refuses; manual `/handoff`, `/clear`, `/pickup` |
| Subagent or workflow running, attached work running, git mid-operation | wait; the relay does not start (`checklist` exit 3) |
| A herdr read fails or the note is unreadable at the checklist | `checklist` exit 2, no relay dir; fix the cause and run it again |
| Successor fails to start | one retry; then `failed.json`, the new pane closed, the predecessor keeps driving and tells the owner |
| `relay-launch.sh` killed (Bash timeout, Ctrl-C) | it closes the pane it made and writes `failed.json` with reason `interrupted`; the predecessor keeps driving and tells the owner |
| Identity mismatch (a mode other than bypass is not passed on) | no fix round; `failed.json`, ask the owner; nothing closed |
| Check fails | up to 2 fix rounds, then `failed.json`, ask the owner; nothing closed |
| Worker delivers during the relay | the predecessor notes it in `handover.md`; the successor's waiter fires on it (`fired/<marker>`) |
| Worker blocked on a question | answered before the freeze if within its brief; otherwise in the note |
| Owner types into the old pane after the hand-over | the predecessor points to the new pane; `relay-close.sh` refuses; the successor tells the owner |
| Successor dies after the hand-over | the old pane is still open (only the successor closes it); the owner resumes it |
| Memory index over the cap | the relay proceeds; debt in the note; the successor's first job |

## Script exit codes

| Script | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| `relay-check.py checklist` | relay dir printed | not run inside a Claude session (`CLAUDE_CODE_SESSION_ID` unset or its transcript not found) | a herdr read failed inside herdr, or the note is unreadable; no relay dir | a blocker (agent or workflow running in this session, git mid-operation); no relay dir |
| `relay-check.py identity` | identity JSON printed | not run inside a Claude session | | |
| `relay-check.py compare` | `PASS` | `FAIL` lines | | |
| `relay-check.py quiet` | no prompt after `handover.md` | a prompt reached the predecessor after `handover.md` (one it cannot date counts) | no `handover.md` yet | |
| `relay-launch.sh` | launched; prints the new pane id | failed: pane closed, `failed.json` written (without a relay-dir argument: a usage error, nothing written) | nothing started: not inside herdr, no checklist, or the checklist names no model | |
| `relay-close.sh` | closed and renamed (a failed rename is reported, the kept name recorded) | refused, pane left open; or the pane or pid outlived the close; or the records could not be written | before any close: not inside herdr, `CLAUDE_CODE_SESSION_ID` unset, no checklist, or a usage error | |

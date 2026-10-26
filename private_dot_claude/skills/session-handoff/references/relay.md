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
   **Confirm by hand that no teammate runs before `/relay`.** The checklist
   cannot see teammates: their transcripts record no per-teammate end. The
   relay gate sees running teammates in the hook's live `background_tasks`.
3. **Freeze.** From here: no new dispatch, merge, spend or score. Note
   arrivals (deliveries, notifications) for `handover.md`; do not act on them.
4. **SAVE** (SKILL.md), including the memory check. From the memory check
   on (SAVE step 2) you write no memory; late facts go in `handover.md`.
5. **Checklist.**
   `python3 -I ~/.claude/skills/session-handoff/scripts/relay-check.py checklist --note <note path>`
   (add `--git-repo <dir>` when this front's repo is not the session cwd's,
   such as a worktree or another checkout: without it git state and the
   mid-operation check read the cwd, and a cwd that is no repo records no
   git at all; `--extra-root <dir>` for each dir outside the repo where this
   front launched panes; `--transcript <earlier.jsonl>` for tasks started
   before a `/clear`). Exit 0 prints the relay dir as an absolute path: pass it on
   exactly as printed. It records your identity (model, effort, permission
   mode, pid, pane, herdr session), git, the note's sha256, open background
   tasks, session crons, the herd (`"version": 2`: from the herd record
   joined with live panes, its `workers` by launch id with their latest
   dispatch, `lost` launches with no live pane, and `unclassified` live panes in
   scope, each flagged `looks_like_worker` or not) and your last 3 prompts. Like
   `bg-tasks.py` it reads only the task ids Claude Code records for Bash,
   Monitor, Workflow and Agent (`async_launched`, not `teammate_spawned`):
   an MCP tool the harness moved to the background
   ("MCP tool … moved to the background as task <id>") is not listed, so record
   it in the note by hand. Exit 3: a blocker from step 2. Exit 2: a herdr read
   failed, the herd record is unreadable, the note is, or `--git-repo` names
   no git repository. Neither creates a relay dir: fix the cause and run it
   again.
6. **Launch.**
   `bash ~/.claude/skills/session-handoff/scripts/relay-launch.sh <relay-dir>`,
   through the Bash tool with `timeout: 300000` (two 90 s start attempts,
   their busy-pane retries and clean-up outlast the default). It splits this
   pane down, starts `lead-<project>-next` with your model and effort, checks
   that the new pane's banner shows both, sends `/pickup relay=<relay-dir>`,
   writes `launch.json` and prints the new pane id (exit 0). A start that
   herdr answers with `agent_pane_busy` (the new pane's shell is not ready
   yet) is retried every second for up to 15 s before it counts as an attempt.
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
7. **Wait on the receipt**, never on the screen and never without a bound.
   Run this through the Bash tool with `run_in_background` (the tool blocks a
   foreground sleep). `<successor name>` is the `name` in `launch.json`
   (`lead-<project>-next`):

       anchor=<relay-dir>/launch.json receipt=<relay-dir>/receipt.json name=<successor name> n=0
       deadline=$(( $(python3 -I -c 'import os, sys; print(int(os.path.getmtime(sys.argv[1])))' "$anchor") + 1200 ))
       status_of() { python3 -I -c 'import json, subprocess, sys; r = subprocess.run(["herdr", "agent", "get", sys.argv[1]], capture_output=True, text=True, timeout=10); print(("gone" if "agent_not_found" in r.stderr else "unread") if r.returncode else ((json.loads(r.stdout).get("result") or {}).get("agent") or {}).get("agent_status") or "unread")' "$1" 2>/dev/null || echo unread; }
       until st=$(status_of "$name")
         case $st in blocked) n=$((n + 1)) ;; *) n=0 ;; esac
         case $st in idle|done) [ "$receipt" -nt "$anchor" ] ;; gone) true ;; blocked) [ "$n" -ge 8 ] ;; *) false ;; esac \
           || [ "$(date +%s)" -ge "$deadline" ]
       do sleep 15; done
       echo "successor=$st receipt=$([ "$receipt" -nt "$anchor" ] && echo new || echo none)"

   `status_of <agent>` prints the `agent_status` field of
   `herdr agent get <agent>`, `gone` when herdr answers `agent_not_found`, and
   `unread` for any other failed read. Each read is bounded: `timeout=10` stops
   a hung `herdr agent get` after 10 s, and any exception (that timeout, herdr
   missing, an answer that is not JSON) exits python non-zero with nothing
   printed, so `|| echo unread` reports it. A poll never outlasts 10 s, and the
   loop ends within about 25 s (one read, one sleep) of its deadline even while
   herdr hangs. The loop ends on the first of:
   - the receipt is newer than the anchor and the successor is `idle` or
     `done` (`working`, `unknown`, `unread` and any other status keep it
     waiting);
   - the successor is gone (`agent_not_found`);
   - the successor stays `blocked` for 8 consecutive polls, about 2 minutes
     (any other status resets the count). A successor waiting on an approval
     shows `blocked` while the owner answers (writing `receipt.json` under
     `~/.claude` can prompt in the default mode, and any other approval
     prompt blocks it the same way), and it must not be failed and closed at
     the first poll;
   - 20 minutes past the anchor's mtime (`+ 1200`).

   Its last line reads `successor=<status> receipt=<new|none>`.
   `receipt=new` with `successor=idle` or `successor=done`: go to step 8.
   Anything else: step 8's failure branch with `"stage": "receipt"` and that
   line as the reason.
8. **Check.**
   `python3 -I ~/.claude/skills/session-handoff/scripts/relay-check.py compare <relay-dir>`.
   - Exit 0 prints `PASS`: go to step 9.
   - Exit 1 prints one `FAIL` line per problem. Fix what each line names:
     correct the note; under the note's `## Relay Q&A`, answer the
     successor's questions, answer each disagreement (correct the note, or
     show with your evidence why it stands) and explain drift. compare hashes
     the note on disk every time, so after any edit to the note the successor
     must re-read it and record the new sha256. Then
     `touch <relay-dir>/fix-<round>` and tell the successor
     (`herdr agent prompt <name> "…"`): "Re-read <items> in the note
     and rewrite <relay-dir>/receipt.json." Wait with step 7's loop, with
     `anchor=<relay-dir>/fix-<round>` and `+ 900` (15 minutes) in place of
     `+ 1200` (the receipt is already newer than `launch.json`, so that anchor
     would pass at once). Read its last line as in step 7, then compare again.
     At most **2** fix rounds.
   - Still failing after 2 rounds, an identity FAIL, a question only the
     owner can answer, or a receipt wait (step 7 or a fix round) that ended
     without a usable receipt: the relay stops. The successor never received
     the lead and stayed read-only, so close the pane you launched for it,
     once that pane is shown to still host it; left alive, its
     `lead-<project>-next` name would block the next relay's launch
     (`agent_name_taken`).
     1. Write `<relay-dir>/failed.json`:
        `{"stage": "check", "reason": "<the FAIL lines>", "attempts": <rounds>, "at": "<UTC ISO time>"}`,
        or after a receipt wait
        `{"stage": "receipt", "reason": "<the waiter's last line>", "attempts": <rounds>, "at": "<UTC ISO time>"}`.
     2. Check the pane's session before closing it. `<pane>` is the
        `pane_id` in `launch.json`, but pane ids can change (a herdr restore
        renumbers them), and after a `successor=gone` wait the recorded id is
        least trustworthy: it may now hold a worker. Run
        `herdr agent get <pane>`. The pane still hosts the successor only when
        the answer's `agent_session.value` equals `launch.json`'s
        `session_id`, or its `name` equals `launch.json`'s `name` (a
        non-empty value either way).
        - It does: `herdr pane close <pane>`, then confirm it:
          `herdr agent get <pane>` must fail with `agent_not_found` (herdr
          reports it on stderr; allow about 10 s, as `relay-close.sh` does).
        - Anything else (another session and another name, `agent_not_found`,
          a failed read): do not close the pane.
     3. Add `"successor_closed": true` to `failed.json` when the close was
        confirmed. Otherwise add `"successor_closed": false` and
        `"successor_close_reason"`: what the pane hosts instead (its session
        and name), herdr's error, or that the close was not confirmed.
     4. Keep the lead and tell the owner, naming the pane if it is still open
        and, when you did not close it, why. If `herdr agent get <name>`
        (`launch.json`'s `name`) still finds the successor, name its pane:
        the owner closes it. `receipt.json` and `failed.json` stay in the
        relay dir for inspection.

     This matches a failed launch, where `relay-launch.sh` closes the pane it
     created (that path does not confirm the close or record it in
     `failed.json`). Your own pane is never closed on a failed relay.
9. **Hand-over** (make before break). The compare PASS already proved that
   every checklist task and worker is covered by a successor waiter, live
   under the successor's process or fired (`<relay-dir>/fired/<marker>`),
   and that the successor re-armed the crons that still apply: do not
   re-check them. In this order:
   1. Delete your session crons (`CronDelete` each). They go first: a cron
      left here fires a prompt into this pane, and one that fires after
      `handover.md` is written is a prompt after the hand-over, so
      `relay-close.sh` would refuse to close this pane.
   2. Write `<relay-dir>/handover.md` (format below) once and completely.
      Never edit it after sending: `relay-close.sh` dates "a prompt after the
      hand-over" from its mtime. Anything you learn later goes to the owner,
      not into that file.
   3. Send the successor exactly `Read <relay-dir>/handover.md; you have the lead.`
      with `herdr agent prompt <name> "…"` and check its exit status. Not 0:
      send it once more.
   4. Sent (exit 0): stop your own waiters (`TaskStop` each) and end your
      turn. They stop only now, after the confirmed send, so a failed send
      never leaves the lead with no session holding it. For those few seconds
      they overlap the successor's waiters; that is harmless because you are
      frozen: a waiter only waits, and you act on nothing it reports.
   5. Not sent after the second try: the successor holds a valid receipt
      (compare PASS) but never got the lead, and stays read-only. Do not end
      silently and do not stop your waiters: this pane keeps the lead's
      record (the note, your waiters) and stays frozen. Write
      `<relay-dir>/failed.json`:
      `{"stage": "handover", "reason": "<herdr's error>", "attempts": 2, "at": "<UTC ISO time>", "successor_closed": false, "successor_close_reason": "it holds a valid receipt; the owner decides"}`.
      Tell the owner that the successor (`<name>`, pane `<pane>`) holds a
      valid receipt but never got the lead and that this pane keeps the
      record. The owner decides: send the line to the successor themselves
      (it then closes this pane with `relay-close.sh`, and its `closed.json`
      supersedes this `failed.json`), or have this session resume and close
      the successor.
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
    <a task that samples, spends or writes while it waits and is still attached:
    its command verbatim, for the successor to restart after the hand-over; or
    `none`. SAVE detaches this before the relay; the line is the fallback>

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
     (it stops them at the hand-over). Arm every waiter with the Bash tool's
     `run_in_background`, never `nohup` or `&`: only a `run_in_background`
     task wakes this session when it ends. A detached waiter fires, writes its
     fired file and wakes no one, so compare FAILs a live waiter whose process
     does not descend from the `pid` in your receipt's `successor` block. Each
     waiter is a loop of this shape:

         : relay-<relay-id>-w<k>; until <condition>; do sleep 30; done; mkdir -p <dir>/fired && touch <dir>/fired/relay-<relay-id>-w<k>

     A task that does work while it waits (samples, spends or writes) and is
     still attached is not mirrored: a second copy doubles the work during the
     read-only phase. Arm a passive waiter on its effect (the line it appends,
     or no process running its script), record it as `rearmed` with a `gaps`
     line naming the task, and restart the task after the hand-over from the
     command under Arrived during the relay. SAVE should have detached it.

     For a version-2 checklist's workers, one waiter covers them all, and
     every worker's `waiter_marker` names it:

         python3 -I ~/.claude/skills/session-handoff/scripts/herd.py wait --marker relay-<relay-id>-w<k> --fired-dir <dir>/fired

     It exits on the first worker event (it also fires when the predecessor's
     waiter recorded the event first) and touches its fired file. A worker
     with nothing to wait on (no dispatch yet, or its latest dispatch already
     reported) gets a `reason` in the receipt, not a marker: `herd.py wait`
     exits 1 when nothing is pending.

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
     `python3 -I ~/.claude/skills/session-handoff/scripts/relay-check.py identity`,
     including your `pid` (compare FAILs a receipt without one).
     What you need the predecessor to answer goes in `questions`; a claim of
     the note or `checklist.json` that your evidence contradicts goes in
     `disagreements` (both defined under receipt.json below); a gap you found
     and filled yourself goes in `gaps` (`references/feedback.md`).
     `questions` and `disagreements` block the compare; `gaps` do not.
   - End your turn with a summary addressed to the predecessor. It stays in
     your pane: files are the channel, and the predecessor waits on
     `receipt.json`. Never type into the predecessor's pane: after the
     hand-over, any prompt there makes `relay-close.sh` refuse.
   - Told to re-read items: re-read them (and re-hash the note if it
     changed). Remove each answered entry from `questions` and
     `disagreements` (compare passes only when both are empty), move anything
     informational to `gaps`, and fill the `explanation` of each drift item
     the predecessor explained. A disagreement the answer does not settle
     stays, with what still contradicts it: after 2 fix rounds the relay
     stops and the owner decides. Rewrite `receipt.json`, end your turn
     again.
2. **On "you have the lead":** read `handover.md`, write its late facts to
   memory (then `memory-check.py --fix` as in SAVE), stamp the note `resumed`.
   Restart each still-attached work-while-waiting task from the command
   `handover.md` names; its passive waiter is already armed. A second copy of
   the line (the predecessor retries a send it could not confirm) changes nothing.
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
     turn yet. Wait for it to leave `working` with this loop, run through the
     Bash tool with `run_in_background`; `<pane>` is the checklist's
     `predecessor.pane_id`, and `status_of` is Predecessor step 7's, bounded
     the same way:

         pane=<pane> deadline=$(( $(date +%s) + 600 ))
         status_of() { python3 -I -c 'import json, subprocess, sys; r = subprocess.run(["herdr", "agent", "get", sys.argv[1]], capture_output=True, text=True, timeout=10); print(("gone" if "agent_not_found" in r.stderr else "unread") if r.returncode else ((json.loads(r.stdout).get("result") or {}).get("agent") or {}).get("agent_status") or "unread")' "$1" 2>/dev/null || echo unread; }
         until st=$(status_of "$pane")
           case $st in working|unread) false ;; *) true ;; esac || [ "$(date +%s)" -ge "$deadline" ]
         do sleep 15; done
         echo "predecessor=$st"

     `unread` keeps it waiting: a failed or hung read says nothing about the
     turn. It ends when the pane shows any other status or 10 minutes pass
     (`+ 600`). Then rerun `relay-close.sh`, which reads the pane again itself.
     Refused again (still `working` at the bound, or another status such as
     `blocked`): tell the owner.
   - Refused because a prompt reached the old pane: tell the owner; the pane
     stays open for them.
   - If it refused and the owner then closes the old pane by hand, the close
     happened but the rename and the records did not. Run
     `herdr agent rename $HERDR_PANE_ID <name>` with the name from
     `python3 -I ~/.claude/skills/session-handoff/scripts/relay-check.py name --repo <repo>`
     (`<repo>` from `checklist.json`), and tell the owner that `closed.json`
     and `lead.json` were not written.
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
      "workers": [{"launch_id": "<checklist launch id>", "status_seen": "<status>", "waiter_marker": "relay-<id>-w<k>",
                   "reason": "<required when there is no waiter_marker>"}],
      "lost": [{"launch_id": "<checklist launch id>", "reason": "<what happened to it>"}],
      "unclassified": [{"pane_id": "<checklist pane id>", "reason": "<whose it is>"}],
      "crons": [{"id": "<checklist cron id>", "action": "rearmed | drop", "reason": "<required for drop>"}],
      "disagreements": [],
      "questions": [],
      "gaps": []
    }

`questions` and `disagreements` are lists of strings, one entry each, and
both block the compare until they are empty:
- a **question** asks for something the note does not tell you (what a
  Backlog item means, where a deliverable lands);
- a **disagreement** says the note or `checklist.json` is wrong about reality:
  quote the claim and give the evidence that contradicts it (the note calls a
  branch merged that git shows unmerged; a waiter's command cannot match the
  report the note names). Drift is different: reality moved on after the save
  (a new commit, a worker that finished), and the claim was true when written.

The predecessor answers each question and disagreement under the note's
`## Relay Q&A`. Once an answer settles one, remove it from the receipt;
anything left that is only informational moves to `gaps`. One still
unsettled after 2 fix rounds stops the relay, and the owner decides.

`compare` passes only when all of these hold:
- `relay_id` is this relay's, and `tier` is `clean` or `drift`;
- the successor's model, effort and permission mode equal the predecessor's,
  and its block carries the `pid` of a running process;
- `note.path` is the checklist's and `note.sha256` matches the note on disk now;
- every checklist task is `rearmed` or `watching-exit-file` with a `marker`
  of this relay that is fired, or live in a process that descends from the
  successor's `pid` (a detached waiter fails), or `drop` with a reason;
- every checklist worker, matched by `launch_id`, has such a `waiter_marker` or
  a reason (its status is not compared: a worker can finish between your look
  and the compare); a checklist without `"version": 2` (written before the
  herd record) matches its workers by `pane_id` instead;
- every `lost` launch has a reason, and so has every `unclassified` pane
  flagged `looks_like_worker` (other unclassified panes need nothing);
- every checklist cron is `rearmed`, or `drop` with a reason;
- `questions` and `disagreements` are empty, and every `drift` item has an
  explanation.

`tier` is `drift` when you found any; each drift item needs the predecessor's
explanation (in the note's `## Relay Q&A`, copied into the receipt) before it
passes.

## Automatic relays (the relay gate)

`scripts/relay-gate.py` is a Claude Code hook that has a lead run `/relay` at
50% context. It acts only once the owner registers it in
`~/.claude/settings.json`:

    "Stop":        [{"hooks": [{"type": "command", "command": "python3 -I ~/.claude/skills/session-handoff/scripts/relay-gate.py stop || true", "timeout": 10}]}]
    "PostToolUse": [{"matcher": "*", "hooks": [{"type": "command", "command": "python3 -I ~/.claude/skills/session-handoff/scripts/relay-gate.py tool || true", "timeout": 5}]}]

Keep the `|| true`: without it a missing script exits 2, and a Stop hook that
exits 2 blocks every turn end of every session.

- **Who.** Only a lead: a herdr session whose name starts with `lead-`, or the
  session in `relay/lead.json`. Name a coordinator `lead-<project>` at start
  (`relay-check.py name --repo <repo>` prints the name). One lead per project:
  successors are named `lead-<slug>-next`, then `lead-<slug>`. Workers,
  subagents and teammates are never gated.
- **When.** At the end of a turn at or above 50%, once it is safe: no subagent,
  teammate or workflow running and git not mid-operation. The checklist checks
  agents, workflows and git; the gate also checks any non-shell task still open
  in the hook's live task list, including teammates. A missing list counts as
  not safe. Below 60%, a prompt
  typed in the last 10 minutes defers it. The turn is blocked with "relay-gate:
  context is N% (threshold 50%). Run /relay now, automatic relay attempt k of
  2." and the open background tasks: run `/relay`. If a listed task is long work
  that must finish first, end your turn instead: the gate asks again when a
  listed task closes or the next 10% band starts, at most 3 times per band and
  attempt.
- **Nudge.** After a tool call past 50%, once per band, the gate adds a line: a
  relay is due, finish the current step, start nothing new in-session (no
  subagents, no attached runs), end your turn.
- **Not safe at 60%,** and at each later band, the gate alerts the owner: a herdr
  toast, and the block asks you to load PushNotification (ToolSearch
  `select:PushNotification`) and push the same text. Keep draining (start
  nothing new in-session), end your turn, and do not run `/relay` yet. A lead
  that is safe at 60% or later (it declined at 50%) gets the ask, with an owner
  alert once per band.
- **Back-off.** A failed relay (`failed.json`, or a relay dir with no activity
  for 25 minutes) is retried once, after 30 minutes. A second failure, or one
  that would repeat (an identity mismatch, a taken agent name), stops the gate
  for this session with one owner alert; the owner relays by hand. A hand-over
  failure (`failed.json` beside `handover.md`, whatever stage it names) is never
  retried and takes precedence over that rule: the gate stays silent, because
  the relay protocol has already told the owner. Otherwise a hand-over not
  closed 30 minutes after `handover.md` raises one owner alert. A predecessor
  the owner resumes after a hand-over is never gated again: the owner relays it
  by hand.
- **State.** `relay/gate/<session-id>.json`, for leads only; errors go to
  `relay/gate/errors.log` (`~/.claude/relay-gate-errors.log` when the project
  is unknown). The gate never fails closed: an error is logged and toasted once
  per session, in any session (workers included), and the turn ends normally.

## Failure table

| Situation | Behaviour |
|---|---|
| Outside herdr | `/relay` refuses; manual `/handoff`, `/clear`, `/pickup` |
| Subagent or workflow running, attached work running, git mid-operation | wait; the relay does not start (`checklist` exit 3) |
| A herdr read fails, or the herd record or note is unreadable at the checklist | `checklist` exit 2, no relay dir; fix the cause and run it again |
| Successor fails to start | one retry (a start answered `agent_pane_busy` is retried for up to 15 s before it counts); then `failed.json`, the new pane closed, the predecessor keeps driving and tells the owner |
| `relay-launch.sh` killed (Bash timeout, Ctrl-C) | it closes the pane it made and writes `failed.json` with reason `interrupted`; the predecessor keeps driving and tells the owner |
| No usable receipt: the successor dies, stays `blocked` for about 2 minutes, or 20 minutes pass (15 per fix round) | the waiter ends; `failed.json` with `"stage": "receipt"`, the predecessor closes the successor it launched if its pane still hosts it (`successor_closed`), keeps the lead and tells the owner |
| Identity mismatch (a mode other than bypass is not passed on) | no fix round; `failed.json`, the predecessor closes the successor it launched if its pane still hosts it (`successor_closed`) and asks the owner; its own pane stays open |
| Check fails, or a question only the owner can answer | up to 2 fix rounds, then `failed.json`, the predecessor closes the successor it launched if its pane still hosts it (`successor_closed`) and asks the owner; its own pane stays open; `receipt.json` and `failed.json` stay for inspection |
| Worker delivers during the relay | the predecessor notes it in `handover.md`; the successor's waiter fires on it (`fired/<marker>`) |
| Worker blocked on a question | answered before the freeze if within its brief; otherwise in the note |
| The hand-over line cannot be sent (two failed `herdr agent prompt`) | the predecessor keeps its waiters and the record, stays frozen, writes `failed.json` with `"stage": "handover"` and tells the owner; the successor holds a valid receipt but not the lead; the owner decides (a later `closed.json` supersedes that `failed.json`) |
| Owner types into the old pane after the hand-over | the predecessor points to the new pane; `relay-close.sh` refuses; the successor tells the owner |
| Successor dies after the hand-over | the old pane is still open (only the successor closes it); the owner resumes it |
| Memory index over the cap | the relay proceeds; debt in the note; the successor's first job |
| An automatic relay fails | the gate retries once after 30 minutes; a second failure, or one that would repeat, stops it for this session with one owner alert; a hand-over failure is never retried |

## Script exit codes

| Script | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| `relay-check.py checklist` | relay dir printed | not run inside a Claude session (`CLAUDE_CODE_SESSION_ID` unset or its transcript not found) | a herdr read failed inside herdr, or the herd record or note is unreadable; no relay dir | a blocker (agent or workflow running in this session, git mid-operation); no relay dir |
| `relay-check.py identity` | identity JSON printed | not run inside a Claude session | | |
| `relay-check.py compare` | `PASS` | `FAIL` lines | | |
| `relay-check.py quiet` | no prompt after `handover.md` | a prompt reached the predecessor after `handover.md` (one it cannot date counts) | no `handover.md` yet | |
| `relay-launch.sh` | launched; prints the new pane id | failed: pane closed, `failed.json` written (without a relay-dir argument: a usage error, nothing written) | nothing started: not inside herdr, no checklist, or the checklist names no model | |
| `relay-close.sh` | closed and renamed (a failed rename is reported, the kept name recorded) | refused, pane left open; or the pane or pid outlived the close; or the records could not be written | before any close: not inside herdr, `CLAUDE_CODE_SESSION_ID` unset, no checklist, or a usage error | |

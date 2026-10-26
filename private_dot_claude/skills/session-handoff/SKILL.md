---
name: session-handoff
description: Use when wrapping up a session or nearing the context limit ("wrap up the session", "save a handoff", "about to compact", "running out of context"), when handing the lead to a new session ("relay", "hand over to a new session", "/relay"), when resuming in a fresh window ("continue from the last session", "pick up where we left off"), or when returning after a crash or limit ("we're back — resume", "agents crashed/died/stalled", "we ran out of tokens", "session/weekly limit hit", "rate limited"). Works in any project, code or content.
---

# Session Handoff

Document-and-clear: near the end of a session save a short, curated,
**command-verified** note; start the next session by reading only that note —
then verifying it against reality. Three modes: **SAVE** (`/handoff`),
**RESUME** (`/pickup`) and **RELAY** (`/relay`: SAVE, then a successor in a new
herdr pane RESUMEs, takes the lead and closes this session).

Notes live in `<memory-dir>/handoffs/YYYY-MM-DD-<slug>.md`, where
`<memory-dir>` is the project memory directory named in your system prompt (or
told to you by the user). Same-day same-topic → update in place. Notes are
task-state: ephemeral, deletable once the front closes. Durable facts (traps,
preferences, recipes) belong in real memory files — write them there, never bury
them in the note.

## SAVE mode

1. **Finish the current micro-step first** — never abandon a working change
   because the meter grew. Attached long work (a `run_in_background` test,
   build or paid run) must finish before this session closes: it dies with
   the session. Before a relay, detach a task that samples, spends or writes
   while it waits (step 3) rather than waiting it out: left attached, the
   hand-over kills it. Long work should have been started detached (global
   CLAUDE.md, "Long work outlives its session").
2. **Memory before the note.** Decide which durable facts (traps,
   preferences, recipes) are worth keeping and write them to memory files now.
   Do not ask first: this is the wrap-up, where an unanswered question is how a
   fact gets lost, and a wrong call costs one deletion. Then run
   `python3 -I ~/.claude/skills/session-handoff/scripts/memory-check.py <memory-dir> --fix`.
   It applies only two safe fixes (an index line for each memory written this
   session; removal of index lines whose every link is dead) and measures
   MEMORY.md as the loader does (200 lines, 25,000 UTF-16 units; the tail past
   the cap never loads). Exit 0 prints `clean (checked)`: that line is the
   note's Memory section. Exit 1 means debt remains: record it in the note's
   Memory section as the successor's first job. Never strand a durable fact in
   the note.
3. **Run the snapshots** — the note records **command output, not conversational
   memory**. Every figure, list or verdict, in every section, is copied from a
   command or file read at SAVE and named beside it with its scope (population,
   tree, commit range); anything not read that way is called an estimate. Every
   time the note or a lead file states is read from `date -u` or the event's own
   record (file mtime, a run's createdAt, a log line), never estimated or
   forecast; an unknown time says "unknown".
   - `git status --porcelain --branch` · `git log --oneline -5` ·
     `git log --oneline <merge-base>..HEAD` (the branch's own commits;
     `<merge-base>` is `git merge-base` against the branch this one forked
     from. `-5` cannot list them) ·
     `git log --oneline @{u}.. 2>/dev/null || git log --oneline HEAD --not --remotes 2>/dev/null`
     (skip silently only if there is no repo. With no upstream — or no remote at
     all — the second form IS the answer, not a failure: record it as
     `no-upstream, N commits exist nowhere else`. A branch with no upstream is the
     case where the count matters MOST, so it is never the case you skip.)
   - **Background tasks:**
     `python3 -I ~/.claude/skills/session-handoff/scripts/bg-tasks.py`
     (add `--transcript <earlier.jsonl>` for tasks started before a `/clear`).
     It reads the structured task ids Claude Code records (Bash, Monitor,
     Workflow, Agent); MCP tools moved to the background are not listed —
     record those by hand.
     Never a hand-written `ps | grep` filter: it can only show what you thought
     to match. Label each open task:
     - **waiter** — record its command VERBATIM and run its condition once now;
       record the result. It must be false. A condition already true is a
       broken waiter (a stale report file passes a bare `[ -f … ]`): fix it
       before writing the note. A report condition checks the report was
       written by this dispatch (mtime after the dispatch), never bare existence.
       It must also be able to turn true: a condition on a file nothing can
       write never fires. For a work task's exit-code file, read the line that
       writes it and confirm it runs on every path (an `exit` inside a
       redirected `{ … } > log` group ends the script before it), and have the
       waiter also fire when the work's pid is gone. A task that samples, spends
       or writes while it waits is **work**, not a waiter. Before a relay,
       detach that work (`nohup … ; echo $? > <x>.exit`) and let a passive
       `run_in_background` waiter watch its effect: the relay mirrors only the
       passive waiter.
     - **work** — its log path and exit-code file, and when it should end
       (an earlier comparable run's duration, with that run's log), so the
       successor can tell a slow run from a hung one without re-deriving it.
     Also record running workflows (each `resumeFromRunId`) and detached
     processes + the ports they hold, and what each creates while it runs
     (a worktree, a temp dir, a lock) and whether it removes it: RESUME's
     `git worktree list` and drift checks otherwise meet it unaccounted for.
     Name every result file a detached process will write, each with its
     waiter (or "unwatched"), and mark a file it writes only on a later event
     as not yet written: a queue of N jobs has N results to wait on. A process
     that respawns is recorded by the command or loop that respawns it, not
     its current pid.
   - **Herd panes**, when `HERDR_ENV=1`:
     `python3 -I ~/.claude/skills/session-handoff/scripts/herd.py status [extra-root …]`
     (read-only; `herd-snapshot.sh` is the same command). Its **workers** are the
     launches this lead recorded (`herd.py launch`, `adopt`), matched to live
     panes by session, then pane id, then name, each with its brief sha256,
     deliverable state and worktree: record the table as printed, plus the
     `herd.py wait` waiter covering them, verbatim. Classify only its
     **unclassified** panes (in scope, matching no launch): **self**, **shell**
     (the command it runs + its log), **not mine**, or **mine, launched by
     hand**: then `herd.py adopt <pane> --role <role>` and record it as a worker.
     A not-mine agent pane is recorded by what stays true (pane id, kind,
     session, cwd). The status column is as of the table's timestamp, not a
     claim that it still holds. One whose cwd is a tree this front writes is a
     possible live writer there, idle or not: say so, so the successor writes
     only in a worktree.
     A **lost** launch (no live pane) is recorded with what happened to it.
     Pass any dir outside the repo where this front launched panes.
   - Session crons — and ANY text the Next step orders re-issued (cron prompt,
     agent dispatch brief, relaunch line) or run (a check, gate or re-gate:
     the command, not just the result it should give): VERBATIM and runnable
     as written (no `…`, no `<…>` left to fill: a value written elsewhere
     names its file and line, one not known yet names where it will come
     from, such as a worker's report path), in the note or in a durable file or
     script (`.scratch/tmp/…` where the project has one, else `./tmp/…`; never
     `/tmp`) whose path the note records. Includes a cron
     deleted at wrap-up. "In this session's transcript" is never a valid location
     — RESUME is forbidden to read it.
   - `gh pr status` (skip silently if no remote / no gh)
   - **Other open fronts**, swept at every SAVE (grep, as RESUME does), in
     `<memory-dir>/handoffs/`. Record the finding, or `none (checked)`:
     - every other `kind: handoff` note whose `status:` is not `resumed`,
       `done` or `superseded`. It becomes the next `/pickup` target once this
       note is consumed. If this session closed its front, stamp it
       `superseded` with `superseded_by: <this note>`; otherwise record it in
       Backlog with what is still open in it;
     - every `EMERGENCY-*.md` without `status: consumed`, with its
       `session_id`. One this session wrote is accounted for by this note:
       stamp it `status: consumed` before writing the note. One another
       session wrote is not this front's: record it in In flight by name and
       session, and leave it unstamped. Do not wait for a pane match. Inside
       herdr, name the pane `herd.py status` shows for that session, or record
       "no pane here (other host or ended)".
4. **Write the note** (template below). Fill every section: for In flight, write
   the finding for each class **or `none (checked)`** — a present `none` proves
   you looked; an absent section reads as "forgot to check". Backlog lists
   every plan item not done, each with what it means, and names the plan file
   it was read from: an item name alone forces the successor to guess.
   A lead file the note cites (LEAD-STATE.md, COMMON.md, a spike's state file)
   is not called "current": quote its header line verbatim beside its mtime
   (`stat`). Tops drift behind appended bodies; the quote is the check.

Discipline: hand off at 50% of the context meter, not at the wire. Inside
herdr, relay to a new session (`/relay`; the relay gate asks a lead to, once
switched on); outside it, `/handoff`, then `/clear`, then `/pickup`. A lead
never compacts instead.

### Note template (copy this — it is THE format)

    ---
    kind: handoff
    date: YYYY-MM-DD
    topic: <2-4 word slug>
    status: in-progress | blocked | done | resumed | superseded
    superseded_by: <filename>    # ONLY with status: superseded — this spelling
    anchor: "<short-sha> <branch> <clean | dirty=<comma-separated paths>> <in-sync | ahead-N-of-<base>>"
    ---
    # <one sentence: what this session was about>

    ## Summary            (2–4 sentences)

    ## Decisions + why

    ## State              (✅ done / 🔄 in progress / ⛔ blocked)

    ## Next step          (ONE concrete move, runnable as written: each command
                          verbatim or a script path, no `…` or `<…>` to fill)

    ## Backlog            (every plan item not done: deferred or not started)
    <one line each: what it means · why it waits · what unblocks it. Name the
    plan file it was read from. A name alone is not enough: the successor must
    never have to guess what an item means.>

    ## What we tried / dead ends
    <chronological; EACH with the reason it was rejected, so the next session
    treats it as settled and does NOT reopen it — the most expensive thing to
    rediscover. If you truly lack the reason, say so; still do not invite a redo.>

    ## Verified vs NOT verified
    <what ran green (command + scope + result) vs what was NEVER run — mandatory
    whenever any code changed. Every recorded check can fail. A verification that
    passes by printing nothing (an empty diff, no matches, exit 0 and no output)
    names the case it was checked against, or why the command would print on a
    failure; otherwise it goes under NOT verified.>

    ## In flight
    <for EACH class: the finding, or `none (checked)` — background tasks from
    bg-tasks.py, one line per task id: command, waiter or work, and the
    condition result (waiter) or log + exit-code file + expected end (work) · workflow
    run IDs · session crons VERBATIM · detached processes+ports+log paths+what they create+each result file with its waiter or "unwatched" · open PRs+CI
    · herd panes (only when HERDR_ENV=1): `herd.py status` as printed (workers
    with brief, deliverable and the `herd.py wait` waiter; lost launches), and
    each unclassified pane classified self / shell / not mine / adopted
    · other open fronts: unconsumed notes and EMERGENCY snapshots>

    ## Artifacts          (paths, branches, PRs)

    ## Memory             (`clean (checked)`, or the debt memory-check.py left)

    ## Relay Q&A          (RELAY only: the successor's questions and disagreements, answered here)

    ## Pickup gaps        (written by the successor after it takes over)

Keep the anchor quoted and colon-free — an unquoted `:` inside it makes the
frontmatter unparseable, and the harness memory layer re-serializes what you
write. `dirty=` must NAME the paths: they are the only operands RESUME's drift
check has, and a bare `dirty` makes that check pass on anything.

Every path in the note is absolute or `~/`-rooted: the successor's cwd may be
a worktree or another checkout.

Core four (Summary, Decisions, State, Next step) plus Backlog and Memory always; the rest adapt to the
project — a content project has no anchor or Verified section, but In flight is
still answered (`none (checked)`).

## RESUME mode

**The note is a claim; reality is the authority.** Distrust it structurally —
verify even when nobody told you to, even when the note "looks complete".

**Relay sub-mode.** When the arguments carry `relay=<dir>`, you are a relay
successor: follow `references/relay.md` § Successor on top of the steps below.
Where they differ, `references/relay.md` wins over the RESUME steps below (it
re-arms waiters while the predecessor's still run, re-arms crons instead of
offering to, and does not wait for confirmation after the hand-over).
In short — read-only until the hand-over (no dispatch, merge or spend; do NOT
stamp the note yet), resume the note `<dir>/checklist.json` names, arm your own
waiters with `run_in_background` (never `nohup` or `&`: a detached waiter wakes
no one), marked `relay-<id>-w<k>`, write `<dir>/receipt.json`, end your turn
addressed to the predecessor. After the hand-over, a clean pickup keeps driving
under the standing instruction quoted in `handover.md`; it does not wait for
confirmation. Log anything the note lacked per `references/feedback.md`.

1. **Locate + sweep.** Work inside `<memory-dir>/handoffs/` (or the topic/path in
   the arguments). Take the newest **unconsumed** `kind: handoff` note — match
   `kind: handoff` ANYWHERE in the frontmatter (grep, not strict YAML): the
   harness memory layer may rewrite frontmatter and nest the fields under
   `metadata:`. **Unconsumed** = its `status:` (grep it the same loose way) is
   none of `resumed` · `done` · `superseded`. Consuming a note REWRITES it, so a
   consumed note is routinely the mtime-newest file in the directory — take it
   and you resume a front someone already closed. If every note is consumed,
   never resume one anyway: that is a Tier-2 trigger (step 3) — audit from git
   and process evidence, and report the closed fronts you found. If a note names
   a successor (`superseded_by:`; older notes spell it `superseded-by:`), read
   that successor and treat IT as the front — one hop only, missing target
   reported.
   Then sweep for evidence that outranks it: any `EMERGENCY-*.md` (the PreCompact
   hook dumps one BEFORE the compaction runs, so it marks an *attempt* — the
   compaction itself may never have landed) and any note **newer than the one you
   selected**
   — "newer" means most recently WRITTEN (file mtime, e.g. `ls -t`), never the
   frontmatter `date:` or filename (a same-day EMERGENCY is newer; lexical sort
   lies). Read ONLY handoff artifacts — those notes, those snapshots, plus any
   EMERGENCY the worktree check in `references/recovery.md` (§1, item 6)
   surfaces — not the rest of the memory tree, not old session history. Note the
   selected note's date: a note older than ~7 days, or a session gap of hours, is
   suspect.
2. **Verify before trusting.** Current branch + `git status` vs the `anchor`,
   BOTH directions: a path recorded dirty that is now clean is drift, and a path
   dirty NOW that the note accounts for nowhere (anchor, State, In flight) is
   drift too. An anchor that says `dirty` without naming paths leaves this check
   with no operands — never let it pass vacuously: treat every uncommitted path
   as unaccounted-for and classify it per `references/recovery.md` §2. Then
   recorded In-flight work vs **live OS processes** (`pgrep`/`ps`, `lsof` on
   ports/logs, DB locks) + PRs — NOT the in-session task registry, which is
   empty in a fresh session and can never prove "nothing is running".
   **Never declare a recorded agent dead without checking THIS session's
   `subagents/` dir** — see the false-death rule below; `ps` cannot see an
   in-process teammate and its old transcript freezes at the clear. An
   `EMERGENCY-*.md` is **degraded mechanical evidence** (a pointer dumped by a
   dying session), never a curated note and never the authority — when it and
   git disagree, git wins.

   **The false-death trap — an agent survives `/clear`.** A note saying an agent
   is RUNNING is the one claim you must not "verify" into a corpse. An in-process
   teammate keeps running inside the SAME OS process across a clear or
   compaction. On a **clear** its transcript **re-homes to the NEW session id**;
   a **compaction** keeps the same session id and the same file, so there is no
   new home to look in. All three
   obvious signals lie at once: its file under the OLD `<session>/subagents/`
   freezes at the clear and reads exactly like a death mid-tool-call; `ps` never
   showed it at all, because it has no process of its own; and a quiet minute or
   two is a model thinking, not a corpse.

   Before concluding dead, BOTH of: (a) list **this** session's
   `~/.claude/projects/<encoded-cwd>/<CURRENT-session-id>/subagents/` — a live
   agent reappears there under the SAME agent id; (b) watch what it would touch
   over a real interval (`stat` twice ~60s apart, or `ls -t` the work dir) — a
   new file or a grown byte count is proof of life that outranks any transcript,
   and it is the test that discriminates. **`SendMessage` is not a third test:**
   a send to a completed agent succeeds and RESUMES it from its transcript, so it
   can never return dead — and you would send precisely when (a) and (b) came
   back empty, restarting a finished agent into the tree you are about to work
   in. Never send to decide the verdict. Dead is a verdict you earn from those
   two, never from silence — and when they disagree, or both come back empty, the
   agent is **undecided**: that goes to the owner in the Tier-2 doubt batch
   (`references/recovery.md` §6), never to a guess of dead.
   **Until then its files belong to a live writer: read them, never write them**
   — no edit, no revert, no mutate-and-restore "just to check". A restore that
   races a live edit destroys work that may exist in no repo. If you already
   raced it, tell it exactly what you did and when, and let IT re-verify.

   **Herd panes — the note records any, or `HERDR_ENV=1`.** Invoke the `herdr`
   skill before the first herdr command: a note that records panes is the
   explicit mention its description waits for. Re-run `herd.py status` with
   the note's extra roots: it matches each recorded worker to its live pane by
   session, then pane id, then name. herdr's live status outranks the note; a
   worker the note records that `status` lists as lost, and an unclassified
   pane the note does not account for, are drift. A worker's progress is its
   deliverable file (present? sha256?), never its chat. Only read panes: no
   `agent prompt`, `send-keys` or `/pickup` to a worker to learn its state. A
   prompt to an idle worker makes it a second writer, and a pane whose cwd is
   this repo shares this memory dir, so `/pickup` there would select and stamp
   THIS note. A recorded waiter is a background task of the old session: `pgrep
   -f` its command, and offer to re-arm it verbatim only when it is gone (one
   `herd.py wait`, run with `run_in_background`, covers every worker).
3. **Classify → tier:**
   - **Tier 1 (clean):** note exists · anchor matches reality · no newer note ·
     no drifted evidence · no unconsumed EMERGENCY, except one this note records
     as another front's by filename and `session_id` · in-flight items all
     accounted for →
     summarize in **~3 lines** (**where we are → next step → what to avoid**),
     offer to re-arm any recorded session crons, then **WAIT for confirmation**
     — do NOT start implementing.
   - **Tier 2 (recovery)** when ANY of: no note · every note already consumed ·
     any **unconsumed** `EMERGENCY-*.md` in the directory, whatever its mtime —
     an unconsumed EMERGENCY routes to Tier 2 by design, even if its git state
     matches the anchor, and even if it now sorts OLDER than the note (stamping
     a note bumps it above an EMERGENCY it postdates; verification is cheap,
     missed drift is not). One the newest unconsumed note records as another
     front's, by its filename and `session_id`, does not send RESUME to Tier 2.
     **Unconsumed** = no `status: consumed` in it,
     grepped the same loose way as a note's · a
     note newer (by mtime) than the one being resumed · anchor drift vs reality ·
     crash signals (hours-scale gap, dead/stalled agents, compact marker,
     in-flight items missing). Before continuing, **classify each prior change
     landed / partial / phantom / unknown** (never discard uncommitted prior
     work without classifying it),
     **batch owner-level open questions to the user** instead of silently
     settling them, and follow `references/recovery.md`.
4. **Afterwards: stamp what you consumed** on disk (in relay sub-mode: only
   after the hand-over) — the stamp is exactly what
   steps 1 and 3 grep to skip it next time, and stamping is also what makes a
   file mtime-newest, so leaving one unstamped is a guaranteed re-resume.
   - The note → `status: resumed`. Never stamp over `done` or `superseded`:
     those are terminal and already exclude it.
   - **Every `EMERGENCY-*.md` this pass actually accounted for → add
     `status: consumed`** to its frontmatter, edited in place. Never rename it:
     the hook's own prune and `references/recovery.md` §1 item 6 both match
     `EMERGENCY-*.md`, so a renamed file escapes the retention AND the sweep.
     Renaming does not retire it. SAVE stamps this session's own snapshots when
     it writes the note; this stamp retires the ones this pass accounted for.
     A snapshot the note records as another front's is left unstamped. The hook
     writes one per compaction *attempt* — an unstamped snapshot the note does
     not record as another front's latches every later `/pickup` here into
     Tier 2. Stamp only snapshots in
     THIS front's memory dir; one surfaced in another project's dir (§1 item 6)
     is reported, never written.
   Session crons recorded in the note NEVER survive into a fresh session —
   offer to re-arm them; never claim to have "confirmed" them.

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
4. `bash ~/.claude/skills/session-handoff/scripts/relay-launch.sh <relay-dir>`
   (Bash timeout 300000).
5. Wait on `<relay-dir>/receipt.json` with a `run_in_background` until-loop,
   never on the screen. It is bounded: 20 minutes, the successor gone, or the
   successor `blocked` for about 2 minutes; no usable receipt fails the relay
   (`"stage": "receipt"`).
6. `python3 -I ~/.claude/skills/session-handoff/scripts/relay-check.py compare <relay-dir>`.
   Fix and answer under the note's `## Relay Q&A`, at most 2 rounds; then
   write `failed.json`, close the successor you launched (only once its pane
   is shown to still host it), keep the lead and ask the owner.
7. Hand-over, in this order: delete your session crons; write
   `<relay-dir>/handover.md` once (never edit it after sending); send
   "Read <relay-dir>/handover.md; you have the lead." and check the send
   (one retry); only once it is sent, stop your own waiters (the compare PASS
   proved the successor covers every task and worker) and end your turn. Two
   failed sends: keep your waiters, write `failed.json` (`"stage": "handover"`)
   and tell the owner. Never close your own pane: the successor does, with
   `bash ~/.claude/skills/session-handoff/scripts/relay-close.sh <relay-dir>`.

**Automatic relays.** Once the owner registers `scripts/relay-gate.py` as a
Stop and PostToolUse hook, a lead (named `lead-…`) is blocked at its first safe
turn end at or above 50% with "Run /relay now": run it, or end your turn if a
listed task is long work that must finish first. The relay gate now names the
only session in a main checkout `lead-<project>` at its first turn end, and you
still name a lead yourself when several sessions share a checkout. Details:
`references/relay.md` § Automatic relays.

## Red flags — you are about to violate this skill

- Writing a figure, list or verdict from memory instead of a named command or file
- Recording a bare `dirty` anchor with no paths — it disarms RESUME's only check
- Resuming the mtime-newest note without reading its `status:` — a `resumed` /
  `done` / `superseded` note is a closed front, and consuming one is what put it
  at the top of `ls -t` in the first place
- "The note looks complete, no need to run git status" — verify anyway
- Treating an `EMERGENCY-*.md` snapshot as a curated, authoritative note
- Pointing the successor at "this session's transcript" for anything it must re-issue
- A Next step that gives a check's expected result without its command, or a
  command with a `…`, a `<placeholder>` or an elided path left to fill, or a
  path in the note that is not absolute or `~/`-rooted
- Continuing a dead agent's "finished" work without re-running its gates
- Declaring a recorded agent dead from a frozen transcript, an empty `ps`, or a
  quiet minute or two — and then writing to the files it owns
- Recording a herd worker without its brief, deliverable and waiter, or
  prompting / `/pickup`-ing a worker pane to find out what state it is in
- Launching, dispatching or closing a worker with raw `herdr agent start`,
  `agent prompt` or `pane close` instead of `herd.py launch`, `dispatch`,
  `close`: the record no longer explains the herd
- Settling an owner-level design question yourself instead of asking
- Leaving a consumed note unstamped, or skipping the handoff because
  "compaction will summarize it anyway"
- Recording background tasks from a hand-written `ps | grep` instead of
  `bg-tasks.py`
- Saving a waiter whose condition is already true, or that can never turn true
- A recorded check that passes by printing nothing, with no case it was checked against
- In a relay: closing your own pane, stamping the note before the hand-over,
  or acting in the old pane after it; as the successor, typing into the old
  pane (`relay-close.sh` then refuses to close it)

## Known limits (stated, not solved)

- Nothing in-session can run while the API/usage window is exhausted — true
  zero-touch resume needs an external monitor.
- A `--resume`d session may restore context incompletely — verify, never assume.
- Checkpoints/rewind track file-tool edits only; bash-created files and git
  state reconcile from git / filesystem evidence.

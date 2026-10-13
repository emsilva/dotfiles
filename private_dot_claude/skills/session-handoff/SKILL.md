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
   the cap never loads). Exit 0 prints `clean (checked)`: that line is the
   note's Memory section. Exit 1 means debt remains: record it in the note's
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

    ## Next step          (ONE concrete move)

    ## Backlog            (every plan item not done: deferred or not started)
    <one line each: what it means · why it waits · what unblocks it. A name
    alone is not enough: the successor must never have to guess what an item
    means.>

    ## What we tried / dead ends
    <chronological; EACH with the reason it was rejected, so the next session
    treats it as settled and does NOT reopen it — the most expensive thing to
    rediscover. If you truly lack the reason, say so; still do not invite a redo.>

    ## Verified vs NOT verified
    <what ran green (command + result) vs what was NEVER run — mandatory whenever
    any code changed>

    ## In flight
    <for EACH class: the finding, or `none (checked)` — background tasks from
    bg-tasks.py, one line per task id: command, waiter or work, and the
    condition result (waiter) or log + exit-code file (work) · workflow
    run IDs · session crons VERBATIM · detached processes+ports+log paths · open PRs+CI
    · herd panes (only when HERDR_ENV=1): one line per pane, classified
    self / worker / shell / not mine, workers with brief, deliverable and waiter>

    ## Artifacts          (paths, branches, PRs)

    ## Memory             (`clean (checked)`, or the debt memory-check.py left)

    ## Relay Q&A          (RELAY only: the successor's questions and disagreements, answered here)

    ## Pickup gaps        (written by the successor after it takes over)

Keep the anchor quoted and colon-free — an unquoted `:` inside it makes the
frontmatter unparseable, and the harness memory layer re-serializes what you
write. `dirty=` must NAME the paths: they are the only operands RESUME's drift
check has, and a bare `dirty` makes that check pass on anything.

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
   explicit mention its description waits for. Re-run `herd-snapshot.sh` with
   the note's extra roots, and match each recorded pane by `session=`, then pane
   id, then name. herdr's live status outranks the note, and a pane in scope that
   the note does not account for is drift. A worker's progress is its
   deliverable file (present? sha256?), never its chat. Only read panes: no
   `agent prompt`, `send-keys` or `/pickup` to a worker to learn its state. A
   prompt to an idle worker makes it a second writer, and a pane whose cwd is
   this repo shares this memory dir, so `/pickup` there would select and stamp
   THIS note. A recorded waiter is a background task of the old session: `pgrep
   -f` its command, and offer to re-arm it verbatim only when it is gone.
3. **Classify → tier:**
   - **Tier 1 (clean):** note exists · anchor matches reality · no newer /
     EMERGENCY / drifted evidence · in-flight items all accounted for →
     summarize in **~3 lines** (**where we are → next step → what to avoid**),
     offer to re-arm any recorded session crons, then **WAIT for confirmation**
     — do NOT start implementing.
   - **Tier 2 (recovery)** when ANY of: no note · every note already consumed ·
     any **unconsumed** `EMERGENCY-*.md` in the directory, whatever its mtime —
     an unconsumed EMERGENCY ALWAYS routes to Tier 2 by design, even if its git
     state matches the anchor, and even if it now sorts OLDER than the note
     (stamping a note bumps it above an EMERGENCY it postdates; verification is
     cheap, missed drift is not). **Unconsumed** = no `status: consumed` in it,
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
     Nothing else retires a snapshot, and the hook writes one per compaction
     *attempt* — so absent this stamp, one keypress latches every later
     `/pickup` in that project into Tier 2 permanently. Stamp only snapshots in
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
5. Wait on `<relay-dir>/receipt.json` with a background until-loop, never on
   the screen. It is bounded: 20 minutes, the successor gone, or the
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

## Red flags — you are about to violate this skill

- Writing State / anchor / In flight from memory instead of command output
- Recording a bare `dirty` anchor with no paths — it disarms RESUME's only check
- Resuming the mtime-newest note without reading its `status:` — a `resumed` /
  `done` / `superseded` note is a closed front, and consuming one is what put it
  at the top of `ls -t` in the first place
- "The note looks complete, no need to run git status" — verify anyway
- Treating an `EMERGENCY-*.md` snapshot as a curated, authoritative note
- Pointing the successor at "this session's transcript" for anything it must re-issue
- Continuing a dead agent's "finished" work without re-running its gates
- Declaring a recorded agent dead from a frozen transcript, an empty `ps`, or a
  quiet minute or two — and then writing to the files it owns
- Recording a herd worker without its brief, deliverable and waiter, or
  prompting / `/pickup`-ing a worker pane to find out what state it is in
- Settling an owner-level design question yourself instead of asking
- Leaving a consumed note unstamped, or skipping the handoff because
  "compaction will summarize it anyway"
- Recording background tasks from a hand-written `ps | grep` instead of
  `bg-tasks.py`
- Saving a waiter whose condition is already true
- In a relay: closing your own pane, stamping the note before the hand-over,
  or acting in the old pane after it; as the successor, typing into the old
  pane (`relay-close.sh` then refuses to close it)

## Known limits (stated, not solved)

- Nothing in-session can run while the API/usage window is exhausted — true
  zero-touch resume needs an external monitor.
- A `--resume`d session may restore context incompletely — verify, never assume.
- Checkpoints/rewind track file-tool edits only; bash-created files and git
  state reconcile from git / filesystem evidence.

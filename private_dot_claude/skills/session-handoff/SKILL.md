---
name: session-handoff
description: Use when wrapping up a session or nearing the context limit ("wrap up the session", "save a handoff", "about to compact", "running out of context"), when resuming in a fresh window ("continue from the last session", "pick up where we left off"), or when returning after a crash or limit ("we're back — resume", "agents crashed/died/stalled", "we ran out of tokens", "session/weekly limit hit", "rate limited"). Works in any project, code or content.
---

# Session Handoff

Document-and-clear: near the end of a session save a short, curated,
**command-verified** note; start the next session by reading only that note —
then verifying it against reality. Two modes: **SAVE** (`/handoff`) and
**RESUME** (`/pickup`).

Notes live in `<memory-dir>/handoffs/YYYY-MM-DD-<slug>.md`, where
`<memory-dir>` is the project memory directory named in your system prompt (or
told to you by the user). Same-day same-topic → update in place. Notes are
task-state: ephemeral, deletable once the front closes. Durable facts (traps,
preferences, recipes) belong in real memory files — write them there, never bury
them in the note.

## SAVE mode

1. **Finish the current micro-step first** — never abandon a working change
   because the meter grew.
2. **Run the snapshots** — the note records **command output, not conversational
   memory**. Never write State / anchor / In flight from what you remember:
   - `git status --porcelain --branch` · `git log --oneline -5` ·
     `git log --oneline @{u}.. 2>/dev/null || git log --oneline HEAD --not --remotes 2>/dev/null`
     (skip silently only if there is no repo. With no upstream — or no remote at
     all — the second form IS the answer, not a failure: record it as
     `no-upstream, N commits exist nowhere else`. A branch with no upstream is the
     case where the count matters MOST, so it is never the case you skip.)
   - Background work you started: task/agent list, running workflows (record
     each `resumeFromRunId`), detached processes + the ports they hold
   - Session crons — and ANY text the Next step orders re-issued (cron prompt,
     agent dispatch brief, relaunch line): VERBATIM in the note, or in a durable
     file (`./tmp/…`, never `/tmp`) whose path the note records. Includes a cron
     deleted at wrap-up. "In this session's transcript" is never a valid location
     — RESUME is forbidden to read it.
   - `gh pr status` (skip silently if no remote / no gh)
3. **Write the note** (template below). Fill every section: for In flight, write
   the finding for each class **or `none (checked)`** — a present `none` proves
   you looked; an absent section reads as "forgot to check".
4. **Decide and write durable facts to persistent memory** — judge which
   trap/preference/recipe is worth keeping, write it to a memory file, and report
   what you wrote. Do not ask first: this is the wrap-up, where an unanswered
   question is how a fact gets lost, and a wrong call costs one deletion. Never
   strand one in the note.

Discipline: save at ~50–60% of the context meter, not at the wire. Hand off when
the next chunk of work shares little of the current window; for direct
continuation, compact instead.

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

    ## What we tried / dead ends
    <chronological; EACH with the reason it was rejected, so the next session
    treats it as settled and does NOT reopen it — the most expensive thing to
    rediscover. If you truly lack the reason, say so; still do not invite a redo.>

    ## Verified vs NOT verified
    <what ran green (command + result) vs what was NEVER run — mandatory whenever
    any code changed>

    ## In flight
    <for EACH class: the finding, or `none (checked)` — tasks/agents · workflow
    run IDs · session crons VERBATIM · detached processes+ports+log paths · open PRs+CI>

    ## Artifacts          (paths, branches, PRs)

Keep the anchor quoted and colon-free — an unquoted `:` inside it makes the
frontmatter unparseable, and the harness memory layer re-serializes what you
write. `dirty=` must NAME the paths: they are the only operands RESUME's drift
check has, and a bare `dirty` makes that check pass on anything.

Core four (Summary, Decisions, State, Next step) always; the rest adapt to the
project — a content project has no anchor or Verified section, but In flight is
still answered (`none (checked)`).

## RESUME mode

**The note is a claim; reality is the authority.** Distrust it structurally —
verify even when nobody told you to, even when the note "looks complete".

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
4. **Afterwards: stamp what you consumed** on disk — the stamp is exactly what
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
- Settling an owner-level design question yourself instead of asking
- Leaving a consumed note unstamped, or skipping the handoff because
  "compaction will summarize it anyway"

## Known limits (stated, not solved)

- Nothing in-session can run while the API/usage window is exhausted — true
  zero-touch resume needs an external monitor.
- A `--resume`d session may restore context incompletely — verify, never assume.
- Checkpoints/rewind track file-tool edits only; bash-created files and git
  state reconcile from git / filesystem evidence.

# Tier-2 recovery — evidence rules

Entered from RESUME (SKILL.md) once it classified **Tier 2**: the note is
absent, contradicted by reality, or crash signals exist. Reality is the
authority; every self-report — the note, a dead agent's "done", an
`EMERGENCY-*.md` — is a claim to be checked against git / filesystem / process
evidence. Act first on the mechanical recovery (re-verify, resume live work);
**batch genuine owner-level doubts and design questions to the owner ONCE, in
the closing report** — never silently settle them, never spray one question per
finding.

## 1 · Inventory (evidence-led, in this order)
**The in-session agent/task registry is not a source of truth for what is
running.** In a fresh post-crash session it is empty by construction — like the
session crons — so an empty registry means "I don't know", never "nothing is
running". Detect live work from the OS, not the list.
1. **Live processes still running** — an orphaned agent survives the session that
   spawned it. Probe generically: `pgrep`/`ps` for agent runtimes (claude,
   node, opencode, …), `lsof` on the lane log / ports a detached process holds,
   `pg_stat_activity` for held DB locks. **`pgrep` empty ≠ clear** — cross-check
   the port/lock before concluding nothing is up. Degrade silently: a project
   with no background agents just finds nothing.
   **An in-process teammate is invisible to every probe in this item** — it has
   no process of its own and survives the clear/compaction inside the parent. A
   clear re-homes its transcript to the NEW session id; a compaction keeps the
   same one. Its old
   `<dead-session>/subagents/*.jsonl` freezes at the clear and mimics a death
   mid-tool-call exactly. Check `<CURRENT-session>/subagents/` for the same agent
   id and watch its output files' mtimes/sizes over a real interval; growth is
   the ruling evidence. Do NOT `SendMessage` it to decide — a send to a completed
   agent succeeds and RESUMES it, so it can never return dead; undecided goes to
   the doubt batch (§6). Until it is proven dead, its files are read-only to you
   (SKILL.md RESUME §2).
2. Last task-list snapshot in the dead session's transcript — the **file**
   `~/.claude/projects/<encoded-cwd>/<session-id>.jsonl` (no id to hand:
   `ls -t ~/.claude/projects/<encoded-cwd>/*.jsonl | head`) — historical ground
   truth for done-vs-pending at time of death (NOT what is live now — see above).
3. Transcript tails — main (that `.jsonl`) plus
   `<encoded-cwd>/<session-id>/subagents/*.jsonl`; the like-named *directory*
   holds only `subagents/`, `tool-results/`, `workflows/` and never the main
   transcript, so do not look for it there. The last complete
   `tool_result` is the executed/pending boundary; a tool call with no result =
   died mid-turn. An `"isCompactSummary":true` entry (or a `compactMetadata`
   field) = the session compacted; before the newest one the transcript is a
   summary, not a record.
4. Background task output files; interrupted workflows — the run id IS the
   `wf_*` directory name under `<session>/subagents/workflows/`; the
   `journal.jsonl` inside it shows which agents already returned results.
5. Git truth: `git status`, `git worktree list`, branches ahead of upstream,
   recent commits, HEAD identity (agents sometimes commit to `main` from a
   shared tree), open PRs via `gh pr list` (skip silently without a remote).
6. `EMERGENCY-*.md` snapshots (in `<memory-dir>/handoffs/`): a mechanical
   git/port dump a dying session left behind — **degraded evidence, never a
   curated note and never the authority. When it and git disagree, git wins.**
   A snapshot lands in the compacting session's OWN project dir, so a child that
   compacted inside a worktree left it somewhere this front never looks: for each
   path from item 5's `git worktree list`, encode it the harness way (every
   non-alphanumeric → `-`) and check
   `~/.claude/projects/<that-encoding>/memory/handoffs/EMERGENCY-*.md`. A hit is
   a compaction signal → Tier 2. Derive the paths from `worktree list`; do NOT
   prefix-glob `~/.claude/projects/` — a sibling encoding that merely shares the
   repo's prefix is an unrelated project with its own live notes.
7. Herd panes via the herdr CLI — ONLY when `HERDR_ENV=1` (see §4).

## 2 · Audit — self-reports are claims, not facts
Classify EVERY in-flight item from artifacts alone. **Never discard uncommitted
prior work without first classifying it** — that instinct destroys evidence on
anything bigger than a vacuous stub.
- **landed** — committed/merged AND its gates re-run green by THIS session.
- **partial** — real work not yet safe: an uncommitted diff, failing or
  never-run gates, a branch with no PR. Preserve it and continue it; never
  delete it unclassified.
- **phantom** — claimed done, but the artifacts are absent (no commit, no files,
  no green run). The claim is wrong; the work does not exist — do not "recover"
  something that was never built.
- **unknown** — evidence insufficient to decide → carry it into the doubt batch
  (§6); do not guess a class.

A dead agent's final "done" is a claim, not a fact. Re-run the gates for
anything you will build on. **Never redo landed work** — don't rewrite a
misleading-but-correct commit; supersede it forward instead.

## 3 · Recover — resume > restart > redo
- Stalled named agent still alive → nudge it (SendMessage); don't respawn a
  live agent.
- Interrupted workflow → resume via `resumeFromRunId` (the cached prefix is
  free); don't restart it from zero.
- Dead subagent with partial work → respawn with an audit-first prompt: point it
  at its branch / worktree / transcript tail and say "prior work is an
  unverified claim — re-read the files, `git diff`, re-run the gates, then
  continue; do NOT redo landed steps."
- Claimed-done work you must build on → re-run its gates + a real smoke here.
- **Stagger respawns in small waves** — a parallel relaunch recreates the
  rate-limit spike that killed the session in the first place.

## 4 · Herd sweep (`HERDR_ENV=1` only)
Only inside a real herd. Enumerate sibling panes via the herdr CLI (read-only),
then inject recovery into idle / failed **Claude** panes — siblings routinely
run per-child branches and worktrees, so unfamiliar branches are normal, not a
reason to skip. Skip non-Claude panes and actively-streaming agents. **The
injected payload is always the self-scoped resume command (`/pickup` — the pane
audits its OWN context), NEVER front-specific instructions from this session** —
that self-scoping is what makes cross-front injection safe. Report who was
nudged (often nobody). NEVER sweep outside herdr; when in doubt,
enumerate-and-report rather than inject.

## 5 · Heartbeat
Only if work is still genuinely in flight after this pass: arm ONE in-session
cron (~20 min) to re-check, re-enter recovery if something stalled, and
self-delete once everything has landed. **Check the cron list first — never arm
a second heartbeat.** A finished audit needs no heartbeat; don't arm one.

## 6 · Report (outcome-first)
Lead with the outcome, then the evidence:
- situation class (compact-caught · crash · stale note · drifted git · …);
- items found, each tagged **landed / partial / phantom / unknown**;
- what was resumed / restarted / re-verified, and what was left as-is;
- the batched owner-level doubts + design questions — ask them here, together,
  and **hold for the owner's call before starting fresh implementation**;
- heartbeat state (armed / none needed).

Then stamp what you consumed on disk: the note `status: resumed` (never over a
terminal `done` or `superseded`), and every `EMERGENCY-*.md` you accounted for
`status: consumed`, edited in place — never renamed, and only in this front's own
memory dir; a snapshot item 6 surfaced under another project is reported, not
written. That stamp is what the next pickup greps to skip them, and it is the
only thing that retires a snapshot: leave one unstamped and every later `/pickup`
in that project routes here forever. Then offer to re-arm any session crons the
note recorded; they died with the old session, so never claim to have confirmed
them.

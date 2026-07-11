# /ship run — orchestrate work to a proven result

The argument is `<epic#>`, `<issue#>`, or `<path/to/epic-spec.md>`. If absent,
ask for it. You are the **owner/orchestrator**: you DISPATCH worker agents to
implement each chunk and you INDEPENDENTLY validate + merge their work. You
write no feature code yourself — you dispatch, redline, validate, and decide.

The **epic issue is the contract**: it carries the North Star, the build
order, per-child acceptance gates, and per-child model tiers. The **ledger**
(schema in SKILL.md) carries the run's state.

## Resolve the target (facts, not argument shape)
- **Number** → `gh issue view <n>`: epic label / sub-issues present → it's an
  **epic**; otherwise it's a **single issue** (see "Single issue? The short
  loop" below).
- **Path** → a local epic file (plan mode's no-`gh` degrade). Children and the
  ledger live in the file; track state via TaskList + the file's `## Ledger`
  section. Everything below applies with "issue body" ↦ "file section" and
  "ledger comment" ↦ "`## Ledger` section"; skip the `gh`-only steps
  (sub-issue closes, PR merges happen locally or wait until issues exist).

## Pane label (herdr) — live progress at a glance
Inside herdr (`HERDR_ENV=1`), keep THIS pane's label in sync with the run so
the herd sidebar reads as a progress board. **Best-effort, non-fatal** — a
cosmetic label must never block or fail a run: guard on `HERDR_ENV`, resolve
the pane id at runtime, swallow errors. The label is a **derived view of the
ledger** (recomputed from merged/total each time — never a separately tracked
counter), so it is correct on resume and cannot drift.

- **Epic, running:** `epic #<n> (<merged>/<total>)` — `<merged>` = children in
  state `merged`; `<total>` = all children (in-flight children count as
  not-done).
- **Epic, all children merged, DoD finale not yet proven:** `epic #<n> (N/N)` —
  `(N/N)` does NOT mean done (merged ≠ done; the DoD demo is still owed).
- **Epic, DoD proven + epic closed:** `epic #<n> ✓`.
- **Single issue:** `#<n>` while running → `#<n> ✓` once its gate re-runs green
  on merged main. No counter — it's one loop.

Write it at three points: **Step 0** after the ledger↔ground-truth
reconciliation (from the reconciled merged count); **Step 2 item 10** after
each merge, in the same ledger checkpoint (recompute + re-apply); **Step 3**
when the DoD is proven and the epic closed (swap the counter for `✓`). Quote
the arg — `#` and `()` are shell metacharacters:

    [ "$HERDR_ENV" = 1 ] && PANE=$(herdr pane current 2>/dev/null \
      | python3 -c 'import sys,json;print(json.load(sys.stdin)["result"]["pane"]["pane_id"])' 2>/dev/null) \
      && [ -n "$PANE" ] && herdr pane rename "$PANE" "<label>" >/dev/null 2>&1 || true

## ★ NORTH STAR — drive toward the goal, not merged PRs ★
The goal is the **North Star** — the *outcome* committed to (a running,
demonstrably-correct result that hits a stated measurable signal), not a stack
of green PRs. Read the North Star the plan recorded, in full. For every slice
ask "does this move us **measurably closer** to the North Star signal?" — not
just "is the code correct?". A clean per-task green does NOT mean the whole
thing composes into a working system. **Catch "unproven done"**: missing
pieces masked by vacuous passes, inert merges that don't compose, scope that
quietly narrowed. When the goal is drifting, **STOP and escalate** (mandatory,
not optional — the escalation ladder in SKILL.md says who decides when the
owner is away). The end-to-end demonstration is EXPLICIT work to
plan and execute — never an afterthought.

## Step 0 — Ground + resume (idempotent — this is both START and RESUME)
Assume nothing about prior conversation state: this step is how you begin a
fresh run AND how you recover after compaction or session loss. In order:
1. Read the epic IN FULL — North Star / how-we'll-know / DoD, build order,
   each child's acceptance gate + model tier. Read every child issue. Note
   `blocked-by` / `depends-on`.
2. Read the **ledger** (pinned epic comment, or the file's `## Ledger`). If
   none exists, seed it (all children `queued`).
3. **Reconcile ledger vs ground truth — ground truth wins.** Check: sub-issue
   open/closed states, `gh pr list` (open PRs referencing children),
   `git worktree list` (stale validation/worker worktrees), TaskList. Correct
   the ledger to match reality.
4. **Quiesce prior-session workers FIRST.** A crashed or cleared session's
   workers may have been auto-resumed by the environment (e.g. herdr) and
   still be writing. Before dispatching ANY fresh worker, establish who is
   actually writing each worktree from process facts — `lsof +D <path>` /
   `pgrep -lf <path>` plus the agent/pane list — NEVER from commit/reflog
   cadence (a clean single-threaded reflog does not prove a single writer).
   Adopt, stop, or wait out each zombie before re-dispatching its child.
5. Read the repo's standing rules (`CLAUDE.md` / `AGENTS.md` / contributing
   guide) — your redline checklist — and the committed decision log / spec
   (often under `docs/`) plus any auto-memory pointer for the epic.
6. Rebuild the TaskList if missing: one task per child + one for the DoD
   demonstration, `blockedBy` edges from the build order.
7. **Resume each child from its actual state:**
   - **A PR exists → NEVER dispatch a new worker for it** — validate that PR
     (Step 2), whatever the ledger or your instincts say.
   - Ledger says dispatched/executing and the named agent is alive → continue
     that agent (poke it; verify progress via commit timestamps, not claims).
   - Dispatched but the agent is gone → re-dispatch, **inlining the ledger's
     redline decisions** so the new worker inherits them.
   - Queued and unblocked → dispatch (Step 1).
8. Remove stale validation worktrees left by prior sessions.
9. **Pane label (herdr):** set this pane's label from the reconciled merged
   count — see "Pane label (herdr)" above.

Redline decisions from a lost session exist **only** if the ledger has them —
that is why checkpoint discipline (SKILL.md) is non-negotiable.

## Single issue? The short loop
For a single well-gated issue (no children): run the per-issue loop (Step 1)
for just that issue, then the full validate/merge recipe (Step 2). The ledger
lives as a comment on the issue itself. The finale degenerates to: **re-run
the issue's acceptance gate on merged main** and confirm the issue's stated
goal/how-we'll-know signal. Everything else below applies unchanged.

## Step 1 — The per-issue agent loop
For each child, run this loop (dispatch INDEPENDENT issues in PARALLEL —
separate named agents in one message; the long-pole / integration issue goes
LAST):

**Collision preflight before every dispatch:** check `git worktree list`,
open PRs, and the sibling issues' scopes for work already covering this
child's defect — this workflow has dispatched two agents at ONE fix under two
issues before. One defect = one child; if two children turn out to share a
fix, re-scope before dispatching, and HOLD if a "proceed" instruction crosses
your collision flag. **Ledger checkpoint:** record the dispatch (agent name,
tier) before it happens.

1. **Dispatch** a worker `Agent` **at the child's model tier** (from the
   plan; if unset or unsure, invoke `choosing-a-model` — default Opus,
   escalate to Fable only for a keystone or a gnarly root-cause, Sonnet/Haiku
   only for genuinely mechanical, gate-backed work). Give it a `name` so you
   can continue it. Tell it: ground vs current code +
   `superpowers:brainstorming`, then **STOP and RETURN design questions +
   proposed approach — NO code/plan yet**. Impose the rails (below).
2. **Redline** its brainstorm against the decision log + the rails + the
   **North Star**. Answer every question; approve or redirect. Continue the
   SAME agent (context intact). **Write the redline decisions to the ledger
   now.**
3. Agent writes the plan (`superpowers:writing-plans`) and RETURNS it. **READ
   THE ACTUAL PLAN FILE — not the agent's summary.** (Reading artifacts is
   where you catch real bugs.) Redline; approve; ledger.
4. On approval the agent EXECUTES via
   `superpowers:subagent-driven-development` → opens a PR whose body says
   `Closes #<n>`.
5. **You independently validate + merge** (recipe in Step 2).

### Rails to impose on every dispatched agent
Ground-first; full superpowers flow; **DATA-SPIKE before building any
producer** (hand-make the input, run the REAL consumer, prove the gap closes +
neighbors don't break — falsifies wrong assumptions for ~0 cost); **TDD
watched-to-fail** (see it RED first); **keep generic core free of
environment/domain literals** — no input-specific format/name/technology
literal in generic code; that knowledge lives in a declared config/skill layer
and is surfaced as data; degrade gracefully, never hard-error on an unknown
input; consume-side invariants via a shared resolver; **fix at the ORIGIN
layer** (a bad downstream result is usually an upstream defect); **never
silently drop a gap** — record it; decision-log / ADR currency (amend the
governing decision in the SAME PR); follow the repo's commit/PR conventions
(including any attribution policy); `Closes #<n>` in the PR body; **never
mutate live/shared data** — copy/fork for any write; model tier per the plan;
**GATE INTEGRITY** — the worker may ADD its own TDD tests but must NEVER
weaken, delete, or edit the acceptance/DoD gate to make it pass; if the spec
and a gate contradict, or the task looks impossible, **STOP and flag it to
you** — never make a check green by gaming it (an explicit "flag impossible"
escape hatch sharply cuts cheating; gates the worker can't edit ≈ 0% cheat).

## Step 2 — The VALIDATE / MERGE recipe (never trust a self-report)
1. `git fetch origin pull/<n>/head:pr-<n>`. Check `gh pr view <n>` mergeable
   state (BLOCKED = review-required: in a **solo/owned repo** — you are the
   sole committer, or the user has said reviews don't apply — bypass with
   `--admin`; in a **shared repo, request review and wait — never bypass
   someone else's gate**. CONFLICTING = needs rebase, see Lessons).
2. Validate in an **ISOLATED `git worktree`** on `pr-<n>` — the shared tree
   flips branch↔main under you when sibling sessions work.
3. **Re-run the gates yourself**: the language build/test, every touched
   component's suite, lint/typecheck, and the issue's acceptance gate. Do not
   accept "X passed" — run it.
   **Gate-change adjudication:** when a worker *proposes changing* a
   gate/oracle/control (excluding residuals, re-basing a threshold),
   legitimate sharpening exists — adjudicate, don't reflex-block: (a) verify
   the change's **premise against live evidence yourself**, not the worker's
   table; (b) the gate must end **stricter or equal** — excluding
   newly-adjudicated items while keeping old thresholds is silent slack;
   re-base floors to the achieved values in the same landing; (c) every
   adjudicated exclusion carries its evidence-based **falsifier** so it
   re-opens when evidence changes; (d) the decision + rationale go in the PR
   body.
4. **Reproduce the real headline claim READ-ONLY** on real inputs to confirm
   the number; never mutate live/shared data (copy/fork for any write).
5. **Confirm**: the redline conditions were folded; the decision log / ADR
   was amended; invariants held; any removed concept is grep-clean;
   conventions followed; the diff is exactly the issue's scope.
6. Read the actual diff of the load-bearing files — mapping bugs,
   loop-control bugs, vacuous passes, and shared-file gaps hide behind green
   tests.
7. **Coverage probe — semantic gaming is the blind spot.** Enumerate every
   layer / output / capability the issue + DoD require and confirm each is
   *actually present* in the diff/artifact — by name, not "looks done."
   Scope-narrowing and silently-omitted outputs are exactly what automated
   review misses worst.
   **Instrument check:** when validation leans on a report/probe/oracle,
   confirm that instrument has been **seen RED on a known-bad fixture** (the
   plan archives these; children flagged `show-RED-before-first-use` MUST
   demonstrate the RED here, before their gate is trusted). A never-red
   instrument certifies nothing — a residue report once read "0 gaps" over an
   app that was all stubs.
8. **★ North Star drift gate (runs on EVERY child) ★** Before merging, ask:
   did this child move a piece from *uphill unknowns* to *downhill /
   derisked* and bring us **measurably closer to the North Star signal** —
   not just "is it green"? Watch for a gate vacuously passed or a
   goal-relevant output dropped. On a vacuous gate, a dropped output, or a
   relaxed guardrail, **STOP and surface it with a recommendation via the
   escalation ladder** (SKILL.md; `AskUserQuestion` only when the owner is
   present). **Scope-narrowing
   nuance:** narrowing that *still hits* the North Star signal is healthy
   (scope-hammering) — don't block it; STOP only when the narrowing
   **abandons** the signal. The honest fix often costs one more pass — take
   it. **A flipped regression control is triage, not auto-fail:** when a
   pinned "X unchanged" check flips, judge it against the control's stated
   premise + falsifier (the plan records these) — a control whose premise was
   wrong flips *because the fix works*; that's a finding to record, not a
   failure to revert.
9. Merge: `gh pr merge <n> --squash --delete-branch` (add `--admin` only
   under the solo-repo rule in item 1). Then handle the **worktree-delete
   gotcha**: if a worktree still holds the branch, `--delete-branch` silently
   skips the REMOTE delete → `git push origin --delete <branch>` directly +
   `git ls-remote --heads origin <branch>` to verify it's gone.
10. FF local main (`git fetch --prune` + `git merge --ff-only origin/main`).
    Remove your validation worktree. Close the child (the epic's sub-issue
    progress auto-updates). **Ledger checkpoint:** record the verdict, merge,
    gotchas found, and refreshed North Star / DoD status. Update the
    auto-memory pointer if the epic's traps changed. **Pane label (herdr):**
    recompute `(<merged>/<total>)` and re-apply the label.
11. **File follow-up issues** for non-blocking gaps you found. Distinguish
    DoD-blockers from hygiene; flag DoD-blockers loudly. Ledger them.

## Step 3 — The DoD demonstration (the finale)
Once the children are merged, prove the DoD as explicit work. The finale is a
DIFFERENT kind of work from the children: it **demonstrates shipped work on a
prepared substrate** (a fresh copy of real inputs, a fixture environment, a
staging deploy) — it is not a build front. Historically this is where runs
circle; run it as a gated drive: preflight → execute the whole chain →
adjudicate once.

### Finale preflight (BEFORE any fork/copy, long stage, or prerequisite work)
1. **Substrate viability.** For EVERY stage the demo will run, verify the
   substrate actually holds the inputs that stage consumes — count them with
   a cheap query/listing, don't assume. One missing input class makes the
   whole path structurally impossible: no downstream regeneration can conjure
   inputs absent upstream, and prerequisite work invested before this check
   is discovered worthless hours later. A substrate that can't carry a stage
   is a **substrate-strategy fork** — escalate it (ladder in SKILL.md); never
   build through it.
2. **Instrument freshness.** Rebuild every artifact/binary the demo shells
   out to (a stale compiled artifact silently runs pre-fix code and its REDs
   poison every downstream diagnosis); restart any shared service that
   predates the epic's merges.
3. **Chain plan with checkpoints.** Write down the stage list with one
   expected observable per stage, each placed BEFORE the expensive or
   destructive step it guards (verify preconditions before a delete/regen,
   not after the regen fails). Plan mode's finale contract carries these —
   read it; if it's missing, write it now before starting.
4. **External gate?** If the DoD is gated on something outside this epic
   (another epic's artifact, a third party), this epic cannot close this
   session: land what's landable, checkpoint, hand off deliberately (see
   Session lifecycle) — don't keep the session alive waiting.

### Execute (typical shape)
- Reproduce the end-to-end proof on a **fresh copy of real inputs** — never
  mutate live/shared data; copy/fork; scope any cleanup narrowly by
  owner/scope, NEVER by a shared/content key; verify the source is untouched.
- Re-run the pipeline / build to the target stage (the slow stage → run as a
  detached background job; arm BOTH a process-exit monitor AND a
  progress/hang timeout — the exit-monitor won't fire on a hang).
- Run the actual build/verify gates on the produced artifact (compile /
  migrate / boot / smoke).
- **Re-run the ORIGINAL acceptance/coverage check** that motivated the work,
  on the new output — the ultimate proof. Do the judgment-heavy comparison
  yourself.

### Adjudicate REDs — the anti-circling rules
- **Worse-before-better.** A demo that rebuilds derived state (replay,
  regeneration, migration) legitimately gets REDDER mid-chain — partial state
  fires more checks than the baseline until the full chain completes. Never
  judge an intermediate state against the final gate: execute the WHOLE
  chain, then measure once. ("Re-run → still RED → investigate → re-run" on
  intermediate states is the circling signature.)
- **Control-normalize every RED.** Run the IDENTICAL instrument on the
  pristine source the substrate came from: a RED line-identical to control is
  INHERITED, not your regression. Pinned thresholds carry the substrate they
  were calibrated on (plan mode records this); a threshold read on a
  different substrate shape is a calibration adjudication (Step 2 item 8),
  not a number to grind toward.
- **Silent no-ops.** A step that reports success while the state didn't
  change is a persistence no-op (idempotency guards, first-write-wins,
  resume-skips). Detect cheaply: run it twice — re-selecting the same items
  or bit-identical state = no-op; trace the persistence semantics before
  re-running anything again.
- **Prerequisite depth ≤ 1.** ONE origin-fix hop inside the finale is
  legitimate (fix at the origin; NEVER weaken the oracle). Discovering a
  SECOND prerequisite before the first has paid off means you are peeling an
  onion — STOP, re-verify substrate viability, escalate the strategy.
- **Same blocker twice = stop.** When the same root cause reappears in a new
  mask, further investigation is circling: write the decision brief (what's
  proven, what's blocked, options + evidence) and escalate per the ladder.
- **Close-out is owner-level.** When the demo is blocked by a newly
  discovered origin defect, "close on shipped value + file the defect" vs
  "fix first" is an owner-level fork — escalate it WITH the proven-signal
  evidence; do not re-attempt the blocked demo while it's undecided.

Confirm the proof **measurably hits the North Star signal**. Record the proof
AND every new trap discovered (ledger + memory/trap notes) BEFORE the session
ends — a finale whose lessons die with the session gets re-learned at the
next epic. Close the epic.
- **Pane label (herdr):** swap the counter for `✓` — `epic #<n> ✓`.

## Session lifecycle — how a run is allowed to end
A session ends in exactly ONE of three states:
1. **DoD proven + epic closed** (the goal);
2. **Deliberate handoff** — ledger checkpointed + a self-contained resume
   prompt (what's done, what's blocked, the exact next actions, the traps);
3. **Decision brief awaiting the owner** — only when the owner is present, or
   Fable was consulted and is itself unsure (ladder in SKILL.md).

**"Holding" is not a terminal state.** If the critical path is frozen by an
external reset (shared usage limit, quota window) and no off-path work
remains: checkpoint and END with a resume prompt — never sit idle waiting for
a reset, and never leave a blocking question as an unattended session's last
act.

**Budget admission control.** Workers, validators, and the orchestrator
usually share ONE account budget. Cap concurrent heavy workers; before
starting the finale, check remaining runway — a heavy demo chain started on a
nearly-drained budget dies mid-chain and wedges the substrate for the next
session.

## ★ LESSONS LEARNED (hard-won — internalize these) ★
1. **READ THE ARTIFACT, NOT THE SUMMARY.** Every real defect is caught by
   reading the actual plan file / PR diff, never the agent's prose: a loop
   that spins forever on a non-advancing item; a flag-name inconsistency that
   breaks the smoke; a slicer that handled 3 of 6 layers; a "no-diff → emit
   done" shortcut that *skipped the gate*. Summaries are confident and wrong.
   Open the file.
2. **"UNPROVEN DONE" IS THE ENEMY.** Watch for: a gate skipped/vacuous-passed,
   a layer/output silently omitted, scope narrowed without a decision. When
   you find one, decide block-vs-followup against the North Star; if it
   relaxes a guardrail or narrows the goal, **surface it to the human with a
   recommendation**.
3. **NAMED BACKGROUND AGENTS MAY STALL AT DISPATCH BOUNDARIES**
   (harness-dependent — verify current behavior before imposing sync-only
   rails; newer harnesses notify you when background agents finish).
   Historically the harness did NOT auto-continue them; they idled after each
   task/subagent and needed a poke. If you observe that: tell them to run
   their subagents **SYNCHRONOUSLY** (spawn, read the return in the SAME
   turn, act, continue — never dispatch-and-idle) and expect to poke once per
   task. Either way, **watch COMMIT TIMESTAMPS, not silence** —
   `git -C <worktree> log -1 --format=%cr` is ground truth. Their messages
   cross yours — re-state, verify state in git/the API rather than their
   claims.
4. **CONCURRENT BRANCHES OFF THE SAME BASE CONFLICT once a sibling merges.**
   Have workers rebase onto the new main the moment a sibling lands (or
   rebase + re-validate yourself in a temp worktree — usually small:
   decision-log appends, a shared registry/entry file).
5. **THE `--delete-branch` WORKTREE GOTCHA** (you WILL hit it):
   `gh pr merge --delete-branch` aborts the whole delete (remote too) when
   any worktree still holds the branch. Merge → `git worktree remove --force`
   the holder → `git push origin --delete <branch>` → verify remote is gone.
6. **VALIDATE IN AN ISOLATED WORKTREE.** Sibling build-sessions mutate the
   shared tree (HEAD flips branch↔main mid-validation). Always
   `git worktree add` on the fetched `pull/<n>/head`.
7. **KEEP GENERIC CORE FREE OF ENVIRONMENT LITERALS.** The seductive wrong
   fix is a literal / special-case / regex for one specific input in generic
   code. Reject it. Domain knowledge must be declared in a config/skill layer
   and surfaced as data; generic core stays literal-free; a new input must
   get the correct result; degrade gracefully. This may force a small,
   correct addition to the public API — that's not gold-plating.
8. **SCHEMA / CONTRACT CHANGES** need: the core registry + every synced copy
   (a sync gate should enforce it) + **a running service rebuilt with the new
   contract** for any live e2e (a stale running service will reject new
   records). Prefer riding a value in open/metadata over a new enumerated
   field when possible.
9. **DATA-SAFETY ON CLEANUP:** delete derived/generated data by
   **owner/scope**, NEVER by a shared/content key — shared keys span scopes,
   so a shared-key delete is a global nuke. Verify the source is untouched
   after any copy/fork cleanup.
10. **SLOW STAGES / INFRA FLAKES:** run long jobs detached with a poller; arm
    BOTH a process-exit monitor AND a progress/row-count timeout — a
    process-exit monitor will NOT catch a hang.
11. **DATA-SPIKE BEFORE A PRODUCER** repeatedly pays off — it falsifies wrong
    assumptions (the real slice key, the gate model, the shared-file
    recompute, the external API ergonomics) for ~0 cost before any plan. Make
    every producer-building agent spike first.
12. **DECISIONS YOU OWN, not the agents:** block-vs-followup; which layer
    owns a defect; whether a gate is honest; whether a slice advances the
    North Star. Agents implement; you judge. When you redline, lead with
    confirmations (don't re-litigate good work) then the load-bearing
    corrections.
13. **MODEL ROUTING:** use `choosing-a-model`. Default Opus; take each
    child's tier from the plan; escalate to Fable only when the child is
    itself high-complexity **and** high-blast (a keystone / gnarly root-cause
    usually is — a *trivial* keystone isn't); Sonnet/Haiku only for genuinely
    mechanical, gate-backed tasks. **Escalate reactively:** if a worker's
    cheaper-tier output fails your validation on *reasoning* grounds,
    re-dispatch a tier up rather than re-running. A quality miss on a
    keystone costs more than the model spend.
14. **KEEP THE LEDGER:** it is the resume point after compaction — checkpoint
    before every dispatch and after every verdict (see SKILL.md). Close the
    child on each merge (epic sub-issue progress auto-updates); refresh the
    North Star / DoD status; keep the auto-memory pointer current; prune
    merged branches/worktrees immediately (sweep orphans with
    `git worktree list`). **And when execution falsifies a premise in ANY
    open issue body** — a number that doesn't reproduce, a mechanism that
    isn't what the body claims, a control that isn't what it was assumed to
    be — correct that body (or comment prominently) in the same landing and
    re-check every child scoped on it. Reconcile, don't accrete: dependent
    children built on a falsified premise are the next epic's defects.
15. **MERGED ≠ MATERIALIZED.** When a child fixes a *producer of
    derived/stored data*, the merge leaves every existing derivation stale —
    the old snapshot keeps asserting the defect the code no longer has, and
    downstream consumers read it as current truth (a topology fix merged
    while the stored `deployment_unit` still said "frontend, owns no
    tables"). Either re-derive promptly or mark the affected records "stale
    until re-derivation" in the epic status; validation headline claims and
    the DoD proof must run on **re-derived state**, never the pre-fix
    snapshot.

## Definition of done for the run
All children merged + validated + closed (epic sub-issue progress at 100%),
the **DoD demonstration executed and the original acceptance proof re-run
green on the produced artifact**, the **North Star signal measurably hit** (or
drift surfaced and decided with the human), follow-ups filed for tracked gaps,
the ledger's final state recorded, and the tree clean (no orphan
branches/worktrees). Report the proof, not just the merges. For a single
issue: merged + validated + closed, its acceptance gate re-run green on main,
its stated signal confirmed.

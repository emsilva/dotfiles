# /ship run — orchestrate work to a proven result

The argument is `<epic#>`, `<issue#>`, or `<path/to/contract.md>`. If absent,
ask for it. You are the **orchestrator — never the owner** (the owner is the
human this run answers to): you DISPATCH worker agents to implement each
chunk and you INDEPENDENTLY validate + land their work within the authority
envelope. You write no feature code yourself — you dispatch, redline,
validate, and decide (within the ladder's "Yours" class).

The **epic issue is the contract**: it carries the North Star, the build
order and per-child acceptance gates. The **ledger**
(schema in SKILL.md) carries the run's state.

## Resolve the target (facts, not argument shape)
- **Number** → `gh issue view <n>`: epic label / sub-issues present → it's an
  **epic**; otherwise it's a **single issue** (see "Single issue? The short
  loop" below).
- **Path** → a local contract file (delivery_mode `local-review`, or plan's
  no-`gh` fallback) — a first-class mode, not a stand-in awaiting GitHub.
  Its `ship:contract` marker is the classifier: `kind=epic` → everything
  below; `kind=single` → the short loop; `status` must be `active`
  (`completed` = done, never re-run). A local contract stays canonical for
  its ENTIRE lifecycle — publishing it to GitHub is a separate engagement
  (plan.md Step 5), never a redirect.
  Children and the ledger live in the file; track state via TaskList + the
  file's `## Ledger` section. Everything below applies with "issue body" ↦
  "file section", "ledger comment" ↦ "`## Ledger` section", and Step 2's
  items 1–2/9/10 plumbing ↦ the **local-review plumbing** (in Step 2); skip
  sub-issue closes; follow-ups (item 11) append to the contract file's
  `## Follow-ups` instead of `gh issue create`.

## Pane label (herdr) — live progress at a glance
Inside herdr (`HERDR_ENV=1`), keep THIS pane's label in sync with the run so
the herd sidebar reads as a progress board. **Best-effort, non-fatal** — a
cosmetic label must never block or fail a run: guard on `HERDR_ENV`, resolve
the pane id at runtime, swallow errors. The label is a **derived view of the
ledger** (recomputed from merged/total each time — never a separately tracked
counter), so it is correct on resume and cannot drift.

- **Epic, running:** `epic #<n> (<merged>/<total>)` — `<merged>` = children in
  state `merged` (owner-gate children count when `accepted`); `<total>` = all
  children (in-flight children count as not-done).
- **Epic, all children merged, DoD finale not yet proven:** `epic #<n> (N/N)` —
  `(N/N)` does NOT mean done (merged ≠ done; the DoD demo is still owed).
- **Epic, DoD proven + epic closed:** `epic #<n> ✓`. Closure-owed + handed
  off → `epic #<n> ✓ closes-owed` — NEVER a bare checkmark while closes
  are owed.
- **Single issue:** `#<n> (<done>/<total>)` when the issue carries an internal
  task plan — `<done>` = tasks committed on the branch, recomputed from git each
  time, never a hand-tracked counter. Bare `#<n>` only when there is no internal
  plan. Either way → `#<n> ✓` once its gate re-runs green on the merged
  base (local-review: the integration branch); with its close owed,
  `#<n> ✓ closes-owed` — never a bare checkmark.

Write it at three points: **Step 0** after the ledger↔ground-truth
reconciliation (from the reconciled merged count); **after each landing** —
gh: item 10's ledger checkpoint; local-review: plumbing item 3, right
after the ff (recompute + re-apply); **Step 3**
when the DoD is proven — swap the counter for `✓` (closed), or
`✓ closes-owed` when closures are owed. Quote
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
   each child's acceptance gate. Read every child issue. Note
   `blocked-by` / `depends-on`.
2. Read the **ledger** — gh modes: locate the epic comment BY its
   `<!-- ship:ledger -->` sentinel, never "the first comment"; local-review:
   derive the integration branch from the contract's plan-id
   (`<plan-id>-integration` — deterministic, no circular lookup) and read
   the contract file from THAT branch (the canonical ref), never whatever
   the shared tree happens to have checked out. If no ledger exists, seed
   it (all children `queued`). Load its `policy:` line — the CANONICAL
   authority envelope (the spec's copy is a plan-time snapshot; never
   consult it after seeding) — into working state: every outward write
   below NAMES its action (SKILL.md's list) and runs ONLY if the envelope
   lists it; anything unlisted takes its stated fallback and is reported in
   the handoff. Run SKILL.md's coherence check — a delivery_mode missing
   its minimum action set is a MALFORMED envelope: surface it now, never
   discover it mid-run. A pre-envelope plan lacks one → derive + record it
   NOW, before any dispatch. **First start only:** gh modes — record
   `baseline: <sha>` = the default branch's current HEAD. local-review — if
   the integration branch doesn't exist yet (legacy contract), create it
   from the default branch's current HEAD, commit the contract file onto
   it, and record its name in the policy line's `integration_branch`; then
   record
   `baseline: <sha>` = that branch's HEAD. The baseline is the immutable
   review base for the whole run; a tag is optional convenience — the
   recorded SHA is the authority.
3. **Reconcile ledger vs ground truth — ground truth wins.** Check: sub-issue
   open/closed states, `gh pr list --state all --limit 200` (PRs referencing
   children — the open/30 default hides merged and closed ones),
   `git worktree list` (stale validation/worker worktrees), TaskList. A PR
   counts as MERGED only when its merge commit is reachable on its ACTUAL
   base — fetch the base FIRST into a private ref (`gh pr view <url>
   --json url,baseRefName,mergeCommit` — base repo derived from `url`,
   Step 2 item 1; `git fetch <base-remote>
   "+refs/heads/<BASE>:refs/ship/base-<n>"`; then
   `git merge-base --is-ancestor <mergeCommit> refs/ship/base-<n>`; a
   stale ref falsifies reachability) — never from
   issue closure or an open-only listing. Reachability proves LANDED, not
   ACCEPTED: acceptance evidence is item 10's published landing record
   (recorded head/base/composition or merge-group identity + verdict); if
   that record is missing for a landed PR, reconstruct and validate the
   HISTORICAL landed composition from the actual `mergeCommit` — never
   rebuild the PR against today's base and call reachability acceptance. Correct the ledger to match
   reality. In local-review mode ground truth is child branches/worktrees +
   merge ANCESTRY (`git merge-base --is-ancestor`), not PRs.
4. **Quiesce prior-session workers FIRST.** A crashed or cleared session's
   workers may have been auto-resumed by the environment (e.g. herdr) and
   still be writing. Before dispatching ANY fresh worker, establish who is
   actually writing each worktree from process facts — `lsof +D <path>` /
   `pgrep -lf <path>` plus the agent/pane list — NEVER from commit/reflog
   cadence (a clean single-threaded reflog does not prove a single writer).
   Adopt, stop, or wait out each zombie before re-dispatching its child.
   Also probe for a second LIVE ORCHESTRATOR on this epic (agent/pane list;
   `lsof` on the epic file/ledger): two orchestrators on one ledger is
   last-write-wins corruption — adopt, stop, or hand off before proceeding.
5. Read the repo's standing rules (`CLAUDE.md` / `AGENTS.md` / contributing
   guide) — your redline checklist — and the committed decision log / spec
   (often under `docs/`) plus any auto-memory pointer for the epic.
6. Rebuild the TaskList if missing: one task per child + one for the DoD
   demonstration, `blockedBy` edges from the build order.
7. **Resume each child from its actual state:**
   - **A PR exists → NEVER dispatch a new worker for it** — validate that PR
     (Step 2), whatever the ledger or your instincts say. Local-review
     analogue: a child branch/worktree WITH COMMITS exists → validate that
     head (Step 2), never re-dispatch; confirm ledger `commit(<sha>)` /
     merged states by ancestry, not by tree appearance.
   - Ledger says dispatched/executing and the named agent is alive → continue
     that agent (poke it; verify progress via commit timestamps, not claims).
   - Dispatched but the agent is gone — a failed SendMessage ("not reachable")
     is the definitive liveness probe; commit silence is only a hint →
     re-dispatch, **inlining the ledger's redline decisions** so the new worker
     inherits them. A dead worker often leaves FINISHED-BUT-UNCOMMITTED work in
     its worktree: verify it green YOURSELF first, then have the successor
     diff-review-and-commit the orphan against the ledgered rulings — credit
     verified work, never redo it.
   - Queued and unblocked → dispatch (Step 1).
   - An **`owner-gate`** child (plan.md) never gets a worker dispatched at
     its acceptance: when its input (draft, evidence, recommendation) is
     ready, park it `awaiting-owner(<gate>)` — dependents stay blocked
     (ladder in SKILL.md). On resume, check for the owner's decision: an
     explicit acceptance — verify PROVENANCE, not mere existence: the
     record must be OWNER-authored (attributable actor + channel) and
     immutably referenced; an agent-authored record may QUOTE an owner
     statement but can never itself supply acceptance — advances the
     ledger to `accepted(<record/ref>)` and
     unblocks dependents; a rejection routes to re-plan (reshape or drop
     dependents via the ladder).
8. Remove stale validation worktrees left by prior sessions — AFTER
   checking each for unharvested evidence or an unlanded composition
   (recover per the plumbing's crash rules first; deleting an unharvested
   worktree destroys the only copy).
9. **Pane label (herdr):** set this pane's label from the reconciled merged
   count — see "Pane label (herdr)" above.

Redline decisions from a lost session exist **only** if the ledger has them —
that is why checkpoint discipline (SKILL.md) is non-negotiable.

## Single issue? The short loop
An **`owner-gate`** single (plan.md) skips the loop entirely — no worker,
no landing, no fake gate: prepare its draft/evidence, park it
`awaiting-owner(<gate>)`, and advance ONLY per Step 0 item 7's owner-gate
rules (accepted → record the provenance + close under `issue-close` / flip
the completed marker; rejected → re-plan; owed close → state-2 handoff).
For a single well-gated CODE issue (no children): run the per-issue loop
(Step 1)
for just that issue, then the full validate/merge recipe (Step 2). The ledger
lives as a comment on the issue itself (same `<!-- ship:ledger -->` sentinel
discipline); a local-review single's ledger is its contract file's
`## Ledger` section — not a comment. The finale degenerates to: **re-run
the issue's acceptance gate
on the merged base** (local-review: on the integration branch) and confirm the
issue's stated goal/how-we'll-know signal — then, local-review, flip the
contract marker to `status=completed` in the final checkpoint. Everything
else below applies unchanged.

## Step 1 — The per-issue agent loop
For each child, run this loop (dispatch INDEPENDENT issues in PARALLEL —
separate named agents in one message; the long-pole / integration issue goes
LAST):

**Collision preflight before every dispatch:** check `git worktree list`,
open PRs, and the sibling issues' scopes for work already covering this
child's defect — this workflow has dispatched two agents at ONE fix under two
issues before. One defect = one child; if two children turn out to share a
fix, re-scope before dispatching, and HOLD if a "proceed" instruction crosses
your collision flag. **Ledger checkpoint:** record the dispatch (agent name)
before it happens.

1. **Dispatch** a worker `Agent`. Give it a `name` so you can continue it.
   Local-review: YOU create its workspace first —
   `git worktree add <path> -b <child-branch> <integration-tip>` — and hand
   it the path; workers never invent branches, and the child roots at the
   tip it must land on. Tell it: ground vs current code +
   `superpowers:brainstorming`, then **STOP and RETURN design questions +
   proposed approach — NO code/plan yet**. Impose the rails (below).
2. **Redline** its brainstorm against the decision log + the rails + the
   **North Star**. **Verify each load-bearing claim in the brief against the
   code yourself before ruling** — a plausible brief with one wrong premise
   ("X doesn't exist", "Y is LLM-backed") redirects the whole design; grep the
   claims, not just the prose. Answer every question; approve or redirect.
   Continue the SAME agent (context intact). **Write the redline decisions to
   the ledger now.**
3. Agent writes the plan (`superpowers:writing-plans`) and RETURNS it. **READ
   THE ACTUAL PLAN FILE — not the agent's summary.** (Reading artifacts is
   where you catch real bugs.) Redline; approve; ledger.
4. On approval the agent EXECUTES via
   `superpowers:subagent-driven-development` → delivers per delivery_mode:
   gh modes — a PR (`push` + `pr-create`; the mode's minimum action set,
   verified at Step 0 — never discovered here) whose body says the
   NON-CLOSING `Refs #<n>` — ALWAYS, regardless of `issue-close`
   authority: closing keywords close at merge, BEFORE item 10's landing
   record is durable, so they are forbidden in this workflow;
   `issue-close` is exercised only by item 10's explicit post-publication
   close. The worker reports
   the PR's FULL URL — the ledger records it, and it is the PR's identity
   from then on; local-review — the
   finished child branch + head SHA (no push, no PR).
5. **You independently validate + merge** (recipe in Step 2).

### Rails to impose on every dispatched agent
The repo's standing rules and the run's authority envelope OVERRIDE these
generic rails wherever they conflict. Ground-first; full superpowers flow;
**one worktree per writer, never the shared checkout** — use the workspace the
dispatch handed you, otherwise create your own (`superpowers:using-git-worktrees`)
rooted at the tip you must land on, and leave its removal to the orchestrator;
**DATA-SPIKE before building any producer** (hand-make the input, run the
REAL consumer, prove the gap closes + neighbors don't break — falsifies wrong
assumptions for ~0 cost); **TDD watched-to-fail** (see it RED first); **where
the repo or the child's spec declares a layer generic, keep it literal-free**
— no input-specific format/name/technology literal there; that knowledge
lives in a declared config/skill layer, surfaced as data (the DECLARATION
decides what counts as generic, never the worker's own classification);
follow the governing contract — **never silently drop, repair, or
reinterpret unknown input**; when the repo declares execution / authority /
regime fields for work items, every child carries them (the repo defines the
taxonomy, not this skill); **fix at the ORIGIN layer** (a bad downstream
result is usually an upstream defect); **never silently drop a gap** —
record it; decision-log / ADR currency (amend the governing decision in the
SAME PR); follow the repo's commit/PR conventions (including any attribution
policy); delivery per delivery_mode — gh modes: the non-closing
`Refs #<n>` in the PR body (closing keywords are FORBIDDEN — they close
before the landing record is durable); local-review: child branch + head
SHA, no push, no PR; **never
mutate live/shared data** — copy/fork for any write;
**GATE INTEGRITY** — the worker may ADD its own TDD tests but must NEVER
weaken, delete, or edit the acceptance/DoD gate to make it pass; if the spec
and a gate contradict, or the task looks impossible, **STOP and flag it to
you** — never make a check green by gaming it (an explicit "flag impossible"
escape hatch sharply cuts cheating; gates the worker can't edit ≈ 0% cheat).

## Step 2 — The VALIDATE / MERGE recipe (never trust a self-report)
1. The PR's identity is its FULL URL (ledgered at delivery) — EVERY
   `gh pr` query or mutation below uses the URL, or explicit
   `-R <base-owner>/<repo> <n>`; never an unscoped number (the same
   number in the wrong repo is someone else's PR). Resolve the ACTUAL
   base repository and ref first —
   `gh pr view <url> --json url,baseRefName,headRefOid`: a PR lives IN its
   base repository, so derive owner/repo from `url` (strip `/pull/<n>`;
   plain `--json` exposes no baseRepository field — query GraphQL
   explicitly if you need it structured). The base
   repo may not be `origin` (fork/upstream layouts): pick the remote that
   matches it, or use the repository URL explicitly — call it
   `<base-remote>`; never assume `main` or that the base is checked out
   anywhere. Fetch with explicit FORCED destination refspecs into private
   refs: `git fetch <base-remote>
   "+refs/heads/<BASE>:refs/ship/base-<n>"
   "+refs/pull/<n>/head:refs/ship/pr-<n>"` — the `+` force-updates the
   disposable refs (a rewritten head otherwise wedges a stale local copy).
   Record the **validated head OID** (`git rev-parse refs/ship/pr-<n>`,
   cross-checked against `headRefOid`) AND the **fresh base tip OID**
   (`git rev-parse refs/ship/base-<n>` — only AFTER that fetch; a stale
   ref is not a recording); use these `refs/ship/*` refs in EVERY later
   step — resume, pre-land, post-land, reachability. Validation binds to
   this exact
   would-land COMPOSITION, not the head alone (`--match-head-commit` cannot
   bind a moving base). Check
   `gh pr view <url>` mergeable state (BLOCKED = review-required: bypass with
   `--admin` ONLY when the envelope lists `admin-bypass` AND
   `landing_authority` records the explicit owner waiver — both keys, one
   decision; sole-committer status is NEVER sufficient, and an
   unavailable reviewer is a deferral, not a waiver; otherwise **request
   review (`review-request`; unlisted → don't request: ledger the block and
   end at `stop_at` as state 2) and wait — never bypass someone else's
   gate**.
   CONFLICTING = needs
   rebase, see Lessons). A
   third-party check wedged `pending` on a diff outside its scope (e.g. a
   dependency scanner on a zero-dep-delta diff) is an adjudication to record,
   not a merge blocker — the repo's own build/test checks are the gate.
2. Validate in an **ISOLATED `git worktree`**: check out the recorded base
   tip (detached) and merge `refs/ship/pr-<n>` into it (a conflict = needs
   rebase, see
   Lessons) — items 3–8 run on THIS would-land composition, never on the
   head alone. Record the **validated composition TREE OID**
   (`git rev-parse HEAD^{tree}` in that worktree) — the post-land identity
   check compares against it. Isolation matters: the shared tree
   flips branches under you when sibling sessions work.
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
   body (`pr-edit`; unauthorized → in the ledger checkpoint instead).
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
   app that was all stubs. When you run a revert-RED yourself, **prove the
   revert took** (ls / git status the reverted file) before trusting the
   result — `git stash` no-ops silently on a committed-clean file and
   certifies the unreverted code.
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
8b. **Gates red? → `rework`, not a re-dispatch.** Items 3–8 failing is the
   ORDINARY outcome, not an exception — give it a state or it has none.
   Ledger `rework(<the specific failures>)` naming what actually failed
   (the gate, the unfolded redline, the coverage hole), then continue the
   SAME agent with those failures — it holds the context that produced
   them. Agent gone → re-dispatch onto the **existing** branch, never a
   new one; a second branch off the same base re-earns Lesson 4's
   conflict. Do NOT advance to item 9 with a red child, and do NOT leave
   the ledger reading `PR#<m>` — after a compaction that reads as
   "delivered, not yet validated", and the resumed session re-runs every
   gate from scratch having lost the failures you already found. Loop back
   to item 3 when the agent redelivers; the count of rework rounds is
   itself signal for the North Star gate at item 8.
9. Land — THREE keys, set at Step 0 coherence and RE-CHECKED here: `merge`
   in `authorized_external_actions` (delivery_mode `github-merge` is shape;
   it authorizes nothing); `landing_authority` NAMES YOU as the lander for
   this child; and `stop_at` does not bound the run before landing (e.g.
   review-ready). In `github-pr` mode, or with any key missing, skip the
   landing and item 10's post-merge plumbing: ledger the child `validated`
   (checkpoint discipline and item 11's follow-ups still apply), leave the
   PR for the authorized lander, and end the run at its `stop_at` boundary
   as a deliberate handoff. **Self-landing — immediate OR queued — has one
   more precondition: PROVIDER-ENFORCED proof on the exact landing
   composition.** The repo's required checks must run the full committed
   acceptance battery on the current test-merge / merge-group composition
   with strict up-to-date semantics — your own pre-land re-fetch NARROWS
   the base race; only provider-side enforcement CLOSES it. Cannot prove
   that configuration → do NOT self-land: stop at `validated` /
   review-ready, state 2. Merge queue / auto-merge enrollment is
   additionally a DISTINCT persistent write — `queue-enqueue` — permitted
   only when authorized. Landing: re-fetch the base into its private ref
   (`git fetch <base-remote> "+refs/heads/<BASE>:refs/ship/base-<n>"`) and
   re-check its tip IMMEDIATELY before landing — never compare a stale
   ref; moved → a sibling landed under you: redo the composition
   validation (item 1) first. Record the **PROVIDER-VALIDATED landing
   identity** — immediate landing: the provider's CURRENT test-merge
   composition (e.g. GraphQL `potentialMergeCommit`); verify its tree
   EQUALS your locally validated composition tree BEFORE merging (differs
   → validate the provider composition via items 3–8, or stop at
   `validated`); queued landing: the merge-group head/tree the queue's
   checks actually tested. Then:
   `gh pr merge <url> --squash --match-head-commit <validated-head-OID>`
   — NEVER pass `--delete-branch`: deletion inside the merge call precedes
   item 10's landing record; head-branch deletion is item 10's explicit
   post-publication step — with `--admin` only under the two-key rule in
   item 1. A refusal = the head moved — revalidate (item 1). If enqueued:
   poll `gh pr view <url> --json state,mergedAt,mergeCommit` until the PR
   is actually MERGED (queue rejection = a failed landing — investigate,
   don't assume). **Post-land identity check — a VERIFICATION, never a
   substitute for pre-land proof:** re-fetch the base ref, take the actual
   `mergeCommit`, and compare its tree against the recorded
   provider-validated landing identity (immediate: the test-merge
   composition; queued: the merge-group — a normal queue rebase is NOT
   an incident). Match → record validated + merged (+ closed only under
   `issue-close`, after item 10's publication). ANY unexpected mismatch
   against that identity is an INCIDENT — something landed that
   was never validated: ledger it and escalate per the ladder; run the
   full battery (items 3–8) on the landed tree as incident RESPONSE
   (green bounds the damage; red = a broken base — stop everything);
   merged only after the incident adjudication.
10. **PUBLISH the landing record FIRST — gh crash-safety.** Before any
    cleanup or close, make the verdict durable: the ledger checkpoint
    (`issue-comment`) carrying the recorded head / base / composition-tree
    OIDs (or the provider-validated merge-group identity), the gate
    verdict, the actual landed `mergeCommit`, gotchas found, and the
    refreshed North Star / DoD status; gate evidence goes to its durable
    path (plumbing item 5) — each write under its named action; anything
    unauthorized → the committed-AND-pushed local fallback (plan Step 4's
    publication rule) or publication-owed + hand off. Only AFTER the
    record is durable: FF your local checkout of the base branch, if one
    exists (re-fetch into `refs/ship/base-<n>` +
    `git merge --ff-only refs/ship/base-<n>` from within it — never assume
    the base is checked out anywhere); remove your validation worktree;
    delete the head branch ONLY under `remote-delete` — first
    remove/salvage any worktree still holding it (clean only, never
    `--force` a dirty tree), then
    `git push <head-remote> --delete <branch>` (head repo from
    `headRepository` — usually `origin` for your own PRs) and verify
    `git ls-remote --heads <head-remote> <branch>` returns nothing;
    unauthorized → retain + report. Then
    close the child (`issue-close`;
    unauthorized → ledger the closure as owed and report it) — the epic's
    sub-issue progress auto-updates. Update the
    auto-memory pointer if the epic's traps changed. **Pane label (herdr):**
    recompute `(<merged>/<total>)` and re-apply the label.
11. **File follow-up issues** for non-blocking gaps you found
    (`issue-create`; unauthorized → append them to the committed
    spec / contract file's `## Follow-ups`, COMMIT the append, and ledger
    them). Distinguish
    DoD-blockers from hygiene; flag DoD-blockers loudly. Ledger them.

### Local-review plumbing (replaces items 1–2, 9, 10; the generic battery —
items 3–8 — runs on the composition built below)
1. The worker delivered `<child-branch>` + head SHA (its worktree was
   created at dispatch — Step 1). Record the **validated head OID** AND the
   **integration tip OID**; in an isolated worktree, check out the tip and
   `git merge --no-ff <head-oid>` to BUILD the exact would-land
   composition; run items 3–8 on it. Ledger `validated` only after the
   composition is green — a child head green on its own branch proves
   nothing about landing on an advanced tip.
2. **Complete the LANDING UNIT in the composition worktree** (before any
   landing): harvest gate output / RED archives / headline reproductions
   into `evidence_home`, update the contract file's `## Ledger`
   (`commit(<head-sha>)` + the merge SHA → `merged`), and commit BOTH on
   top of the merge commit — then RE-RUN the repository's full/applicable
   gate on this EXACT final commit (the evidence/ledger additions changed
   the tree; only the post-publication commit is `validated` and
   landable). The landing unit = code + evidence + ledger,
   one atomic fast-forward target — a crash before landing leaves NOTHING
   landed (everything recoverable in the worktree; Step 0 item 8 never
   deletes it unharvested), a crash after leaves everything landed
   together: no window with merged ancestry and a stale ledger or orphaned
   evidence.
3. Land by fast-forward — TWO landing keys apply locally
   (`landing_authority` names you; `stop_at` doesn't bound pre-landing —
   item 9's `merge`/`queue-enqueue` keys are GitHub actions; the local
   merge is not an external write): **name the checkout — item 1's
   composition worktree is at a DETACHED tip, and an ff there advances
   HEAD while the integration branch ref stays put, so the ff "succeeds"
   and nothing lands.** Add a worktree ON the integration branch
   (`git worktree add <path> <integration-branch>`) and ff there:
   `git merge --ff-only <landing-unit-sha>` — the landed unit IS
   the validated one, bit-for-bit, and ff-only REFUSES if the tip moved
   since validation (a sibling landed): rebuild the composition on the new
   tip and revalidate; never land what you didn't validate. NO squash —
   merge ancestry IS the per-slice review record (baseline→HEAD, one
   `--no-ff` merge per slice). Either key missing → stop at `validated`,
   state-2 handoff at the boundary. After the ff: recompute the pane
   label, THEN remove the composition worktree.
4. Verify reachability — `git merge-base --is-ancestor <head-sha>
   <integration-branch>` — THEN remove the child worktree and delete the
   child branch (ancestry preserves its history; retention is unnecessary).
   Never force-remove a dirty worktree: dirty = unharvested work — stop and
   salvage first (Step 0 item 7's orphan rule).
5. Evidence lives in `evidence_home`, referenced from the ledger line;
   follow-ups append to the contract file's `## Follow-ups`. EVERY local
   append — follow-ups, journal, decision records, any gh-mode fallback —
   is COMMITTED in its checkpoint; an uncommitted fallback is one
   tree-reset from gone. gh modes give gate evidence a durable path too:
   archive it on the PR/issue (`issue-comment`) or in the pushed contract
   ref (plan Step 4's publication rule — every later checkpoint is
   committed AND pushed and verified fetchable; `push` unauthorized →
   publication-owed + hand off).

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
   predates the epic's merges. Verify the rebuilt artifact's identity by
   **behavior** (a capability only the new build has), never by its
   self-reported build/version stamp — stamps can derive from the wrong
   source tree and produce false-stale AND false-fresh verdicts.
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
  mutate live/shared data; copy/fork; scope any cleanup narrowly by the
  owning scope, never by a key shared across scopes; verify the source is
  untouched.
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
  different substrate shape is a calibration adjudication (Step 2 item 3's
  gate-change adjudication), not a number to grind toward.
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
next epic. Close the epic (gh: `issue-close`; unauthorized → report it as
owed). Local-review: flip the contract marker to `status=completed` in the
same final checkpoint — scout stops surveying it.
- **Pane label (herdr):** swap the counter for `✓` — `epic #<n> ✓`; with
  closes owed, `epic #<n> ✓ closes-owed`, never a bare checkmark.

## Session lifecycle — how a run is allowed to end
Whichever state it ends in, the session FIRST delivers the run review +
skill feedback loop (SKILL.md) — states 2 and 3 especially: that is when the
owner most needs the recap. Unattended sessions ALSO record the
release-notes review durably — local-review: the contract file's
`## Journal`; gh modes: a comment on the epic/issue (`issue-comment`;
unauthorized → append to the committed spec AND commit the append) — a
recap that lives only in
the transcript never reaches the owner. A session ends in exactly ONE of
three states:
1. **DoD proven + epic closed** (the goal) — gh: reachable only when the
   authorized closes actually happened; anything closure-owed ends as
   state 2 with the owed closes listed, never a claimed close;
2. **Deliberate handoff** — ledger checkpointed + a self-contained resume
   prompt (what's done, what's blocked, the exact next actions, the traps).
   Also the CORRECT unattended terminal for a parked owner-reserved gate
   (`awaiting-owner(<gate>)`) and for reaching the envelope's `stop_at`
   boundary (e.g. review-ready);
3. **Decision brief awaiting the owner** — only when the owner is present, or
   Fable was consulted and is itself unsure (ladder in SKILL.md; never for
   owner-reserved gates, which park via state 2).

**"Holding" is not a terminal state.** If the critical path is frozen by an
external reset (shared usage limit, quota window) and no off-path work
remains: checkpoint and END with a resume prompt — never sit idle waiting for
a reset, and never leave a blocking question as an unattended session's last
act (a parked owner-reserved gate ends as state 2's handoff, not as a
question).

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
   Have workers rebase onto the new base tip the moment a sibling lands (or
   rebase + re-validate yourself in a temp worktree — usually small:
   decision-log appends, a shared registry/entry file).
5. **HEAD-BRANCH DELETION IS ITEM 10's EXPLICIT POST-PUBLICATION STEP.**
   Never pass `--delete-branch` to `gh pr merge`: it deletes inside the
   merge call, BEFORE the landing record is durable — and historically it
   also silently aborted the remote delete whenever any worktree still
   held the branch. ONE authority: item 10 (holder worktree first —
   clean/salvaged, never `--force` — then the `remote-delete`-gated
   push-delete, then `ls-remote` verification).
6. **VALIDATE IN AN ISOLATED WORKTREE.** Sibling build-sessions mutate the
   shared tree (HEAD flips branches mid-validation). Always
   `git worktree add` a dedicated worktree and build the would-land
   COMPOSITION there (Step 2 items 1–2) — never validate in the shared
   tree, and never on the head alone.
7. **KEEP A DECLARED-GENERIC LAYER FREE OF ENVIRONMENT LITERALS.** The
   seductive wrong fix is a literal / special-case / regex for one specific
   input in code the repo or the child's spec declares generic. Reject it. Domain knowledge must
   be declared in a config/skill layer and surfaced as data; the declared
   layer stays literal-free; a new input must get the correct,
   contract-directed result. This may force a small, correct addition to the
   public API — that's not gold-plating.
8. **SCHEMA / CONTRACT CHANGES** — when the repo keeps a schema/contract
   registry with synced copies: update the registry + every synced copy (a
   sync gate should enforce it). When a live service consumes the contract:
   rebuild/restart it for any live e2e (a stale running service will reject
   new records). Where the repo's schema-evolution policy permits, prefer
   riding a value in open/metadata over a new enumerated field — never use
   it to dodge typed schema evolution.
9. **DATA-SAFETY ON CLEANUP** — when cleanup deletes derived/generated
   data: delete by the OWNING scope, never by a key shared across scopes —
   a shared-key delete is a global nuke. Verify the source is untouched
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
13. **KEEP THE LEDGER:** it is the resume point after compaction — checkpoint
    before every dispatch and after every verdict (see SKILL.md). Close the
    child on each merge (`issue-close`; unauthorized → owed + reported —
    sub-issue progress advances only on real closes); refresh the
    North Star / DoD status; keep the auto-memory pointer current; prune
    merged branches/worktrees immediately (sweep orphans with
    `git worktree list`). **And when execution falsifies a premise in ANY
    open issue body** — a number that doesn't reproduce, a mechanism that
    isn't what the body claims, a control that isn't what it was assumed to
    be — correct that body (`issue-edit`) or comment prominently
    (`issue-comment`) in the same landing — unauthorized → record the
    correction in the ledger/spec and mark the body fix OWED — and
    re-check every child scoped on it. Reconcile, don't accrete: dependent
    children built on a falsified premise are the next epic's defects.
14. **TEAMMATE IDLE NOTIFICATIONS ARE STALE AND RACY.** They fire per stop and
    routinely predate your last send (sends resume idle agents from their
    transcript). On an idle event: timestamp-compare it against your last
    message, ground-check cheaply (commits, dirty files, task outputs), and
    poke AT MOST once on evidence of non-consumption — poke-spam burns worker
    turns and your own context.
15. **INTENTIONAL RED WINDOWS (red-on-unwired).** When a change legitimately
    trips cross-cutting derivation guards until a later task wires them,
    don't stub them green and don't hold the branch: ledger the EXACT
    expected red set + its shrink schedule, require every per-task report to
    assert the full red set equals expectation (this is what catches the
    guard nobody predicted), name the intentional reds in the commit body,
    and witness the green flip when the wiring lands. Any red outside the
    ledgered set = stop.
16. **MERGED ≠ MATERIALIZED.** When a child fixes a *producer of
    derived/stored data*, the merge leaves every existing derivation stale —
    the old snapshot keeps asserting the defect the code no longer has, and
    downstream consumers read it as current truth (e.g. a fix merged while
    a stored derived record still asserted the pre-fix
    state). Either re-derive promptly or mark the affected records "stale
    until re-derivation" in the epic status; validation headline claims and
    the DoD proof must run on **re-derived state**, never the pre-fix
    snapshot.

## Definition of done for the run
All code children merged + validated — and closed where `issue-close` is
authorized: sub-issue progress reaches 100% only through REAL authorized
closes (always item 10's explicit post-publication close — never closing
keywords); owed closures are listed in the handoff and force state 2, never a
claimed 100% — every owner-gate child `accepted(<record/ref>)` (done at
accepted, never "merged"; in gh its issue closes under `issue-close` or
stays closure-owed; a rejected one has been re-planned), the **DoD
demonstration executed and the original acceptance proof re-run
green on the produced artifact**, the **North Star signal measurably hit** (or
drift surfaced and decided with the human), follow-ups filed for tracked gaps,
the ledger's final state recorded, the tree clean (no orphan
branches/worktrees), and — local-review, where no "closed" exists —
children complete at validated+merged with the contract marker flipped to
`status=completed`. Report the proof, not just the merges. For a single
issue: merged + validated (+ closed under `issue-close`), its acceptance
gate re-run green on the merged base
(local-review: on the integration branch), its stated signal confirmed.

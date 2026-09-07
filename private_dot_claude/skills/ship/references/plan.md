# /ship plan — turn an idea into provable, ready-to-run work

The deliverable depends on size (Step 2): **one chunk → ONE well-gated issue;
two-plus chunks → an epic contract (GitHub epic + child issues, or a local
epic file in `local-review`) + a committed spec.** The epic carries the North Star, the build-order DAG,
per-child acceptance gates. `/ship run` drives
whichever you produce.

## ★ Anchor everything to the North Star ★
An epic is a commitment to an **outcome**, not a pile of tickets. Before
decomposing anything, define what "done and working" means and how you'll
*measure* it. Every child must trace to it; run mode re-checks "are we getting
closer?" against it after every merge. No North Star → no epic.

## Step 0 — Ground + brainstorm intent
- Understand the ask, the repo, constraints, and prior art (read
  `CLAUDE.md`/`AGENTS.md`, related code/docs, any existing decision log).
  **Greenfield / no repo / dry-run?** Then state the assumptions and
  conventions you're adopting explicitly, instead of reading them.
- **Derive the authority envelope** (schema in SKILL.md) from the owner's
  explicit instructions + the repo's standing rules — NEVER from what tools
  can reach. Run SKILL.md's coherence check: the chosen delivery_mode's
  minimum action set must be authorized — otherwise fix the envelope with
  the owner or take local-review, NOW, not mid-run. If an outward action's
  authorization is genuinely unsettled and it matters, ask the owner once
  now. The envelope lands in the spec (Step 4) and the ledger seed (Step 5).
- **Reality-check the premise against the code.** The ask assumes something
  about how things work today — verify it before scoping. Does the thing
  you're "fixing" actually exist and behave the way the ask implies?
  Motivating beliefs are often wrong: a tool that doesn't exist, a file
  nothing reads, a behavior already handled, an overloaded term meaning two
  different things. If grounding falsifies the premise, reshape or cancel the
  work **before** decomposing.
- **Reality-check the BASE, not only the ask.** The default branch is not
  automatically a valid base. Before the base is fixed, verify it carries the
  machinery this design is written against — the files, symbols and gates the
  children depend on — and record the result in the spec:

      git cat-file -e <base>:<path>              # does it exist there at all?
      git show <base>:<file> | grep -c <symbol>  # 0 on the base, >0 on yours?

  A deterministic branch name makes the cut **reproducible, never correct**.
  When a predecessor's unmerged work is what carries the premise, the base is
  an OWNER decision: merge the predecessor first (re-running its gates
  yourself, never on its self-report), stack deliberately, or narrow the
  design. Skipped, this surfaces at the first gate run as arms that cannot
  mint — after the slice is built.
- **Every number cited in the epic or a child ships with the command/query
  that reproduces it.** A figure without its query is a premise waiting to rot
  — it can't be re-checked, so a wrong count silently scopes the work (earned:
  an epic child cited a corpus split that didn't reproduce; the "N-column
  table" motivating it was really 3 columns × 12 duplicate records).
- **Portfolio check.** List currently-open epics. State what this epic blocks
  / is blocked by among them, whether it supersedes or absorbs any (close or
  re-scope those now — `issue-close` / `issue-edit`; unauthorized → record
  the reconciliation recommendation read-only in the spec instead —
  reconcile, don't accrete), and its **start gate** if it
  must wait on another epic's proof (e.g. "starts after the walk is green").
  An epic that can't say why *now* joins the pile instead of the plan.
- Invoke `superpowers:brainstorming` to pin intent, surface unknowns, and
  explore approaches **before** decomposing. Do not skip to issues.

## Step 1 — Write the North Star
The spine of the work — capture the outcome, not just the technical work:
- **Goal** — what we're actually trying to accomplish, in plain language.
- **Why / who it's for** — the value and the user.
- **How we'll know it worked** — a *measurable signal / demonstrable proof*
  (a number, a passing acceptance check, an observable behavior) — never just
  "it's done." **Only if the work is genuinely security / privacy / financial
  / data-loss:** also state the *threat or failure it must withstand* (what an
  adversary can reach, or what must survive a failure) so the proof can't be
  gamed (base64 ≠ encryption). For ordinary work, skip this — don't invent a
  threat you don't have.
- **Non-goals** — what's explicitly out of scope, **including what the change
  does NOT cover or what still leaks** — enumerate it, don't leave it implicit.
- **Open questions / risks** — the make-or-break unknowns not yet decided
  (recovery policy, revocation semantics, rollback strategy, …). Distinct from
  Non-goals (deliberate exclusions); these are what run mode's "unknown→known"
  progress check tracks down over the work.

**Live-data check (do it now):** does this change existing/live data, a stored
format, or established behavior? If yes, **migrating existing data is an
explicit chunk**, and the DoD proof must cover *migrated* data — not just
newly-created data — or the stated problem stays true for the whole installed
base.

**Behavior-preserving refactor? Guard, don't migrate.** If the change is
*plumbing* — it reorganizes code/wiring but is meant to leave observable
behavior (outputs, routing, results) identical — do the opposite of a
migration chunk: constrain the work to behavior-preserving and make a
**differential / golden oracle** the keystone gate (capture current outputs
across the real corpus, assert byte-identical before/after). Add a migration
chunk **only** when the change *intends* to alter existing data or behavior.

## Step 2 — Size the work (the chunk gate)
Count the chunks (the chunk rule is in SKILL.md). The question: **can ONE
concrete, non-gameable acceptance gate prove the whole ask, landed as ONE
reviewable landing (a PR, or one local `--no-ff` merge) by one worker?**
(An owner-gate chunk is the exception: no worker, no landing — it is sized
by its decision.)

- **1 chunk → single issue.** Take the single-issue path below, then stop —
  the rest of this file is the epic pipeline. Do NOT manufacture an epic for
  one chunk: no spec file, no DAG, no keystone, no portfolio ceremony.
- **2+ chunks → epic.** Continue with Step 3.

Sizing smells: an "epic" whose children are *phases* of one change
(design → implement → test) is ONE chunk — phases are not slices. A "single
issue" that needs two different acceptance gates, or whose parts could land
and be validated separately, is 2+ chunks — split it.

### The single-issue path (1 chunk)
Open ONE issue per the envelope's delivery_mode — github modes via `gh`;
`local-review` (or no `gh` / no remote) as a local file under `docs/` with
the same fields, first-class — carrying everything an epic child would carry:
- **Scope** — the chunk, stated as an independently testable vertical slice.
- **Acceptance gate** — concrete, runnable, non-gameable. If it's runnable now
  (pre-fix reproduction, existing fixture), run it and **archive the RED** in
  the issue. If the work itself builds the gate, flag it
  **`show-RED-before-first-use`** — run mode's instrument check enforces it.
  Destructive/irreversible work also gates on backup + *exercised* rollback +
  partial-failure handling. An **`owner-gate`** single carries the
  `owner-gate` mark INSTEAD of a runnable gate (Step 3's owner-gate rules):
  run mode gives it no worker and no landing.
- **Compact North Star** — goal + how-we'll-know, inline.
- **Context inlined** — constraints, non-goals, and the settled brainstorm
  decisions. The issue body IS the spec for a single; no separate spec file.
- **Policy** — the authority envelope (SKILL.md), authored inline in the
  body. It is then seeded into the single's ledger (below) exactly as for
  epics — the ledger's `policy:` line is the canonical live record; the
  body copy is the authoring snapshot.
- **Origin-or-defensive flag** — if it fixes a defect, say which; a defensive
  patch links its origin issue and states its retirement condition.

Durability — the epic path's machinery, scaled down. Identity is Step 4's
deterministic engagement-key / plan-id; the body carries the
`engagement-key:` and `plan-id:` marker lines. **github mode**
(needs `issue-create`): persist the identity AND CONTENT before the
external write — commit a receipt `docs/specs/<plan-id>.receipt.md`
carrying both markers and the COMPLETE approved issue-body draft (crash
recovery must re-create identical content, never re-derive it; no
`ship:contract` marker — a receipt is not a contract, scout ignores it).
Push the receipt (Step 4's publication rule) and verify it is fetchable.
The single follows Step 5's creation state machine
(`prepared → attempting → created(#n)`, pushed before/after
`gh issue create`) and its recovery scan (ambiguous → poll → fail closed
creation-uncertain; >1 exact match = incident) — never re-mint. Then seed the
sentinel ledger comment
(`<!-- ship:ledger -->`, needs `issue-comment`) with the `policy:` line and
read it back. **local-review**: the contract is the ONE canonical file
`docs/specs/<plan-id>.md`, opening with
`<!-- ship:contract plan-id=<id> kind=single status=active -->`; create the
integration branch `<plan-id>-integration` from the default branch's
current HEAD if absent and commit the file ON it (Step 5's bootstrap,
identically); its `## Ledger` section carries the policy line. Re-running
this path is idempotent: search / check the canonical path FIRST — a
full-identity match = resume; a fingerprint mismatch = a distinct plan,
never adopt it.

Hand off: report the issue number (or branch + path) and "ready for
`/ship run <issue# | path>`".

## Step 3 — Decompose into child issues (a DAG, not a list)
Use `superpowers:writing-plans` discipline. **Each child is one chunk (the
chunk rule) and carries:**
- **Scope** — one independently valuable, independently testable **vertical
  slice** (INVEST), not a horizontal layer.
- **Acceptance / gate** — the concrete check that proves it works (prefer a
  runnable command / test); it must defend the North Star's stated
  threat/failure and not be gameable. **For a destructive or irreversible
  child** (migrations, purges, deletes): also require a backup + an
  *exercised* rollback path and partial-failure handling, and gate on *safety
  of failure*, not just the happy path. **If the gate uses a regression
  control** ("X must remain unchanged"): the premise that qualifies X as a
  control must be *verified against evidence and stated with its falsifier*
  in the child body — an assumed control enforces the defect it was meant to
  catch. Make the check **directional**: state what a legitimate flip of the
  control would mean, so a change there is triaged finding-vs-regression
  instead of auto-failed.
- **Origin-or-defensive flag** — if the child fixes a defect, state whether
  it's the *origin* fix or a *defensive* patch. A defensive child must link
  the origin issue and state its **retirement condition** ("this code becomes
  a no-op when the origin fix lands" — and the origin's acceptance asserts
  that no-op). A defensive patch with no named origin is how guard sprawl
  starts.
- **Contributes to North Star** — one line on *how* this child moves the
  signal. Can't write it? The child doesn't belong (or the North Star is
  wrong).
- **Context inlined** — the parent decisions/constraints + relevant non-goals
  this child must respect, plus a link to the **specific spec section**
  (anchor), so an autonomous worker executes without re-deriving the design
  or diverging from siblings.
- **Repo-declared fields** — when the repo declares execution / authority /
  regime fields for work items, every child carries them (the repo defines
  the taxonomy, not this skill).
- **blocked-by** — dependency edges.
- **Owner-gate children** — when a child's acceptance is a reserved owner
  decision (SKILL.md ladder + the envelope's `owner_reserved_decisions`,
  e.g. governance / contract acceptance): mark it **`owner-gate`**. Its
  gate is the owner's RECORDED acceptance — non-runnable by design; never
  manufacture an executable proxy a worker or delegate could satisfy.
  Dependents take `blocked-by` edges on it; unattended, run mode parks it
  `awaiting-owner(<gate>)` and hands off. After the owner's explicit
  acceptance — owner-authored, attributable, immutably referenced; an
  agent-authored record can QUOTE an owner statement but never supply
  acceptance — run mode advances it to `accepted(<decision record/ref>)`
  and unblocks dependents; a rejection re-plans them (run.md Step 0).
- **Data-spike-first flag** — set if the child is a **producer** (it generates
  an artifact/format that downstream children consume). The spike is an
  INTERNAL pre-implementation substep of that same chunk: the worker
  hand-makes the input, runs the REAL consumer, proves the gap closes, then
  discards the spike and builds. Split it into its own child ONLY when the
  spike settles an independently reviewable/landable decision — then it's a
  real slice, not a spike.

Express the build order as a **dependency DAG / phases with parallel
branches** (e.g. `1 → {2,3} → {4,5} → 6`), not a flat sequence — run mode
dispatches independent branches in parallel. Identify the **keystone**. The
**end-to-end DoD demonstration is itself an explicit child** — ideally a
permanent CI regression gate, not a one-off script — and it carries an
**executable finale contract** (the finale is where runs historically stall;
run mode's Step 3 preflight consumes exactly these fields):
- **Substrate recipe** — how to construct the demonstration environment/data
  (source, copy/fork steps, preparation) — not just "on a fresh copy". **One
  substrate per proof** when proofs flip shared state/signals: a CLI proof and
  a driven proof on one substrate contaminate each other (the first pre-flips
  what the second must observe unflipped).
- **Required-inputs inventory** — for every stage that rebuilds derived
  state, the upstream inputs that stage consumes, so run mode can verify the
  substrate can carry each stage BEFORE spending on it.
- **Oracle command + per-stage expected observables**, each placed BEFORE the
  expensive/destructive step it guards.
- **Calibration record** — every pinned threshold states the substrate it was
  measured on; a number read on a different substrate shape is an
  adjudication, not a target.

## Step 4 — Write & commit the spec
Write a decision-log/spec to `docs/` (repo convention, else
`docs/specs/<plan-id>.md`). **Identity is DETERMINISTIC — recomputable on
any fresh host from the same inputs, never random:**

    engagement-key = sha256( canonical repo identity
        + "\n" + exact initial request
        + "\n" + owner nonce )
    plan-id = <slug>-<first 12 hex of engagement-key>

- *canonical repo identity* — the normalized canonical remote URL
  (lowercase, https form, trailing `.git` stripped); no remote → the root
  (initial) commit SHA; neither → an owner-declared local ID.
- *exact initial request* — the ask as first recorded: the spec's verbatim
  `## Ask` block, or a wake's durable Intent section. Bytes: UTF-8, LF
  line endings, trailing whitespace stripped per line.
- *owner nonce* — EMPTY unless the owner explicitly directs a second,
  deliberately identical engagement.

The creation date is metadata inside the spec — never identity. Resume =
recompute the key from the same inputs → the same plan-id → the same
paths, branches, and markers. Persist `engagement-key: <64-hex>` and
`plan-id: <id>` as exact marker lines in the spec, EVERY receipt, and
EVERY issue body. Before adopting ANYTHING found under a plan-id, verify
its FULL `engagement-key:` marker: a 12-hex prefix collision, or a
same-slug ACTIVE plan under a different key, is a STOP-and-reconcile
signal — never adoption. The spec carries:
the verbatim **`## Ask`** block (the identity input, recorded exactly as
received — never edited after mint),
the North Star (all fields, incl. Open questions),
the **authority envelope**, the settled decisions + *why*, the child
breakdown, the build-order DAG, and the DoD-demonstration plan. **github
modes:** commit it now, then PUBLISH the contract ref — push the spec to
the DETERMINISTIC ref `ship/contract/<plan-id>` (`push`; a protected
target may additionally require a PR — `pr-create`; never assume direct
default-branch pushes): a fresh host fetches the contract by name. Link
issues to the IMMUTABLE commit-SHA URL, never a branch path (a local-only
spec makes every issue link a dead reference). **Publication rule for
every LATER checkpoint on this ref** — receipts, evidence, fallback
appends: commit AND push it the same way, then verify the SHA is remotely
fetchable (`git ls-remote`) — the initial push never publishes later
commits; `push` unauthorized → record it as publication-owed and hand
off. **local-review:** hold the
commit — Step 5 creates
the integration branch FIRST and commits the ONE canonical file there (the
spec IS the contract; never a second path). Either way this is the "why"
run mode redlines against.

## Step 5 — Open the contract (per the envelope's delivery_mode)
**github modes** — via `gh`, idempotent and resumable. Requires the mode's
minimum action set (SKILL.md coherence check: `issue-create`,
`issue-comment`, `push`, `pr-create`) in `authorized_external_actions` —
delivery_mode authorizes nothing; missing → local-review, or ask the owner:
- **Plan identity first.** Every body carries the exact marker lines
  `engagement-key: <64-hex>`, `plan-id: <id>`, and its own stable
  `item: <id>#<child-slug>` (Step 4's deterministic identity).
- **Creation state machine — every item (the epic, each child, a single):**
  receipts track `prepared → attempting → created(#n)`. Commit AND push
  `attempting: <item-id>` (publication rule, Step 4) BEFORE
  `gh issue create`; on success record `created(#n)` and push. An
  ambiguous response (timeout, 5xx, unknown) → poll the recovery scan;
  found → record `created(#n)`; still absent after retries → the item
  stays `attempting` = **creation-uncertain: FAIL CLOSED** — never create
  again automatically; the owner or an incident resolves it. More than one
  exact `item:` match = an incident.
- **Recovery scan — the authority (typed, paginated, non-search):**

      gh api --paginate "repos/<owner>/<repo>/issues?state=all&per_page=100" \
        --jq '.[] | select(has("pull_request") | not) | {number, body}'

  then match the exact `plan-id:` / `item:` marker lines LOCALLY, and
  verify the FULL `engagement-key:` before adopting any match (GitHub's
  `--search` index lags — convenience only, never the guard).
- **Epic issue** — the North Star (verbatim), the build-order DAG, the DoD /
  how-we'll-know, and a link to the committed spec. Label it (e.g. `epic`).
- **Child issues** — each seeded with: scope, acceptance gate, "contributes to
  North Star", blocked-by, data-spike flag, the **inlined parent
  constraints**, and a link to the **specific spec section** (anchor, not just
  the whole doc).
- **Receipts immediately:** the state machine above IS the receipt — each
  transition (`attempting`, `created(#n)`) is appended to the committed
  spec (`## Receipts`), committed, pushed, and verified fetchable — a
  crash mid-batch resumes from receipts + the recovery scan, creating only
  what has never reached `attempting`.
- **Wire relationships as a resumable SECOND pass** once all children exist
  (`issue-edit`; unauthorized → record the wiring as OWED in the ledger +
  handoff, for an authorized session): native sub-issue links if supported,
  otherwise a task-list in the epic
  body + "Part of #<epic>" in each child — check existing links first; the
  pass is idempotent.
- **Seed the ledger** (schema in SKILL.md): post the status comment opening
  with `<!-- ship:ledger -->` — every child `queued` (seed a child already
  landed/closed at its ACTUAL state, not blindly `queued`), the `policy:`
  line, the open questions — then READ IT BACK by sentinel to verify run
  mode will find it. Run mode maintains it from here.
- Seed **enough context that an autonomous agent can execute the child**
  without re-deriving the whole design.

**`local-review`** — the contract is the ONE canonical file
`docs/specs/<plan-id>.md` (the Step 4 spec itself — never a second path),
committed on the integration branch:
1. Create/select the integration branch `<plan-id>-integration` from the
   default branch's current HEAD — the name is DETERMINISTIC from the
   plan-id, so resume re-derives it without reading anything first; record
   it in the envelope's `integration_branch`. **Verify the base carries the
   premise before cutting** (Step 0) — determinism is not correctness, and
   this is the step where an invalid base becomes a built slice.
2. Extend the spec into the contract: open the file with
   `<!-- ship:contract plan-id=<id> kind=epic status=active -->`, then every
   child with all its fields (incl. item ids), the envelope, and a
   `## Ledger` section (`blocked-by` by child title/number).
3. Commit the file ON the integration branch — the canonical ref run mode
   reads. The handoff names BOTH the branch and the path.
**Local-review is first-class and stays canonical for its ENTIRE
lifecycle — there is no in-place lift and no authority transformation.**
Publishing the work to GitHub later is a SEPARATE owner-gated `/ship plan`
engagement (its own approved envelope and its own deterministic identity)
planned around a publication slice; the local contract's results enter it
as EVIDENCE — links, SHAs, gate output — never as pre-existing remote
"merged" state. No `gh` / no remote forces this mode regardless of the
envelope.

## Step 6 — Validate before handoff
- Every child traces to the North Star (non-empty "contributes" line).
- Every child has a **concrete, non-gameable** acceptance gate; destructive
  children have a rollback / partial-failure gate.
- The build order is **acyclic** and the keystone is identified.
- The **base carries the premise**: every file, symbol and gate the children
  depend on was verified present at `baseline`, and the check is recorded. A
  base taken by rule with no such evidence fails validation.
- The **end-to-end DoD demonstration is a planned child** carrying the
  executable finale contract (substrate recipe, required-inputs inventory,
  checkpointed oracle, calibration record).
- The North Star's "how we'll know" is genuinely measurable/demonstrable.
- Every gate **runnable at plan time** (pre-fix state, existing or
  deliberately-broken fixture) has been **shown able to fail** — run it and
  archive the RED (watch-the-test-fail, lifted to epic level). A gate that
  has never been red proves nothing — a residue report once read "0 gaps" on
  an app that was all stubs. A gate the child itself will build **cannot** be
  run yet: flag it **`show-RED-before-first-use`** in the child body; run
  mode's instrument check enforces it before that gate is trusted. An
  **`owner-gate`** child is the third bin: its gate is a recorded owner
  decision — neither red-proof rule applies; do NOT manufacture an
  executable proxy for it.
- **Every pinned gate figure was produced by the gate's OWN instrument on the
  gate's own material.** Put the two commands side by side: the one that
  produced the number, and the one the gate runs. Not the same command over the
  same material → the number is EVIDENCE, not a threshold: record it as
  evidence, name the instrument whose scope DOES contain it, and let the gate's
  own first run establish the figure the gate reads. (Step 3's calibration
  record — "a number read on a different substrate shape is an adjudication,
  not a target" — applied to every gate, not only the DoD child's finale.)
  Corollary: **an open question may not sit under a pinned threshold** — if the
  plan asks whether an instrument reports a figure, settle it here or don't pin
  the figure. Earned: an epic pinned "75 resolved / 24 unresolved" on a
  single-grammar census arm while the query that produced it was SQL against the
  shared graph, and asked in the same document whether the census reported it;
  the census cannot see the far end of an edge whose ends come from two
  grammars, so that arm could only ever fail. Two commands compared cannot be
  satisfied by prose. "Can the instrument see it?" can be, and was.
- The **authority envelope** is in the spec and the ledger seed; every
  planned action it does NOT authorize has a stated alternative (local file,
  wait, or ask).
- Every owner-reserved acceptance is an explicitly marked **`owner-gate`**
  child — a non-runnable gate WITHOUT the mark fails validation (unmarked
  prose gates are how reserved decisions get delegated by accident).
- Regression controls have evidence-verified premises with falsifiers;
  defensive children link their origin issue and name their retirement
  condition; cited numbers carry their reproducing query.
- If the change touches live data, **existing-data migration is a child and
  the DoD proof covers migrated data**.
- **Only if genuinely high-stakes** (security / privacy / financial /
  data-loss): require a **threat model + a data-loss/rollback review** in the
  spec. For ordinary work, skip it — don't manufacture one.

If any check fails, fix it before handoff — never hand run mode a plan that
can't be proven.

## Handoff
Report the contract per mode — gh: the epic number; local-review: the
integration branch AND contract path — and "ready for
`/ship run <epic# | path>`". Summarize the
North Star, the child count + build-order DAG, and the open questions/risks.
Close with the run review + skill feedback loop
(SKILL.md): the release-notes recap of anything else the session changed,
plus any ship-skill improvement offers captured in the spec's decision notes
while planning — offers only; landing follows SKILL.md's gate.

## Waking a parked ledger entry
The argument is an intention-ledger entry (`docs/backlog/<slug>.md`) — always
a wake, never an epic spec (SKILL.md routes it here):
1. **Re-baseline first.** The entry's Intent is the ask. Re-judge EVERY
   perishable note and the `wake:` trigger against current code — they are
   dated observations that EXPECT to be wrong, never inputs to trust. If
   re-grounding falsifies the premise, reshape — or kill the entry
   (park.md's Kill) — instead of planning it.
2. Run this file's normal pipeline (Step 0 onward) on the re-baselined
   intent. The engagement-key's exact-request input is the entry's durable
   Intent section VERBATIM (Step 4), so key and plan-id recompute
   identically on any host; also write `minted: <plan-id>` into the
   entry's frontmatter and commit the nested ledger repo BEFORE any
   external write — the belt-and-braces registry record. The envelope's
   delivery_mode governs Step 5 as usual.
3. **Retire the entry — idempotent, only after the contract exists:** move
   the file to `docs/backlog/shipped/<slug>.md`, record the minted
   epic/issue number (or local spec path) in its frontmatter, drop its
   INDEX.md line, commit the nested ledger repo. Crash between minting and
   retiring → the re-run recomputes the deterministic identity (or reads
   `minted:`), then finds the contract via the recovery scan / receipts /
   the canonical local contract path (Steps 5–6 or the single-issue path)
   — the wake is recoverable BEFORE the entry records its final issue
   number — and completes this step WITHOUT re-minting; the entry sitting
   in both
   `docs/backlog/` and `shipped/` means this step half-finished — finish the
   move, don't re-plan.

## Common mistakes
- **Inflating one chunk into an epic** — ceremony without a second slice to
  order; the sizing gate exists to stop this. Phases (design/implement/test)
  are not chunks.
- **Compressing multiple chunks into one mega-issue** — if parts could land
  and be validated separately, split; one gate can't honestly prove two
  slices.
- Scoping against how you *assume* things work instead of verifying against
  the code → work that fixes a non-problem (a tool that doesn't exist, a file
  nothing reads).
- Jumping to issues before the North Star / brainstorm → tickets with no
  outcome to check against.
- A "how we'll know" that isn't measurable ("it works") → run mode can't run
  its drift gate.
- A child with no "contributes to North Star" line → scope creep, or a wrong
  North Star.
- Vague or **gameable** acceptance gates → run mode can't validate and
  workers game them (base64 ≠ encryption).
- Forgetting **existing-data migration** when the change touches live data →
  the North Star is unmet for the installed base.
- Adding a migration child for a **behavior-preserving refactor** → wrong
  guard; use a differential/golden oracle (prove before == after), not a
  migration.
- Forgetting the end-to-end demo as an explicit child → guarantees "unproven
  done."
- A DoD child naming the proof but not the substrate recipe / calibration
  record → the finale gets improvised at the end of a long run and circles.
- A destructive step with no rollback / partial-failure gate → an
  irreversible mistake waiting to happen.
- One whole-doc spec link per child → the worker re-reads everything; link
  the specific section + inline the constraints.
- Cycles in `blocked-by` → the build order deadlocks.
- A figure with no reproducing query → the count is wrong and nobody can
  tell; the work scopes against a phantom.
- A figure whose reproducing query is **not the gate's own command** → a
  *plausible* red that sends the investigation at the implementation instead of
  at the assertion; the number is usually true somewhere else — pin it on the
  instrument that produced it, and let this gate pin what it can actually read.
- A regression control with an unverified premise ("X is static, assert
  unchanged") → the gate enforces the defect; a legitimate flip gets
  auto-failed instead of triaged.
- A gate never seen red (and not flagged `show-RED-before-first-use`) →
  vacuous pass; it certifies stubs as done.
- A defensive child with no origin link / retirement condition → guard
  sprawl; the symptom fix silently becomes the resolution.
- Opening an epic into a full portfolio with no start gate → WIP multiplies,
  every epic slows, the week circles.
- Treating tool availability as authority — `gh` reachable ≠ authorized; the
  envelope decides per named action, and delivery_mode is shape, never
  authorization (capability-keyed outward writes are how local-only runs
  leak).
- An owner-reserved acceptance without the `owner-gate` mark → a delegate can
  lawfully "accept" it unattended.
- Minting issues without plan-ID + receipts → a crash mid-creation
  duplicates the contract on retry.

# /ship plan — turn an idea into provable, ready-to-run work

The deliverable depends on size (Step 2): **one chunk → ONE well-gated issue;
two-plus chunks → a GitHub epic issue (the contract) + child issues + a
committed spec.** The epic carries the North Star, the build-order DAG,
per-child acceptance gates, and per-child model tiers. `/ship run` drives
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
- **Reality-check the premise against the code.** The ask assumes something
  about how things work today — verify it before scoping. Does the thing
  you're "fixing" actually exist and behave the way the ask implies?
  Motivating beliefs are often wrong: a tool that doesn't exist, a file
  nothing reads, a behavior already handled, an overloaded term meaning two
  different things. If grounding falsifies the premise, reshape or cancel the
  work **before** decomposing.
- **Every number cited in the epic or a child ships with the command/query
  that reproduces it.** A figure without its query is a premise waiting to rot
  — it can't be re-checked, so a wrong count silently scopes the work (earned:
  an epic child cited a corpus split that didn't reproduce; the "N-column
  table" motivating it was really 3 columns × 12 duplicate records).
- **Portfolio check.** List currently-open epics. State what this epic blocks
  / is blocked by among them, whether it supersedes or absorbs any (close or
  re-scope those now — reconcile, don't accrete), and its **start gate** if it
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
concrete, non-gameable acceptance gate prove the whole ask, landed as ONE PR
by one worker?**

- **1 chunk → single issue.** Take the single-issue path below, then stop —
  the rest of this file is the epic pipeline. Do NOT manufacture an epic for
  one chunk: no spec file, no DAG, no keystone, no portfolio ceremony.
- **2+ chunks → epic.** Continue with Step 3.

Sizing smells: an "epic" whose children are *phases* of one change
(design → implement → test) is ONE chunk — phases are not slices. A "single
issue" that needs two different acceptance gates, or whose parts could land
and be validated separately, is 2+ chunks — split it.

### The single-issue path (1 chunk)
Open ONE issue via `gh` carrying everything an epic child would carry:
- **Scope** — the chunk, stated as an independently testable vertical slice.
- **Acceptance gate** — concrete, runnable, non-gameable. If it's runnable now
  (pre-fix reproduction, existing fixture), run it and **archive the RED** in
  the issue. If the work itself builds the gate, flag it
  **`show-RED-before-first-use`** — run mode's instrument check enforces it.
  Destructive/irreversible work also gates on backup + *exercised* rollback +
  partial-failure handling.
- **Compact North Star** — goal + how-we'll-know, inline.
- **Model tier** — apply `choosing-a-model` to this chunk.
- **Context inlined** — constraints, non-goals, and the settled brainstorm
  decisions. The issue body IS the spec for a single; no separate spec file.
- **Origin-or-defensive flag** — if it fixes a defect, say which; a defensive
  patch links its origin issue and states its retirement condition.

No `gh` / no remote? Write it as a local file under `docs/` with the same
fields. Hand off: report the issue number and "ready for `/ship run <issue#>`".

## Step 3 — Pick the planning model (and act on it)
Invoke `choosing-a-model` for the **planning work itself**, and *do the
decomposition with that model*: if it's Fable (extremely complex **and**
high blast-radius), plan with Fable now (expect minutes-long turns). Most
planning is Opus. Record the `MODEL PICK: ...` line in the spec. This is
separate from the per-child tiers in Step 4 — the planning pick does not
dictate child tiers.

## Step 4 — Decompose into child issues (a DAG, not a list)
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
- **Model tier** — apply the `choosing-a-model` gate to **this child**:
  default Opus; Sonnet/Haiku for mechanical, gate-backed work; **Fable only
  when the child itself scores high on *both* axes — complexity AND blast
  radius.** "Keystone" is a heuristic, not a trigger: a trivial keystone stays
  Opus, and a dangerous non-keystone can warrant Fable. Judge the child, not
  its label.
- **Context inlined** — the parent decisions/constraints + relevant non-goals
  this child must respect, plus a link to the **specific spec section**
  (anchor), so an autonomous worker executes without re-deriving the design
  or diverging from siblings.
- **blocked-by** — dependency edges.
- **Data-spike-first flag** — set if the child is a **producer** (it generates
  an artifact/format that downstream children consume). Then precede it with a
  *throwaway spike* that hand-makes the input and runs the REAL consumer;
  discard the spike, productionize in a follow-on child.

Express the build order as a **dependency DAG / phases with parallel
branches** (e.g. `1 → {2,3} → {4,5} → 6`), not a flat sequence — run mode
dispatches independent branches in parallel. Identify the **keystone**. The
**end-to-end DoD demonstration is itself an explicit child** — ideally a
permanent CI regression gate, not a one-off script — and it carries an
**executable finale contract** (the finale is where runs historically stall;
run mode's Step 3 preflight consumes exactly these fields):
- **Substrate recipe** — how to construct the demonstration environment/data
  (source, copy/fork steps, preparation) — not just "on a fresh copy".
- **Required-inputs inventory** — for every stage that rebuilds derived
  state, the upstream inputs that stage consumes, so run mode can verify the
  substrate can carry each stage BEFORE spending on it.
- **Oracle command + per-stage expected observables**, each placed BEFORE the
  expensive/destructive step it guards.
- **Calibration record** — every pinned threshold states the substrate it was
  measured on; a number read on a different substrate shape is an
  adjudication, not a target.

## Step 5 — Write & commit the spec
Write a decision-log/spec to `docs/` (repo convention, else
`docs/specs/YYYY-MM-DD-<epic>.md`): the North Star (all fields, incl. Open
questions), the settled decisions + *why*, the child breakdown, the
build-order DAG, and the DoD-demonstration plan. Commit it — this is the
"why" run mode redlines against.

## Step 6 — Open the GitHub issues (the contract)
Via `gh`:
- **Epic issue** — the North Star (verbatim), the build-order DAG, the DoD /
  how-we'll-know, and a link to the committed spec. Label it (e.g. `epic`).
- **Child issues** — each seeded with: scope, acceptance gate, "contributes to
  North Star", model tier, blocked-by, data-spike flag, the **inlined parent
  constraints**, and a link to the **specific spec section** (anchor, not just
  the whole doc). Cross-link to the epic (native sub-issue relationship if
  supported; otherwise a task-list in the epic body + "Part of #<epic>" in
  each child).
- **Seed the ledger** (schema in SKILL.md): post the status comment on the
  epic with every child `queued` and the open questions listed. Run mode
  maintains it from here.
- Seed **enough context that an autonomous agent can execute the child**
  without re-deriving the whole design.

Degrade gracefully: no `gh` / no remote → write a local epic file under
`docs/` (`docs/specs/<epic>.md`) containing the epic body + a checklist of
children with all their fields + a `## Ledger` section, expressing
`blocked-by` by child title/number. `/ship run <path>` drives that file
directly; the issues can still be opened later.

## Step 7 — Validate before handoff
- Every child traces to the North Star (non-empty "contributes" line).
- Every child has a **concrete, non-gameable** acceptance gate; destructive
  children have a rollback / partial-failure gate.
- The build order is **acyclic** and the keystone is identified.
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
  mode's instrument check enforces it before that gate is trusted.
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
Report the epic number and "ready for `/ship run <epic#>`". Summarize the
North Star, the child count + build-order DAG, the open questions/risks, and
any Fable-tier children.

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
- Not recording model tiers → run mode re-derives them or over/under-pays.
- Cycles in `blocked-by` → the build order deadlocks.
- A figure with no reproducing query → the count is wrong and nobody can
  tell; the work scopes against a phantom.
- A regression control with an unverified premise ("X is static, assert
  unchanged") → the gate enforces the defect; a legitimate flip gets
  auto-failed instead of triaged.
- A gate never seen red (and not flagged `show-RED-before-first-use`) →
  vacuous pass; it certifies stubs as done.
- A defensive child with no origin link / retirement condition → guard
  sprawl; the symptom fix silently becomes the resolution.
- Opening an epic into a full portfolio with no start gate → WIP multiplies,
  every epic slows, the week circles.

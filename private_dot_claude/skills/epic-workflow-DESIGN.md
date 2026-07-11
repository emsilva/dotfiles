# Epic Workflow — design (account-wide skills)

Status: approved 2026-07-01. This file is the durable design record for three
account-wide skills that together form a model-aware, goal-driven epic lifecycle.
It is documentation, not a skill; `~/.claude` is not a git repo, so it is not committed.

> **Superseded 2026-07-05:** `plan-epic` + `run-epic` are merged into the single
> skill **`ship`** (extended to single-issue work + a compaction-survival ledger).
> See the dated section at the bottom. `choosing-a-model` is unchanged. The
> sections in between remain as the historical record of the two-skill design.

## North Star (of this meta-work)

**Goal:** make it effortless to (a) always use the *best model for the job without
overpaying*, and (b) run epics that stay anchored to *what we're actually trying to
accomplish* — not just a parade of merged PRs.

**Why / who:** the user runs multi-issue epics (originating in the `<project>`
project's `/run-epic`). They want the same rigor available in every repo/session,
plus a disciplined front-end (`/plan-epic`) and a shared model-selection rubric now
that Fable 5 is returning.

**How we'll know it worked (signal):** any session can (1) get a defensible model
pick with a one-line rationale, (2) plan an epic into contextualized, linked GitHub
issues backed by a committed spec, and (3) drive that epic to a *proven* Definition
of Done while a drift gate keeps asking "are we getting closer to the goal?".

**Non-goals:** a project overlay for run-epic; a full scored progress ledger; any
model-cost telemetry/metering. (All deliberately cut — see YAGNI.)

## Architecture

Three skills in `~/.claude/skills/`, one lifecycle:

```
/plan-epic  ──writes──►  the Epic (GitHub issue + committed spec)  ──drives──►  /run-epic
     │                     North Star + children + tiers + build order            │
     └────────► choosing-a-model  ◄──── invoked at every model decision ──────────┘
```

The **epic issue is the contract**: plan-epic writes it, run-epic reads and drives it.

### 1. `choosing-a-model` — the rubric
- Default = **Opus 4.8** (the workhorse). Move off it only deliberately.
- Cost ladder (output $/1M): Haiku `$5` → Sonnet 5 `$15` → Opus 4.8 `$25` → **Fable 5 `$50`**. Fable ≈ 2× Opus → reserved, not default.
- Route by **reasoning required × blast radius**, never by phase.
- **Fable gate** — escalate to Fable only when BOTH complexity AND blast radius are high
  (irreversible / cross-cutting / client-facing / data-loss / security / sets architecture).
- Tiers: Fable = plan/architect the hardest+highest-impact work, keystone/integration
  design, load-bearing root-cause; Opus = default judgment work; Sonnet = well-specified
  non-trivial / high-volume / scoped sub-agents; Haiku = mechanical / search-explore / lookups.
- "Don't overpay": a Sonnet/Haiku miss a gate catches is cheap; a keystone quality miss
  costs more than the Fable premium; escalate only when smarter reasoning would decide
  *differently*, not just phrase it nicer.
- Fable caveats: thinking always on; minutes-long turns on hard tasks; use it for hard
  thinking, hand grinding to Opus/Sonnet workers.
- Output contract: emits `MODEL PICK: <tier> — <axes>` that the epic skills record/honor.

### 2. `plan-epic` — create the epic
ground → `superpowers:brainstorming` for intent → **North Star** (goal · why/who ·
how-we'll-know + measurable signal · non-goals) → pick planning model via
`choosing-a-model` (Fable if extremely complex + high blast radius) → decompose into
child issues with `superpowers:writing-plans` discipline (each: scope · acceptance/gate ·
"contributes to North Star: how" · model tier · blocked-by · data-spike-first flag) →
commit spec to `docs/` → open GitHub epic + child issues via `gh` (labeled, cross-linked,
blocked-by, sub-issue linkage, seeded with context) → validate (every child maps to the
North Star; DoD is a real demonstration; build order acyclic; every child gated; the
end-to-end demo is itself a planned child) → handoff "ready for /run-epic <epic#>".
Degrades gracefully with no `gh`/remote (specs + local epic file, tells the user).

### 3. `run-epic` — drive the epic (generalized)
Keep the bones: owner-orchestrator, per-issue ground→brainstorm→redline→plan→execute→PR
loop, independent validate/merge recipe (worktree isolation, re-run gates, READ THE
ARTIFACT NOT THE SUMMARY, coverage probe, merge/worktree gotchas), DoD-demonstration
finale, Lessons. **Strip** <project> specifics (§9 corpus-agnostic, LiteLLM, slug/fork
data-safety, Go/Python literals); rails become generic (ground-first, spike-before-producer,
TDD-watched-to-fail, fix-at-origin, never-silently-drop, decision-log/ADR currency,
gate-integrity + flag-impossible escape hatch, `Closes #n`). Two upgrades:
- **Model routing** → delegate to `choosing-a-model` (per-child tier from the plan;
  escalate to Fable for keystone / gnarly root-cause).
- **North Star drift gate** → after each child merges, check "are we measurably closer
  to the North Star signal?"; on drift / scope-narrowing / vacuous-done, STOP and surface
  to the human with a recommendation.

## YAGNI (deliberately not doing)
- No project overlay for run-epic (drop <project> specifics; re-supply per run).
- No full scored progress ledger (North Star + drift gate is enough).
- No model-cost telemetry.

## Validated & refined (2026-07-01)

Built with the `superpowers:writing-skills` TDD discipline (RED→GREEN→refine). Evidence:
- **choosing-a-model** — RED baseline: two fresh agents, *once handed the model facts*, already derived the right heuristic ("blast radius × ambiguity"), so the real gap is post-cutoff knowledge of Fable → the skill is a **reference** that makes the facts + gate resident. GREEN: a fresh agent with no price knowledge got all 6 scenarios right, including the traps (volume≠complexity; security-but-simple≠Fable; no-tests→don't-downgrade).
- **run-epic** — verified port: all 14 lessons preserved (generalized), zero <project> specifics leaked.
- **plan-epic** — gap-tested by a harsh-critic agent on an E2E-encryption epic; findings folded in.

Refinements folded from a cited deep-research sweep + the gap-test:
- choosing-a-model: reactive escalation (LLM-cascade pattern) + architect→editor task-splitting + context-reliability volume nuance + two-way-door down-classification.
- plan-epic: live-data migration as a mandatory child; Open-questions/risks North Star field; INVEST vertical slices; non-gameable gates + threat model for high-stakes; rollback/partial-failure gate for destructive children; per-child spec anchors + inlined parent constraints; build order as a DAG.
- run-epic: drift gate scope-hammering nuance (STOP only when narrowing *abandons* the signal) + hill-chart unknown→known progress.

Note: the account-wide `run-epic` is generic; <project>'s project-level `run-epic` (with its specifics) still exists and takes precedence inside that repo. They coexist — remove the project copy only if you want <project> to use the generic one.

## 2026-07-05 — Merged into one skill: `/ship`

Status: approved 2026-07-05 (user decisions: name `ship`; subcommands only;
archive + remove the old dirs). `plan-epic` and `run-epic` are merged into a
single account-wide skill, extended to single-issue work and to surviving
context compaction mid-run. Old dirs archived at `~/.claude/skills-archive/`
(the skills dir is not chezmoi-managed and not a git repo — never hard-delete).

### Why
- One lifecycle, one skill: the pair shared all doctrine but split it across
  two trigger surfaces.
- Small work was over-ceremonied: an ask that fits ONE testable chunk should
  become one well-gated issue, not an epic.
- run-epic held orchestration state only in conversation; compaction mid-epic
  lost redline decisions and per-child status.

### Interface (subcommands only)
- `/ship plan <idea>` — plan mode
- `/ship run <epic# | issue# | path/to/epic-spec.md>` — run mode
- bare `/ship` — print both forms and ask
- Inside run mode, epic-vs-single-issue is detected from facts (epic label /
  sub-issues present), never guessed from the argument.

### Architecture (progressive disclosure)
```
~/.claude/skills/ship/
  SKILL.md            router + shared doctrine: the chunk rule, North Star,
                      sizing gate, ledger protocol (always loaded)
  references/plan.md  full planning playbook (epic + single-issue paths)
  references/run.md   full run playbook (epic orchestration + single-issue run)
```
A session loads only its mode's playbook.

### The chunk rule + sizing gate (new)
Atomic unit = a chunk that is independently testable/validated by ONE
non-gameable acceptance gate and landable as one PR. Plan mode always grounds +
premise-checks + writes a North Star, then sizes: **1 chunk → single issue**
(carrying scope, gate, model tier, inlined context, and a compact
goal/how-we'll-know; settled decisions go in the issue body — no spec file for
singles); **2+ chunks → epic** (the full existing pipeline, unchanged).

### Ledger + resume protocol (new)
Canonical orchestration state = ONE pinned status comment on the epic issue
(degraded/no-gh mode: a `## Ledger` section in the local epic file). Per child:
state (queued → dispatched(agent-name) → brainstorm-redlined → plan-approved →
executing → PR#m → validated → merged) + key redline decisions + gotchas found;
plus open-questions status, follow-ups filed, DoD status. Rules:
- **Checkpoint discipline:** write the ledger BEFORE every dispatch and AFTER
  every validate/merge verdict.
- **"A decision not in the ledger doesn't exist."**
- Run Step 0 is an **idempotent resume**: read epic + ledger, reconcile against
  ground truth (gh sub-issue states, open PRs, `git worktree list`, TaskList),
  rebuild the TaskList if gone, continue live named agents else re-dispatch
  with the ledger's redlines inlined; NEVER re-dispatch a child whose PR
  exists — validate it instead.
- Auto-memory holds only a pointer + cross-epic traps (one canonical ledger,
  not two drifting ones). Plan mode seeds the ledger skeleton (all children
  queued) when it opens the epic.

### Review fixes folded in (from the 2026-07-05 skill review)
1. Run mode accepts a local epic spec path — closes the "plan degrades to a
   local file but run can't consume it" gap.
2. Seen-RED at plan time only for gates runnable then (pre-fix reproductions);
   gates a child itself builds are flagged "show RED before first use",
   enforced by run's instrument check.
3. `--admin` merge bypass only in solo/owned repos; otherwise request review.
4. The "named background agents stall" lesson gets a verify-current-harness
   caveat before imposing sync-only rails.
5. The 14-vs-15 lesson-count drift in this doc is superseded by this section.

### Content-preservation audit
The port must be content-complete: every section of plan-epic/run-epic maps to
a named location in ship — North Star doctrine, rails, validate/merge recipe,
all 15 lessons, both common-mistakes lists. Mapping verified at build time.

### Validated (2026-07-05) — RED/GREEN evidence
Built with `superpowers:writing-skills` TDD; two scenarios, baseline (old
skills) vs new, all on Opus:
- **Sizing** — RED: given a ~30-line single-chunk ask, the agent right-sized
  to one issue but **had to disobey plan-epic to do it** ("I right-size down
  rather than spin up the epic apparatus") and its improvised issue dropped
  the disciplined fields (no model tier, no seen-RED gate handling). GREEN:
  the single-issue path was followed with **no deviation** ("fully
  sanctioned"), producing a sentinel-based non-gameable gate with the RED
  archived, correctly NOT flagged `show-RED-before-first-use`, MODEL PICK
  recorded, context inlined, correct handoff line.
- **Resume after compaction** — RED: a strong baseline run avoided
  re-dispatching a child with an existing PR only by *deriving* it from the
  collision preflight, and confirmed the design gap in its own words: an
  uncommitted redline is "indistinguishable from 'never decided'". GREEN
  (with a deliberately STALE ledger that didn't know the PR existed):
  ground-truth-wins reconcile executed, ledger corrected preserving the
  redline + gotcha, the no-re-dispatch rule quoted verbatim (not derived),
  and the ledger-held `schema_version` redline enforced as a merge-blocking
  check during PR validation — the exact loss mode the ledger was built for.

## Dogfood trial + tuning (2026-07-01)

Ran `/plan-epic` for real on a "make fingerprints part of the skill definition (retire skills-lock.json)" epic in <project>. Grounding (Step 0) caught two premise problems before any decomposition: "skill"/"fingerprint" are each overloaded (Go-engine domain vs markdown-agent domain), and `skills-lock.json` has **no reader** and was hand-created — so the epic is a convention + validator + migration + lock-removal, not "modify a sync tool." Two tunes applied from the trial:
1. The high-stakes security / threat-model prompts are now explicitly **skip-if-not-applicable** (they were noise on a dev-tooling cleanup).
2. Step 0 gained a **"reality-check the premise against the code"** step (the motivating belief — that a sync tool exists — was wrong; grounding must falsify premises before scoping).
A fresh Opus 4.8 run of the *tuned* skill is being compared head-to-head to judge whether the tuning improved the output.

**Outcome:** the tuned Opus run materially outperformed — it identified the *correct* target (Go `fingerprint/` + `skill/` dialect detection, per `docs/building-a-skill.md:387`: "registering the skill is not enough — you must also teach the fingerprinter") and flagged `skills-lock.json` as a red herring, which the earlier run had missed (it trusted a sub-agent's confident mis-framing instead of re-grounding — the "read the artifact, not the summary" trap). Verified by hand against the repo; user confirmed Domain A. Two further tunes applied: (3) "behavior-preserving refactor → differential/golden oracle, not a migration child"; (4) model-tier reconciled to the strict two-axis gate ("keystone" is a heuristic, not a Fable trigger). Net: plan-epic's premise-check + overloaded-term line is validated as its highest-value step.

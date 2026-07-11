---
name: ship
description: Use when the user types /ship, or asks to plan, scope, or break down a feature, epic, initiative, or multi-issue change into issues; to create a single well-gated issue; to park a future want / durable intention into the local backlog ledger instead of an open issue; to survey where a project stands or pick what to work on next ("what's next?", "what's on the backlog?", "where do we stand?"); or to orchestrate, drive, or execute an epic or issue to a proven, working end state (not just merged PRs). Replaces /plan-epic and /run-epic — use for any ask that previously matched those.
---

# /ship — plan work into provable chunks, then drive it to proven done

One lifecycle for any size of work: shape an ask into **fully testable, fully
validated chunks**, open them as GitHub issues, and orchestrate them to a
demonstrated outcome. Pairs with `choosing-a-model` — invoke it at every model
decision.

## Subcommands (explicit — never guess the mode)

- `/ship plan <idea>` → read `references/plan.md` (under this skill's base directory) NOW and follow it.
- `/ship run <epic# | issue# | path/to/epic-spec.md>` → read `references/run.md` NOW and follow it.
- `/ship scout` → read `references/scout.md` NOW and follow it. Read-only: surveys what's in flight (GitHub / local epic files) and what's parked (`docs/backlog/`, judging wake triggers), then recommends ONE next item and asks which mode follows. Never mutates state, never starts the work.
- `/ship park <intention>` → read `references/park.md` NOW and follow it. Retires a durable *intention* into the local ledger (`docs/backlog/`) instead of leaving it as a rotting GitHub issue; the inverse of plan (which mints issues at work-start). Generic — bootstraps the ledger in any repo on first use.
- **Waking a parked intention:** a ledger entry (`docs/backlog/<slug>.md`, frontmatter `intent:`/`parked:`) passed to `/ship` is ALWAYS a wake, never an epic spec — route it to `references/plan.md` ("Waking a parked ledger entry"), which re-baselines it against current code before minting issues. If such an entry reaches `/ship run`, redirect to plan.
- Bare `/ship` → run scout: the survey ends by asking which mode comes next, which is exactly what a bare `/ship` is asking. Arguments that fit none of the forms → show the forms above and ask which is meant.

Inside run mode, epic-vs-single-issue is decided by FACTS about the target
(epic label, sub-issues present, a spec file with children) — never by the
shape of the argument.

## Shared doctrine (plan + run)

These invariants govern the issue-producing modes. **Park and scout are
deliberately lightweight** and share none of them — no chunk rule, no North
Star, no status ledger; their whole discipline lives in `references/park.md`
and `references/scout.md`.

### The chunk rule — the atomic unit of work
A chunk is a slice that is **independently testable, validated by ONE concrete
non-gameable acceptance gate, and landable as one PR** (an INVEST vertical
slice, not a horizontal layer or a phase). Plan mode sizes an ask by counting
chunks: **1 chunk → a single issue. 2+ chunks → an epic.** Never inflate one
chunk into an epic; never compress multiple chunks into one mega-issue.

### The North Star
Every unit of work commits to an **outcome** with a measurable / demonstrable
signal — never just "it's done". An epic carries the full North Star (goal ·
why/who · how-we'll-know · non-goals · open questions). A single issue carries
the compact form — goal + how-we'll-know — inline in its body.

### The status ledger — state lives outside the conversation
*(Run mode's per-epic progress record — distinct from the intention ledger in
`docs/backlog/` that `park` writes to. Same word, different store.)*
Orchestration state must survive context compaction and session loss.
Canonical state is ONE pinned status comment on the epic issue (no-`gh` mode:
a `## Ledger` section in the local epic file). One line per child:

    #<child> — <state> — <key redline decisions> — <gotchas found>
    states: queued → dispatched(<agent-name>) → brainstorm-redlined →
            plan-approved → executing → PR#<m> → validated → merged
    plus: open-questions status · follow-ups filed · DoD status

- **Checkpoint discipline:** update the ledger BEFORE every dispatch and AFTER
  every validate/merge verdict.
- **A decision not in the ledger doesn't exist.** Write redline decisions there
  the moment you make them — if compaction eats the conversation, the ledger is
  what survives.
- Auto-memory holds only a pointer to the epic plus cross-epic traps. One
  canonical ledger, never two drifting copies.

### Model routing
Default Opus. Sonnet/Haiku only for genuinely mechanical, gate-backed work.
Fable only when complexity AND blast radius are both high. When unsure, invoke
`choosing-a-model` and record its `MODEL PICK:` line.

### The escalation ladder — who decides, and when to block
Decisions derivable from code/spec/evidence: make them yourself (redline,
validate, merge, sequence). Genuine owner-level forks — scope change, gate
weakening or re-reading, close-on-shipped-value, substrate strategy:
- **Owner present** → `AskUserQuestion` with options + a recommendation.
- **Owner away / unattended** → dispatch a `model: fable` decision agent with
  the full brief (what's known, the options, the evidence), VERIFY its
  verdict against live evidence, record it in the ledger, act on it. Only if
  Fable is itself unsure does the question go to the owner.
- A blocking question must NEVER be an unattended session's terminal state —
  if you're about to end a session waiting on the owner, a rung was skipped.

Investigation never needs permission: control runs, instrument-freshness
checks, no-op detection, read-only probes — run them BEFORE escalating; the
brief must contain their results.

---
name: choosing-a-model
description: Use when deciding which Claude model to dispatch or plan with — picking a model for an agent, sub-agent, epic, task, or plan; weighing capability vs cost; or unsure whether work is complex and high-stakes enough to warrant Fable 5 vs Opus 4.8, Sonnet 5, or Haiku 4.5.
---

# Choosing a Model

## Overview

Pick the **cheapest model that will still get the decision right**. Default to **Opus 4.8**; move off it only deliberately — *down* for mechanical/low-stakes work, *up* to **Fable 5** only when a task is **both** highly complex/ambiguous **and** high blast-radius.

Route by **reasoning × blast radius — not by phase.** "Planning" is not automatically Fable; "coding" is not automatically Sonnet. A trivial plan is Haiku-able; a gnarly implementation is Opus/Fable.

## The models (current as of 2026-07 — if a fact looks stale, re-check with the `claude-api` skill or the Models API)

| Model | id | output $/1M | context | Use for |
|---|---|---|---|---|
| **Fable 5** | `claude-fable-5` | $50 | 1M | the hardest **and** highest-stakes *thinking* only |
| **Opus 4.8** | `claude-opus-4-8` | $25 | 1M | **default** — judgment work |
| **Sonnet 5** | `claude-sonnet-5` | $15 | 1M | well-specified non-trivial / high-volume |
| **Haiku 4.5** | `claude-haiku-4-5` | $5 | 200K | mechanical / search / lookups |

Fable ≈ **2× Opus** on output — that's why it's reserved, not default. (Fable is post-cutoff; if you didn't know it existed, that's why. It's real.)

## The gate — when to escalate to Fable

Escalate to Fable **only when both axes are high**:

| | Low blast radius | **High blast radius** |
|---|---|---|
| **Low complexity** | Haiku / Sonnet | Opus |
| **High complexity** | Opus | **Fable** |

- **Blast radius = high** if: irreversible, cross-cutting, client-facing, data-loss/security risk, or it sets an interface/architecture others depend on.
- **Complexity = high** if: ambiguous, novel, long-horizon, or there's no known-good pattern to follow.
- **Within the low/low cell:** mechanical / search / lookup → **Haiku**; writing real code, even simple → **Sonnet**.
- **Hard floor:** Haiku caps at **200K context** (others are 1M) — a task whose working context exceeds that starts at **Sonnet** regardless of the gate.

Volume ≠ complexity: a big-but-well-trodden, reversible refactor is Sonnet/Opus, not Fable. (But very large context or long multi-step trajectories degrade cheaper models' *reliability* — escalate a notch for context-reliability, not because the reasoning got harder. Rule of thumb: ~150–200K tokens of working context, or 30+ tool-call trajectories → one tier up.)

## Tiers — what each is for

- **Fable 5** — architect an extremely complex + high-impact initiative; the keystone/integration design others depend on; root-cause on a load-bearing system where a silent miss is catastrophic; the Definition-of-Done strategy for a big migration. **Not** implementation grind.
- **Opus 4.8 (default)** — per-child implementation needing real judgment; validation/redline; most planning.
- **Sonnet 5** — well-specified non-trivial coding (especially with tests as a success oracle); high-volume work; a worker's own scoped sub-agents.
- **Haiku 4.5** — renames/one-liners, mechanical edits, search/explore sub-agents, trivial reviews, fast lookups.

## Don't overpay (the tension, resolved)

- A Sonnet/Haiku miss that a **gate or test catches** is cheap — use them freely where a gate backs you.
- But a **keystone** quality miss costs far more than the Fable premium — don't cheap out on load-bearing decisions.
- **Escalate only when a smarter model would decide *differently*, not just phrase it nicer.**
- Downgrade the moment the task becomes well-specified and reversible.

## Escalate reactively & split the task

- **Start at the gate-suggested tier, then escalate on failure.** If a cheaper model's output fails its gate/review, or you're re-prompting to fix its *reasoning* (not typos), step up a tier — that failure is the signal (the LLM-cascade pattern). Don't just re-run the same tier.
- **Split within a task, not just across tasks.** Let the strong tier decide *what* to do; let a cheaper tier apply the mechanical change (architect → editor). `/ship` embodies this — keystone reasoning is high-tier; workers grind at their tier.
- **Before escalating, ask "is this actually a one-way door?"** Bias to the cheaper tier on reversible (two-way-door) work; reserve escalation for genuinely irreversible calls.
- **High blast radius → verify regardless of tier.** Run an independent verification pass on a high-stakes output no matter which model produced it.

## Fable operational reality (plan for it before you pick it)

- Thinking is **always on** — you can't disable it. Control depth with `effort` (low→max), not a token budget.
- Turns run **minutes** on hard tasks — plan for timeouts / async check-ins; don't mistake a long run for a hang.
- Use Fable for the hard **thinking**; hand the grinding to Opus/Sonnet workers it directs.
- (API only) safety classifiers can return `stop_reason: "refusal"`, and it needs 30-day data retention — see the `claude-api` skill.
- **If Fable declines or is unavailable, fall back to Opus 4.8** (also the API's own recommended fallback) — never downgrade below the gate's non-Fable answer.

## Output contract

Emit one line others can record and honor:

```
MODEL PICK: <Fable 5 | Opus 4.8 | Sonnet 5 | Haiku 4.5> — <complexity + blast-radius reason>
```

In an epic, record the pick **per child issue**; `/ship` dispatches at that tier and escalates to Fable for a keystone or a gnarly root-cause.

## Common mistakes

- Defaulting to Sonnet "to save money" on judgment-heavy work → a miss costs more than the savings.
- Using Opus/Fable for mechanical work a gate would catch → waste.
- Treating "planning = Fable" → most planning is Opus; Fable is for the extremely complex **and** high-impact plan.
- Forgetting Fable exists (post-cutoff) or misremembering its price/behavior → use the facts above.
- Picking Fable, then being surprised by minute-long turns → that's expected; plan for it.
- Escalating on **volume** (many files, long diff) rather than complexity/blast-radius → volume alone is Sonnet/Opus.

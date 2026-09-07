---
name: ship
description: Use when the user types /ship, or asks to plan, scope, or break down a feature, epic, initiative, or multi-issue change into issues; to create a single well-gated issue; to park a future want / durable intention into the local backlog ledger instead of an open issue; to survey where a project stands or pick what to work on next ("what's next?", "what's on the backlog?", "where do we stand?"); or to orchestrate, drive, or execute an epic or issue to a proven, working end state (not just merged PRs). Replaces /plan-epic and /run-epic — use for any ask that previously matched those.
---

# /ship — plan work into provable chunks, then drive it to proven done

One lifecycle for any size of work: shape an ask into **fully testable, fully
validated chunks**, open them as the delivery contract (GitHub issues, or a
local epic file — the authority envelope's delivery_mode decides), and
orchestrate them to a demonstrated outcome.

## Subcommands (explicit — never guess the mode)

- `/ship plan <idea>` → read `references/plan.md` (under this skill's base directory) NOW and follow it.
- `/ship run <epic# | issue# | path/to/contract.md>` → read `references/run.md` NOW and follow it.
- `/ship scout` → read `references/scout.md` NOW and follow it. Read-only: surveys what's in flight (GitHub / local epic files) and what's parked (`docs/backlog/`, judging wake triggers), then recommends ONE next item and asks which mode follows. Never mutates state, never starts the work.
- `/ship park <intention>` → read `references/park.md` NOW and follow it. Retires a durable *intention* into the local ledger (`docs/backlog/`) instead of leaving it as a rotting GitHub issue; the inverse of plan (which mints issues at work-start). Generic — bootstraps the ledger in any repo on first use.
- **Waking a parked intention:** a ledger entry (`docs/backlog/<slug>.md`, frontmatter `intent:`/`parked:`) passed to `/ship` is ALWAYS a wake, never an epic spec — route it to `references/plan.md` ("Waking a parked ledger entry"), which re-baselines it against current code before minting issues. If such an entry reaches `/ship run`, redirect to plan.
- Bare `/ship` → run scout: the survey ends by asking which mode comes next, which is exactly what a bare `/ship` is asking. Arguments that fit none of the forms → show the forms above and ask which is meant.

Inside run mode, epic-vs-single-issue is decided by FACTS about the target
(epic label, sub-issues present, a spec file with children) — never by the
shape of the argument.

## Shared doctrine (plan + run)

These invariants govern the issue-producing modes. **Park and scout are
deliberately lightweight**: neither sizes chunks, neither carries a North
Star, and neither ever WRITES a status ledger — their discipline lives in
`references/park.md` and `references/scout.md`. But they are not sealed off
from this section, and two dependencies run the other way: **scout READS
the status ledger, and the `<!-- ship:ledger -->` sentinel it locates it by
is defined here and nowhere else**; park cites the named-action rules below
for its origin closure. Do not relocate this section on the theory that the
lightweight modes don't use it — scout would lose the only definition of
the thing it reads.

### The chunk rule — the atomic unit of work
A chunk is a slice that is **independently testable, validated by ONE concrete
non-gameable acceptance gate, and landable as one reviewable landing** — a PR,
or a single local `--no-ff` merge (an INVEST vertical
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
Canonical state is ONE status comment on the epic issue opening with the
sentinel `<!-- ship:ledger -->` — GitHub cannot pin comments, so post it,
READ IT BACK, and on resume locate it by sentinel (duplicates → merge into
the newest, mark the rest superseded). In `local-review` mode it is the
`## Ledger` section of the canonical contract file on the integration
branch. These mode-derived locations are NORMATIVE — no other copy is
canonical. One run-policy header + one line per child:

    policy: <authority envelope — seeded once from the spec, then THE
            canonical live record; run Step 0 fills baseline /
            integration_branch here and reads only this copy>
    #<child> — <state> — <key redline decisions> — <gotchas found>
    states: queued → dispatched(<agent-name>) → brainstorm-redlined →
            plan-approved → executing → PR#<m> | commit(<sha>) →
            validated → merged
    rework:  PR#<m> | commit(<sha>) → rework(<the specific failures>) →
            executing — YOUR validation came back red. This is the most
            frequent path, not an exception; a delivery state with no
            recorded rework reads as "not yet validated", which is a
            different thing and re-validates from scratch after a
            compaction. Record WHAT failed, never just the state.
    owner-gate: queued → awaiting-owner(<gate>) →
            accepted(<decision record/ref>) | rejected → re-plan
    plus: open-questions status · follow-ups filed · DoD status

- **Checkpoint discipline:** update the ledger BEFORE every dispatch and AFTER
  every validate/merge verdict. In file mode a checkpoint ENDS with a commit
  of the epic file — an uncommitted ledger edit is one tree-reset from gone.
- **A decision not in the ledger doesn't exist.** Write redline decisions there
  the moment you make them — if compaction eats the conversation, the ledger is
  what survives.
- Auto-memory holds only a pointer to the epic plus cross-epic traps. One
  canonical ledger, never two drifting copies.

### The authority envelope — capability is never authority
Every outward write in EVERY mode — plan, run, and park's origin closure —
operates under an explicit envelope, derived from
the owner's instructions + the repo's standing rules (repo authority precedes
this skill's generic rails). It is authored into the committed spec at plan
time and seeded ONCE into the ledger's `policy:` line — thereafter the
ledger copy is the single canonical record: run fills runtime fields there
and reads only it; the spec's copy is a plan-time snapshot, never updated
or consulted after seeding. Fields:

    delivery_mode: local-review | github-pr | github-merge
      — the workflow SHAPE only; it authorizes NOTHING
    authorized_external_actions: deny-by-default list of the ONLY outward
      writes permitted, named per action: issue-create · issue-edit ·
      issue-comment · issue-close · push · pr-create · pr-edit ·
      review-request · merge · queue-enqueue · admin-bypass ·
      remote-delete — or none
    landing_authority: <who lands what; --admin ONLY on an explicit owner
      waiver — sole-committer status is never sufficient>
    owner_reserved_decisions: <decisions reserved beyond the ladder's
      standing list>
    stop_at: <boundary ending the run as a deliberate handoff, e.g.
      review-ready>
    baseline: <immutable start SHA — run Step 0 records it>
    integration_branch: <local-review only — `<plan-id>-integration`;
      plan Step 5 / run Step 0 create + record it>
    evidence_home: <durable evidence dir; default
      docs/specs/<plan-id>-evidence/>

Every outward write in every procedure NAMES its action from that list and
runs only if the envelope lists it — an unlisted action takes its stated
fallback (record locally, retain the branch, report the gap in the handoff)
instead. Never infer one action from another: merge does not imply
remote-delete or issue-close. Compound writes need EVERY component
action: close-with-comment = `issue-close` + `issue-comment`. Closing
keywords (`Closes #<n>`) in PR bodies are FORBIDDEN in this workflow
outright — they close at merge, BEFORE the landing record is durable
(evidence-before-close). Every close is a separately-authorized
`issue-close` at a NAMED site — a PR never closes its own issue. The
sites: run Step 2 item 10 (child, post-publication), run's epic close,
run's owner-gate single, park's origin closure, plan's superseded epic. **Coherence check (plan Step 0 + run Step
0):** each delivery_mode has a minimum action set its procedures require —
github modes: `push` + `pr-create` (worker delivery), `issue-create` (the
contract), `issue-comment` (the ledger); `github-merge` additionally
`merge` AND a `landing_authority` naming the orchestrator as lander —
pairing `github-merge` with a pre-landing `stop_at` (e.g. review-ready) is
INCOHERENT: resolve it at Step 0. An envelope granting a mode without its
minimum set is MALFORMED — surface and fix it with the owner at Step 0 (or
take local-review); never discover it mid-run. local-review: if landing is
INTENDED, `landing_authority` must name the orchestrator and `stop_at`
must not bound pre-landing — an intended review-ready boundary is RECORDED
here at plan time, never discovered after worker execution. All other
actions (issue-edit, issue-close, pr-edit, review-request, queue-enqueue,
admin-bypass, remote-delete) are optional and carry per-site fallbacks. Genuinely unsettled and it matters → ask the
owner once at plan time; never infer authority from what `gh` can reach.

### The escalation ladder — who decides, and when to block
Three decision classes:
- **Yours** — derivable from code/spec/evidence: redline, validate, sequence,
  merge (within the authority envelope), stricter-or-equal gate adjudication,
  scope narrowing that still reaches the committed signal.
- **Owner-level forks** — judgment with no derivable answer (gate
  *re-reading*, close-on-shipped-value, substrate strategy):
  - **Owner present** → `AskUserQuestion` with options + a recommendation.
  - **Owner away / unattended** → dispatch a `model: fable` decision agent
    with the full brief (what's known, the options, the evidence), VERIFY its
    verdict against live evidence, record it in the ledger, act on it. Only
    if Fable is itself unsure does the question go to the owner.
- **Owner-reserved — non-delegable.** An advisor/model may RECOMMEND, never
  decide: gate weakening below committed thresholds; scope expansion beyond
  the committed North Star / non-goals; irreversible or destructive
  authorization; outward/external authorization (any envelope change); plus
  whatever the envelope's `owner_reserved_decisions` field declares (e.g.
  governance / contract acceptance). Unattended → record the recommendation
  + evidence in
  the ledger, park the gate `awaiting-owner(<gate>)`, and END as a deliberate
  handoff (run.md state 2) — the correct terminal, not a skipped rung.
- A blocking question must NEVER be an unattended session's terminal state —
  *except a parked owner-reserved gate*; any other end-on-a-wait means a rung
  was skipped.

Investigation never needs permission: control runs, instrument-freshness
checks, no-op detection, read-only probes — run them BEFORE escalating; the
brief must contain their results.

### The run review + skill feedback loop
Every plan or run session closes — in WHICHEVER lifecycle state it ends —
with two artifacts, before the final message:

1. **Release-notes review**, for the returning owner. Epic (or
   many-changes) sessions fill EVERY slot — an empty slot says "none", which
   is itself signal; a single-issue session may stop after the first two:

       SIGNAL   — North Star / DoD result: proven or not, one line of proof
       SHIPPED  — each merge/PR: what + why, one line each
       FIXED    — defects corrected along the way
       FILED    — issues opened
       PARKED   — ledger intentions written
       TRAPS    — lessons/gotchas recorded, and where
       FRICTION — what slowed the session or forced re-work, and the fix
       STATE    — deployment + substrate as left
       NEXT     — the next move

   (Terminal-state-2's resume prompt serves the SUCCESSOR AGENT — a
   different audience; produce both, don't merge them.)
2. **Improvement offers** — even when empty ("no candidates observed this
   session"). Two classes, and the second is the one that gets swallowed:
   - **This skill's wording** — a rule that misfired, a step that read
     ambiguously, a gap that let a defect reach a landing.
   - **Anything else that cost the session time.** The harness or tooling
     fighting you. Work you had to redo. A chunk split too coarse to
     validate honestly, or so fine the landing cost more than the slice. A
     gate slower than the work it guards. A brief you had to reconstruct
     because it drifted from the plan. A permission prompt on the critical
     path. **If it slowed you down or made you repeat yourself, it is a
     candidate — do not filter for whether it is "about ship".**

   Capture candidates at each ledger checkpoint (run) or in the spec's
   decision notes (plan) — end-of-session recall loses them, and friction is
   the class recall loses first, because working around it feels like
   progress. Offer; never auto-apply.

The gate below governs **edits to this skill**. A friction offer that changes
no skill text — a harness setting, a tooling fix, a different split next time —
is reported in FRICTION and needs no panel; it is the owner's call whether to
act, and an unacted friction report is still a kept lesson.

Landing an offered skill change is ALWAYS the owner's decision — never the
unattended-Fable rung; reviewers inform, they don't replace. Gate by class:
- **Mechanical** (typo, broken xref, formatting): normal writing-skills
  checks; no panel.
- **Wording/doctrine**: two or more independently-dispatched reviewers
  briefed to ADJUDICATE — attempt refutation, return REFUTED /
  STANDS-WITH-FIXES / STANDS. **Any surviving, un-rebutted refutation
  blocks; a tie fails closed** (the owner adjudicates fatality). The panel
  SUPPLEMENTS writing-skills discipline (documented baseline; micro-tested
  wording for behavior-shaping text) — it never substitutes for it.
- **Owner-directed edits** land on the owner's word; a panel pass over the
  wording is cheap insurance, not a precondition.
Rejected candidates appear in the review with their refutation — a recorded
rejection is still a lesson kept.

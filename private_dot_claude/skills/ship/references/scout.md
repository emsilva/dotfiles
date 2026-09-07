# /ship scout — survey the landscape, recommend the next move

Read-only reconnaissance ahead of the other modes. The deliverable is a
**conversation-only report**: what's in flight, what's parked (with wake
triggers judged), one reasoned recommendation, and the question "which mode
next?". Scout mutates nothing — no issue closes, no ledger writes, no report
files, no dispatches, no starting the recommended work.

## ★ Altitude — scout reads state, it never settles it ★
Scout's whole discipline is staying shallow. Two neighboring modes own the
deep work, and scout hands off to them instead of doing it:

- **Ledger-vs-reality discrepancies → `/ship run` Step 0.** If a status
  ledger claims something a *cheap* observable contradicts (a "merged" child
  whose gate file doesn't exist), that is ONE flagged line in the report and
  a reason to route to run — whose Step 0 reconciliation exists for exactly
  this. Scout does not adjudicate it: no reflog/stash/worktree archaeology,
  no rewriting ledger lines, no verdict on where the work went.
- **Parked-entry premises → wake (plan.md) re-baselines.** Scout evaluates
  only the `wake:` field. It does not re-judge an entry's Intent or
  perishable notes against current code — that is the wake session's job,
  and doing it early is spend the owner hasn't approved.
- **Depth budget:** epic state comes from the sentinel-marked status-ledger comment
  (local contracts: the file's `## Ledger` section) — never from reading
  child bodies (Step 1's one batched metadata scan reads marker lines
  only, for grouping). Entry state comes from INDEX.md + frontmatter. One cheap
  probe per wake trigger (below). That's the whole read.

## Step 1 — Gather the three stores
Resolve `ROOT` from the main worktree, as park.md does:

    ROOT=$(git worktree list --porcelain | awk '/^worktree /{sub(/^worktree /,""); print; exit}')

- **In flight (GitHub AND local contracts — survey both):** with `gh` + a
  remote, ONE typed paginated scan powers both the listing and the
  grouping:

      gh api --paginate "repos/<owner>/<repo>/issues?state=open&per_page=100" \
        --jq '.[] | select(has("pull_request") | not) | {number, title, body}'

  read ONLY for marker lines — `plan-id:`, `item:`, `engagement-key:`,
  "Part of #" — plus native parent/sub-issue fields where available;
  never a semantic review of child bodies. Epic AND single state comes
  from the sentinel-marked status-ledger comment, never the title line.
  REGARDLESS of `gh`: grep
  `$ROOT/docs/specs/*.md` for a `ship:contract` marker with
  `status=active` — the active local contracts (`kind` says epic|single);
  state from the
  `## Ledger` section. The canonical copy may live ONLY on an integration
  branch: also check each `git branch --list '*-integration'` branch via
  `git grep -l 'ship:contract' <branch> -- docs/specs/` (read-only).
  **One line per contract:** group by plan-id / GitHub parent — dedupe
  working-tree vs integration-branch copies and children under their
  epic; state comes from the canonical ledger location only. A
  specs file WITHOUT the marker is not a contract; `status=completed` is
  done, not in flight;
  merged-but-closure-owed is DONE work awaiting an
  authorized close — report it as that, never as unfinished
  implementation.
- **Parked:** `$ROOT/docs/backlog/` — INDEX.md plus each entry's frontmatter
  (`intent`/`track`/`parked`/`wake`). No ledger directory → note "no
  intention ledger" and move on; scout never bootstraps one.
- **Todos:** lines in `~/TODO.md` tagged `#<this-project>`, if the file
  exists. List them read-only with a pointer to `/todo`; scout doesn't
  manage them.

## Step 2 — Judge wake triggers (the only checking scout does)
For each parked entry with a `wake:` field, classify it:
- **ripe** — the trigger names an observable and ONE cheap read-only probe
  (a grep, a file check, a count) confirms it now holds;
- **not ripe** — the same probe shows it doesn't;
- **can't tell** — the trigger needs evidence that isn't at hand (telemetry,
  production data, an owner judgment). Say so; never build the missing
  instrument at scout time.
Entries with no `wake:` field are listed with their parked date only.

## Step 3 — Rank, then pick ONE recommendation
Order candidates by this ladder — the first non-empty rung wins:
1. **In-flight work not yet at its proven end** — finishing beats starting,
   always. Multiple in flight → the one closest to done. A smelly status
   ledger does NOT demote an epic; it sharpens the routing ("resume via
   `/ship run` — its Step 0 reconciliation will settle #2's real state").
2. **Ripe wake triggers** — route `/ship plan docs/backlog/<slug>.md`.
3. **Project-tagged todos** — route `/ship plan <the ask>`.
4. Nothing above → the field is clear; say so and stop after the report.
State the pick's reasoning in ≤3 sentences. Stale no-trigger entries get at
most one line suggesting a kill/keep look — never a premise investigation.

## Step 4 — Report, then ask
The report is compact — one line per item, this exact shape:

    ## In flight
    - epic #12 / docs/specs/<file>.md — 1/3 merged — #2 mid-flight — [any one-line smell]
    ## Parked (docs/backlog)
    - drop-legacy-config — single config path · tech-debt — parked 2026-05-14 — wake: RIPE (no importers)
    - fast-startup — cold start <2s · performance — parked 2026-06-28 — wake: not ripe
    - dark-mode — terminal light/dark · ux — parked 2025-11-10 — no trigger
    ## Todos (~/TODO.md, #project)
    - <line>  (or omit the section when empty)
    ## Next
    <the ONE recommendation + its ≤3-sentence why>

Then hand the decision to the owner — picking what to work on is theirs:
- **Owner present** → `AskUserQuestion`: the recommendation first, marked
  "(Recommended)", the runner-up candidates, and "just looking". Route the
  answer: in-flight → `/ship run`, ripe entry → `/ship plan <entry>` (a
  wake), new idea → `/ship plan`, retire something → `/ship park`.
- **Unattended** → the report with the printed recommendation IS the
  terminal deliverable. Scout is complete, not blocked — the escalation
  ladder's "never end on a blocking question" applies to blocked work, and
  a finished survey isn't blocked work. Never auto-start the recommended
  work to avoid ending on a question.

## Common mistakes
- **Digging where run reconciles** — reflog/stash/worktree archaeology to
  settle a ledger-vs-tree contradiction. Flag the smell in one line; route
  to `/ship run` Step 0. (Both baseline runs did this — it's the mode's
  strongest temptation.)
- **Re-baselining parked entries** — judging Intent/perishable notes against
  current code at scout time. Only the `wake:` field gets probed.
- **Demoting in-flight work because its ledger smells** — WIP-first holds;
  the smell changes the routing note, not the rank.
- **Prescribing run-mode work** — "overwrite ledger line #1, then rebuild
  child 1" is run's Step 0 output, not scout's report.
- **Reading every child/issue body for STATE** — the status ledger line is
  the state (Step 1's marker-line metadata scan is the one sanctioned
  exception, for grouping only).
- **Writing anything** — a report file, a ledger correction, an INDEX touch.
  Conversation-only.
- **Starting the pick** — scout ends at the question, even unattended.

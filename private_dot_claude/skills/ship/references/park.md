# /ship park — retire a durable intention into the local ledger

The inverse of `/ship plan`. Plan mints issues at the moment work starts; park
does the opposite — it records **what we intend to do** as a durable local entry
and gets it *off* GitHub, so GitHub only ever holds work that is in flight. A
future `/ship` **wakes** the entry, re-baselines it against then-current code,
and mints the issues fresh (see plan.md "Waking a parked ledger entry"). This ledger is
**generic**: any repo you run `/ship park` in gets one, bootstrapped on first use.

## What park is for
- A future want that **outlives today's code** — worth remembering, not worth an
  open issue that will rot before anyone starts it.
- An open GitHub issue that **isn't being driven this week** (its body was scoped
  against code that has since moved).

**Not for:**
- Work in flight right now → that's a `keep`; leave the issue open (or `/ship run`).
- A fact that is already **true** → that's memory (`~/.claude/…/memory/`), not
  intent. The ledger holds wants, not truths.

## The three stores — don't cross them
| Store | Holds | Example |
|---|---|---|
| Memory (`~/.claude/…/memory/`) | what is **true** | traps, recipes, platform facts |
| Ledger (`docs/backlog/`) | what we **intend to do** | "swap the WASM compile step for a native fallback" |
| GitHub issues | what is **in flight** right now | the live epic + its READY children |

(This *intention ledger* is a different thing from run mode's **status ledger**
— the epic's pinned progress comment. Same word, unrelated. Park writes to
`docs/backlog/`, never to an epic comment.)

## ★ Anchor, don't cement — the one rule that makes the ledger work ★
A ledger entry is **not a plan**. A plan is written against code you can see
right now; an intention will be implemented against code you *cannot* see yet —
it may be months and many refactors away. Cementing today's implementation
detail into the entry is exactly what rotted the old issues. So:

- **The `Intent` section is durable — outcome and *why*, never *how*.** No file
  lists, no step-by-step, no design. State what we want to be true and the value
  it delivers, in words that survive refactors. If a sentence would be falsified
  by a rename or a reorg, it's in the wrong section.
- **Every concrete claim about the current code is perishable — anchor it and
  caveat it.** When a fact is genuinely useful (where a thing lives today, a
  count, a measurement), stamp it with **when it was true** (a commit SHA or a
  date) and tell the future reader to **re-check it**:

  > "As of `3ab9bb0f` (2026-07-07) the compile target is hardcoded to WASM in
  > `src/index.ts` — verify this still holds at wake; the module may have moved."

  Never write a code fact as a timeless truth ("the compiler is in
  `src/index.ts`"). Write it as an as-of observation that expects to be wrong.
- **Perishable notes are for the reader at wake to *distrust*.** Their job is to
  give a re-baselining session a head start, not to be believed. Label them
  dated, and phrase them so being stale is expected, not surprising.

Rule of thumb: if removing every anchored/caveated line still leaves the reader
knowing *what we want and why*, the entry is shaped right.

## Step 0 — Settle the entry's fields
From the conversation (ask the owner one or two questions only if it isn't
derivable):
- **intent** — kebab-case slug (uniqueness is enforced in Step 2, once the ledger
  is located).
- **track** — the theme/epic-track it belongs to (or `tech-debt`).
- **the durable intent** — outcome + why (see the rule above).
- **origin** *(optional)* — the open GitHub issue URL(s) this is born from.
- **wake** *(optional)* — the trigger/event that makes it worth doing.
- **perishable notes** *(optional)* — anchored, caveated, dated. Convert relative
  dates ("tomorrow", "next sprint") to absolute ones.

## Step 1 — Locate / bootstrap the ledger (idempotent, generic)
Resolve the ledger against the **main working tree**, never the current checkout
— a gitignored dir is per-checkout, so a ledger written inside a transient
`.claude/worktrees/*` worktree is destroyed when that worktree is pruned:

    ROOT=$(git worktree list --porcelain | awk '/^worktree /{sub(/^worktree /,""); print; exit}')  # main worktree, always listed first; sub() keeps paths with spaces intact
    LEDGER="$ROOT/docs/backlog"

**Guard — is `docs/backlog` already TRACKED in the outer repo?** If
`git -C "$ROOT" ls-files -- docs/backlog` is non-empty, STOP and surface it: this
repo already uses that path for something real; gitignoring won't untrack it and
nesting a repo would hijack it. Pick a different ledger dir or ask the owner.

Otherwise bootstrap (each step a no-op once done):
1. `mkdir -p "$LEDGER/shipped"`.
2. **Gitignore it durably in the outer repo.** If `/docs/backlog/` isn't in the
   outer `.gitignore`, add it and commit **only that file** (the `-- .gitignore`
   pathspec keeps the commit scoped; use `add` + `commit -- <path>`, not
   `commit <path>`, which errors when `.gitignore` is brand-new — the
   fresh-repo case):

       git -C "$ROOT" add .gitignore
       git -C "$ROOT" commit -m "chore: gitignore intention ledger" -- .gitignore

   An uncommitted ignore is one `git checkout` from vanishing, after which the
   ledger becomes pushable to a repo that may be shared or client-facing.
3. **Nest a git repo inside it.** Check the directory, NOT `rev-parse` — a
   gitignored dir is still "inside" the outer work tree, so
   `rev-parse --is-inside-work-tree` returns true and would skip init, sending
   Step 5's commit into the OUTER repo:

       [ -d "$LEDGER/.git" ] || git init "$LEDGER"

   Gitignored means no outer history; the nested repo *is* the backup, invisible
   to the outer repo (no submodule, no nesting conflict).
4. **INDEX.md** — if absent, create it with a self-describing preamble (in a
   generic repo, this is the only in-repo description a clean-context session gets):

       # Intention Ledger — index

       GitHub holds only in-flight work; this ledger holds durable intent. One
       line per intention, grouped by track. Wake via `/ship` from the entry
       (re-baseline against current code first); the entry then moves to
       `shipped/` with its new issue number. Park/wake/kill are the ship skill's
       `park` reference.

## Step 2 — Write the entry (collision-gated)
**Uniqueness gate first.** If `$LEDGER/<slug>.md` already exists, **STOP — do not
overwrite** (a `Write` clobbers it, and Step 3 would append a duplicate INDEX
line). Read it, then either merge the two intentions into one entry (union the
`origin`s, refresh `parked`) or pick a distinct slug. A slug collision usually
means the intentions should merge.

Then write `$LEDGER/<slug>.md`:

```markdown
---
intent: <slug>
track: <track, or tech-debt>
origin: <issue URL(s), comma-separated — optional>
parked: <YYYY-MM-DD>
wake: <trigger — optional>
---

**Intent** (durable): <the outcome we want to be true and why it matters.
Outcome and value only — no implementation plan, no file paths, no design.
Written to survive refactors.>

**Perishable notes** (as of <commit SHA / YYYY-MM-DD>): <anchored, caveated
evidence — where things live today, counts, measurements — each phrased as an
as-of observation that the wake session must re-verify, never trust.>
```

## Step 3 — Index it
Append one line to `INDEX.md` under its `## <track>` heading (add the heading if
the track is new) — on the **merge path** from Step 2's gate, update the existing
line instead of appending, so INDEX never doubles:

    - [<slug>](<slug>.md) — <one-line hook> · <track>

## Step 4 — Close the origin issue(s) (only if born from open issues)
If `origin` names an open GitHub issue **and** `gh` is available, close it by
**URL** (cross-repo safe — `gh issue close <n>` only resolves against the cwd
repo's remote) with a pointer; the closed issue is the free permanent archive,
and the entry must **not** copy its body:

    gh issue close <url> --comment "parked to local backlog: <slug>"

- **Parking an epic?** Close its **unstarted** sub-issues too, same pointer — else
  GitHub isn't at zero. A child **genuinely in flight** forces a `keep`: don't
  park the epic out from under live work.
- **No `gh` / no origin →** skip, and report any un-closable origin as still-open
  debt in the handoff. Never duplicate the issue body into the entry.

## Step 5 — Validate, then commit
Self-check before committing — the entry is durable memory; a bad one rots:
- **Strip-test the Intent:** mentally remove every anchored/dated line — do you
  still know *what we want and why*? If not, implementation detail has leaked in;
  move it to Perishable notes or cut it.
- **Every code claim — anywhere, including the `wake` field and the INDEX hook —
  carries a SHA/date + re-verify caveat.** No code fact stated as timeless truth.
- Slug is unique; INDEX lines == entry files; no issue body copied in.

Then commit the **nested** repo (guarded so it's a no-op-safe idempotent step):

    git -C "$LEDGER" add -A
    git -C "$LEDGER" diff --cached --quiet || git -C "$LEDGER" commit -m "park: <slug> — <hook>"

The gitignored dir's only durability is this commit — make it every park.

## Handoff · Wake · Kill
- **Report:** the slug, where it landed, any origin issue(s) closed (or still-open
  debt if `gh` was unavailable), and the wake trigger.
- **Ripe?** `/ship scout` (scout.md) surveys the ledger read-only and flags
  entries whose `wake:` trigger now holds — the usual way a parked entry gets
  noticed again.
- **Wake** = `/ship` starting *from the entry* — `/ship plan docs/backlog/<slug>.md`.
  It re-baselines the intent against current code (re-judging every perishable
  note, never trusting it), mints the epic/issues fresh, then moves the file to
  `docs/backlog/shipped/` with the new issue number and drops its INDEX line.
  (plan.md, "Waking a parked ledger entry".)
- **Kill** = delete the entry file **and its INDEX line**, commit the nested repo.
  No other ceremony (INDEX lines must always == entry files).

## Common mistakes
- **Cementing today's code into the entry** — the exact rot the ledger exists to
  kill. Implementation detail, file paths, and "the code does X" belong in
  anchored+caveated perishable notes, or nowhere. Intent = outcome + why.
- **A code fact stated as timeless truth** — "the compiler is in `src/index.ts`"
  will be wrong by wake. Stamp it: "as of `<sha>`… verify at wake."
- **Overwriting on a slug collision** — STOP and merge (or re-slug); the existing
  entry is someone's parked intention.
- **Writing the ledger into a worktree checkout** — resolve `ROOT` from the main
  worktree; a gitignored dir dies when its worktree is pruned.
- **Parking work that's in flight** — that's a `keep`; leave the issue open.
- **Parking a fact** — "X is true" is memory, not intent.
- **Copying the closed issue's body into the entry** — the issue is the archive;
  link it via `origin`, don't duplicate what will rot.
- **Leaking the ledger into the outer repo** — commit the `.gitignore` line; never
  nest the repo inside a `docs/backlog` the outer repo already tracks.
- **Forgetting to commit the nested repo** — gitignored, so the commit is the only
  thing standing between the ledger and a lost intention.

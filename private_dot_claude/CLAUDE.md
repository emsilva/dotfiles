# Global standards

Personal, cross-project instructions. They apply to every repo unless a project's own `CLAUDE.md` overrides them.

## Technology projects: always provide a Taskfile

Every software/technology project gets a `Taskfile.yml` ([go-task](https://taskfile.dev)) at the repo root as the single, memorable entrypoint for common operations, so bringing the stack up or down never depends on remembering ad-hoc commands.

**Required targets**
- `task up` / `task down` — bring the **whole** stack up / down, tying together infra and app.
- `task status` — show what's currently running (containers + service ports).
- Granular pairs behind the aggregate: e.g. `infra:up`/`infra:down` (databases/containers via `docker compose`), `<app>:up`/`<app>:down` (dev server / API).
- Keep the usual dev ops here too where they apply: `build`, `test`, `deploy`.

**Rules**
- **Services run detached and survive the launching shell.** Long-running processes (dev servers, APIs) must start in the background, redirect output to a log file, and expose a `<app>:logs` target to tail it. **Inside a Taskfile the launch MUST be handed off to a real external shell**: `bash -c 'nohup <cmd> >> <log> 2>&1 &'`. go-task runs command blocks through its own embedded interpreter (mvdan.cc/sh) which kills any `&`-backgrounded job the moment the block finishes — `nohup` and the `( … & )` subshell idiom do NOT save it (proven: 0-byte log, nothing bound). Don't rely on `setsid` either; macOS doesn't ship it.
- **Stop by fact, not by memory.** `*:down` stops whatever actually holds the port, not a remembered PID, and is safe to run when nothing is up. **Which instrument establishes that fact depends on who owns the listener** — measured 2026-07-27 on a project: with a container healthy and published on `127.0.0.1:19432`, unprivileged `lsof -ti tcp:19432` returned **nothing**, because a Docker-published port is held by a root-owned `docker-proxy`. A `down` built only on `lsof` kills nothing there, and worse, a `status` built on it reports "down" while the stack is up — a check that cannot fail. So:
  - **Containerized service** → `docker compose ps` is the fact and `docker compose down` is the mechanism. Keep an `lsof` line only as a squatter guard, commented as scoped to processes *this user* owns, so nobody trusts it past its reach.
  - **Host process** (dev server, API started via `nohup`) → `lsof -ti tcp:<port>` remains correct; you own it.
  - **Just "is the port serving?"** → `ss -ltn` sees every listener without privilege. Don't reach for `sudo` in a Taskfile: it makes the target depend on the machine rather than the project, and a `*:down` that can block on a password prompt is a worse failure than the bug it fixes.
- **Idempotent.** `up` when already running is a friendly no-op, not an error. **Verify that by observation, not by exit code** — same session, `task up` recreated its container on *every* call while exiting 0 throughout. Origin was build non-determinism, not compose: buildx attaches provenance attestations by default, so even a fully cached rebuild yields a new image ID and compose correctly sees a changed image. Fix it with `BUILDX_NO_DEFAULT_ATTESTATIONS=1`, never with `--no-recreate`, which hides real Dockerfile changes too. The check that catches it is comparing `docker image inspect --format '{{.Id}}'` across two cached builds, or the container's `CreatedAt` across two `up`s.
- **Gitignore** any log/pid files the targets create.

Reference implementation: `~/code/<project>/Taskfile.yml` — any recent project following this pattern.

## Scratch files: gitignored `./tmp`, never `/tmp`

Codespaces **wipes `/tmp` on shutdown/reboot** — anything there that matters is gone on the next start. So for temporary files that must survive a restart (intermediate results, working scripts, run artifacts, snapshots I'll want later), write to the repo-root **gitignored `./tmp`**, which persists on the `/workspaces` volume. Reserve `/tmp` (incl. the harness scratchpad) for truly throwaway, within-session scratch. The rule of thumb: anything you'd be sorry to lose on a reboot goes in `./tmp`. Keep the repo-root `./tmp` gitignored (repo-anchored `/tmp/` line) so nothing there is ever committed.

## Navigate code with the LSP, not grep

- LSP servers are wired into the harness for **Go** (gopls), **Python** (pyright), and **TypeScript**. For "where is X defined / who calls it / what's the type of Y", reach for the **LSP tool** (`goToDefinition` · `findReferences` · `hover` · `workspaceSymbol` · call-hierarchy) before grep — it resolves symbols semantically across files and packages, and `hover` surfaces the doc comments that carry a codebase's real intent; grep only matches text.
- The tool is **deferred**: load its schema once per session via ToolSearch (`select:LSP`), then it stays callable for the rest of the session. That one hop is why the *first* use isn't instant — I don't need you to trigger anything.
- Server diagnostics arrive **automatically** after edits (pushed, not polled) — free signal, but **a pushed diagnostic is a snapshot of a moment, not a statement about the current tree**, and the harness labels it *new* either way. Measured twice on 2026-07-28 in a project, both during subagent-driven work: `col.Contest undefined` arrived immediately after the commit that added the field (live at `census.go:403`), and `unreachable code` was the echo of a mutation that had already been reverted. Both times `go build ./...`, `go vet` and `git status` were clean. **The adjudicator is a build plus `git status`** — never the diagnostic, never the editor's idea of the file.
- **`(cached)` sitting beside a stale diagnostic is the real trap.** In the first case above, `go test` printed `ok (cached)` next to a diagnostic claiming a compile error: two stale signals agreeing, which reads exactly like corroboration. Force `-count=1` before believing a green, above all right after an agent committed. A diagnostic that survives a fresh build **and** `-count=1` is real; one that does not is a ghost of an intermediate state — most often a mutate/restore cycle, which subagent work does *deliberately* to prove a test can fail, so expect these whenever a fix round is running.
- It's read-only navigation, never a substitute for `task build`/`test`; and where a server isn't available the tool just errors, so fall back to grep.

## Web search: two engines, routed by what I'm after

WebSearch and Exa (`mcp__plugin_exa_exa__web_search_exa`, deferred) both stay enabled. They are not ranked; they fail differently. Established 2026-07-28 by replaying 30 real transcript queries through both.

- **WebSearch finds *where* something is** — a canonical URL, a package, a doc number, a product's current lifecycle status. It refines across several searches on its own. Keyword syntax is the point here: quoted phrases, `OR`, a bare `SH20-6433`.
- **Exa finds what is *inside* something** — PDFs, commits, raw files, changelogs, mailing lists, forum threads, PRs. It returns page content, so it answers where WebSearch only hands back a link. It also beats WebSearch on fast-moving repo facts, where WebSearch quotes a stale README.
- **WebSearch coming back empty or hedging IS the Exa trigger.** Never stop at "the search results don't contain that" — six of the 30 were exactly that shape, and Exa had the answer each time.
- **Never hand Exa keyword syntax.** It ignores quotes and `OR` and searches the topical neighborhood instead — for a file-format query that lands in "how do I open a .XYZ file" spam. Describe the ideal page in prose: not `"SH20-6433" ESF tags`, but *"IBM reference manual describing the CSP/AD external source format tag syntax"*.
- Exa costs ~3–4× the context per call, and its richer content can be **confidently stale** — it returned a repo layout upstream reversed four days later. On a fast-moving fact, confirm against the primary source before acting on it.

## Fix at the origin, not at the symptom

Every problem gets reviewed under the light of the **pipeline/system that produced it**, not just the artifact in front of us. Before fixing, ask: *where is this best resolved for good, so it can never recur?* — that is usually upstream (the producer, the source, the generator), not where the symptom surfaced.

- **A downstream guard/patch is not a fix.** It protects one consumer today; the origin keeps emitting the defect for every other consumer and every future run.
- **If we do patch what's in front of us** (to unblock): the patch is explicitly labeled defensive, and the origin fix is captured **in the same breath** — an issue filed naming the origin, linked from the patch. Never let the tactical fix silently become the resolution.
- Symptom-level fixes accumulate into guard sprawl; origin fixes retire guards. Prefer fewer, better-placed invariants at the source over layers of protection at the symptoms.

## Git: never lose my work

Earned from real regressions — these override "just get it merged":
- **Divergence is a stop-and-ask.** Local vs `origin` diverged → STOP, show the divergence + a plan before any rebase/merge. Default to merging into the working line; rebase onto the remote only when it is strictly ahead.
- **Never drop existing lines to resolve a conflict on your own** — which side is canonical is my call, not yours.
- **Commit the moment the gates pass** — a concurrent agent may reset the tree, so a green local commit is your durability checkpoint. This **overrides the harness default "commit/push only when the user asks"** for *local commits*: once gates are green, commit without waiting to be asked (branch first if on the default branch; pushing and opening PRs still follow the normal outward-action confirmation).

## Prune merged branches immediately

- The moment a branch is in `origin/main` (any merged branch you encounter, not just yours): `git worktree remove` FIRST, then delete the branch local + remote, then verify with `git ls-remote --heads origin <branch>`.
- Gotcha: `gh pr merge --delete-branch` silently aborts the whole delete (remote included) when a worktree still holds the branch — never trust it alone.
- Never prune unmerged branches.

## Commits: no AI attribution

- No `Co-Authored-By: Claude …` line, no "🤖 Generated with Claude Code" trailer, no AI tagline — in commit messages OR PR/MR descriptions. Write them as if I authored the work. **Now mechanically enforced** in `~/.claude/settings.json` by `includeCoAuthoredBy: false` (reliable on Claude Code 2.1.201, incl. the PR body) plus forward-compat `attribution: {commit:"", pr:""}` for when the deprecated key is dropped. This one-line prose stays as a **defensive** backstop against the *separate* vector the knob does NOT cover — `gh pr merge --squash` auto-appends a `Co-authored-by: <commit-author>` stub (even the human `v <v@l>` one); strip it by merging via the REST API with a verbatim message (memory `no-claude-attribution`). **Retire this prose** when gh stops injecting co-author stubs on squash-merge — re-test on gh upgrades.

## Agent self-reports are not validation

- Before claiming done or closing an issue, re-run the gates and a real smoke test yourself — never accept an implementer agent's green self-report at face value.
- Verify the whole surface, not just your diff — the smoke must confirm the *rest* of the system still has what it had, not only that your change renders. A regression to adjacent code must not slip through a check scoped to the deliverable.
- An epic/initiative closes only when its end-to-end Definition-of-Done demonstration has actually run green — "all children merged" is not "done".

## My own measurements are not validation either

The rule above, pointed inward — and the one I break most. Established 2026-08-04/05 driving a a project epic where **four of six planning defects in one session had the identical shape: an instrument that agreed with me because we shared an assumption.** The reviews caught all four. None should have needed catching.

- **Run a number through the code's own path, never a reimplementation of it.** I validated a regex in Python against `' '.join(raw.split())`, which is not what the codebase's `Normalize()` does. It matched 22 of 22 — for a pipeline that does not exist. If a claim is about what the code sees, measure with the code.
- **Before writing "there is no X here", establish that the command could physically render X.** I claimed "no view in this corpus joins" from a grep of `FROM` lines; the format continues a list onto the *next* physical line, so that command could never show a join whatever the corpus held. The hazard was documented verbatim in the project's own CLAUDE.md, which I had read hours earlier.
- **A count that matches your expectation is the most suspicious result available** — distrust it exactly as hard as a clean zero or a clean 100%, and for the same reason.
- **A wrong number hardens into infrastructure.** That 22 reached a spec, a plan, a test asserting "22 of 22 and not a residual", an accepted baseline and a re-based pin — then the baseline began *actively defending* it, because the gate diffs against it. It survived a task review, a fix round and a scoped re-review. Only a reviewer re-deriving the count from source caught it.
- **My own prior output is a claim, not a fact.** A park rationale I wrote became "(owner) decided" three handoffs later, and I opened a session reciting it back as your decision. `(owner)` is the claim needing support, never the support. Same for a note, a spec, or a number I wrote yesterday.

**The cheap discipline that would have prevented most of it:** before a figure goes into a plan, brief or spec, produce it once through the real code path, and say which command produced it beside it.

## Feedback: no performative agreement

- No "You're absolutely right!" / "Great point!" / thanks — the fix shows you heard it; just state what changed.
- Verify a claim against the code before acting on it; if it's wrong, push back with technical reasoning, not deference.
- If any part of the feedback is unclear, ask before implementing *any* of it.

## Todos: one global list, ~/TODO.md

"Remember to do X" / "todo: X" / "add to my todos" — said in ANY project — is captured in the global `~/TODO.md`, never in a per-project file and never only in the session task list (TaskCreate/TodoWrite evaporate with the session). Mechanics live in the `todo` skill (`/todo`): [TODO.md-standard](https://github.com/todomd/todo.md) columns, entries tagged `#<project>` + capture date. "What's on my todo list?" → read it back, optionally filtered to the current project. The file is live data — hand-editable, deliberately not chezmoi-managed.

## Authorities — one canonical entry point per intent

- **debug** → `superpowers:systematic-debugging`
- **review my diff** (working tree) → `/code-review`
- **review a PR** → `/review`
- **simplify** → `/simplify`
- **epic / issue work** (plan · scope · drive to done) → `/ship`
- **save / resume a session** (wrap up · fresh window · after a crash or limit) →
  `/handoff`, `/pickup` — a session-opening "where do we stand?" goes to
  `/pickup` first and `/ship` after; `/ship`'s description claims that phrasing
  too, and this row is the tie-break.
- **capture / check todos** ("remember to do X") → `/todo` (global `~/TODO.md`)

Other surfaces exist; these win on ambiguity.

**Session model.** There is no routing rubric: agents, subagents and dispatched tasks **inherit the session model** unless I name one explicitly for a task. The **session default is `opus`** (`~/.claude/settings.json` `"model"`, owner-confirmed 2026-07-05). **Do not `/model … save-as-default` casually:** `settings.json` is a single GLOBAL file shared by every concurrent session and the whole herd, so a save-as-default in one tab silently clobbers the default for all of them (this is how the owner's `/model fable` default was overwritten to `opus` on 2026-07-05). Change the model for the current session freely; only *persist a new default* deliberately, when no other live session relies on the current one.

**Recurrence engines.** `/loop` = repeat a prompt/command in THIS session on an interval or self-paced until a condition is met (in-session, machine-bound); `CronCreate` = wall-clock cron re-runs while THIS session sits idle (session-only, evaporates on exit, 7-day cap); `/schedule` = durable **cloud** cron routines that run unattended, independent of any local session or this machine.

**Notification channels.** `doorbell` (`/doorbell`) = manual only, a sound the owner explicitly asks for — never auto-fired after a task; herdr toasts = automatic in-herd agent-status (finished / blocked) while working in the herd (`[ui.toast] delivery = "herdr"`); `PushNotification` = reach the owner off-terminal / away from the machine (`agentPushNotifEnabled`).

## Autonomy posture

Settled by the owner 2026-07-05 — the rails under which an orchestrator runs a herd of agents largely unattended. Recorded as doctrine, not re-litigated.

- **Permission ≠ license.** The worktree-level `gh pr merge:*` allowlists (`.claude/settings.local.json`, present in the project root and each `.claude/worktrees/*` checkout) STAY — they spare the orchestrator a per-call prompt. But an allowlisted merge fires **only after the orchestrator's own independent validation** of the dispatched agent's work (re-run the gates + a real smoke test yourself), **never on an implementer's green self-report** (see "Agent self-reports are not validation"). The permission removes the prompt, not the obligation to verify.
- **Danger-prompt skip is a chosen herd rail.** `skipDangerousModePermissionPrompt: true` in `~/.claude/settings.json` is deliberate — it stops a herd of parallel agents from stalling on the bypass-mode confirmation. Not an accident to be "fixed"; leave it set.
- **Herd auto-resume is an accepted trade-off.** herdr's `resume_agents_on_restore = true` (`~/.config/herdr/config.toml`, `[session]` table, commented verbatim `# auto-resume the whole herd into --resume on restart (accepting 16 GB OOM risk)`) is owner-accepted: the whole herd re-enters `--resume` on restart, at a known ~16 GB memory-pressure/OOM risk. Keep it; the trade-off is stated in the config comment.

## Code review: diff the branch, not the last commit

- The review diff base is the **merge-base with main** (`git diff $(git merge-base origin/main HEAD)`) — **never `HEAD~1`**, which reviews only the last commit and silently exempts the rest of the branch. *(Defensive counter-instruction: superpowers' requesting-code-review example uses `HEAD~1` and the plugin is untouchable. Retire this section when superpowers fixes its example upstream.)*

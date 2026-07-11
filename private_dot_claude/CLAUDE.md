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
- **Stop by fact, not by memory.** `*:down` kills whatever actually holds the port (`lsof -ti tcp:<port>`), not a remembered PID, and is safe to run when nothing is up.
- **Idempotent.** `up` when already running is a friendly no-op, not an error.
- **Gitignore** any log/pid files the targets create.

Reference implementation: `~/code/<project>/Taskfile.yml` — any recent project following this pattern.

## Navigate code with the LSP, not grep

- LSP servers are wired into the harness for **Go** (gopls), **Python** (pyright), and **TypeScript**. For "where is X defined / who calls it / what's the type of Y", reach for the **LSP tool** (`goToDefinition` · `findReferences` · `hover` · `workspaceSymbol` · call-hierarchy) before grep — it resolves symbols semantically across files and packages, and `hover` surfaces the doc comments that carry a codebase's real intent; grep only matches text.
- The tool is **deferred**: load its schema once per session via ToolSearch (`select:LSP`), then it stays callable for the rest of the session. That one hop is why the *first* use isn't instant — I don't need you to trigger anything.
- Server diagnostics arrive **automatically** after edits (pushed, not polled) — treat them as free signal. It's read-only navigation, never a substitute for `task build`/`test`; and where a server isn't available the tool just errors, so fall back to grep.

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
- **capture / check todos** ("remember to do X") → `/todo` (global `~/TODO.md`)

Other surfaces exist; these win on ambiguity.

**Model routing.** `choosing-a-model` is the SOLE authority for which model an agent, subagent, epic, or task runs on — it routes per-task (escalate to Fable only for genuinely complex / high-stakes work; drop to Sonnet/Haiku for trivial). It **subordinates** two other model-guidance sources, which are inputs, not deciders: superpowers' "use the least powerful model that can do the job" line, and the harness "inherit the parent/default model" behavior. *(This subordination clause is **defensive** — superpowers' text is upstream and untouchable under the plugin constraint; retirement condition: superpowers aligns its model guidance with `choosing-a-model` upstream.)* The **session default is `opus`** (`~/.claude/settings.json` `"model"`, owner-confirmed 2026-07-05), a capable middle tier — Fable is dispatched explicitly per task, never as a blanket default. **Do not `/model … save-as-default` casually:** `settings.json` is a single GLOBAL file shared by every concurrent session and the whole herd, so a save-as-default in one tab silently clobbers the default for all of them (this is how the owner's `/model fable` default was overwritten to `opus` on 2026-07-05). Change the model for the current session freely; only *persist a new default* deliberately, when no other live session relies on the current one.

**Recurrence engines.** `/loop` = repeat a prompt/command in THIS session on an interval or self-paced until a condition is met (in-session, machine-bound); `CronCreate` = wall-clock cron re-runs while THIS session sits idle (session-only, evaporates on exit, 7-day cap); `/schedule` = durable **cloud** cron routines that run unattended, independent of any local session or this machine.

**Notification channels.** `doorbell` (`/doorbell`) = manual only, a sound the owner explicitly asks for — never auto-fired after a task; herdr toasts = automatic in-herd agent-status (finished / blocked) while working in the herd (`[ui.toast] delivery = "herdr"`); `PushNotification` = reach the owner off-terminal / away from the machine (`agentPushNotifEnabled`).

## Autonomy posture

Settled by the owner 2026-07-05 — the rails under which an orchestrator runs a herd of agents largely unattended. Recorded as doctrine, not re-litigated.

- **Permission ≠ license.** The worktree-level `gh pr merge:*` allowlists (`.claude/settings.local.json`, present in the project root and each `.claude/worktrees/*` checkout) STAY — they spare the orchestrator a per-call prompt. But an allowlisted merge fires **only after the orchestrator's own independent validation** of the dispatched agent's work (re-run the gates + a real smoke test yourself), **never on an implementer's green self-report** (see "Agent self-reports are not validation"). The permission removes the prompt, not the obligation to verify.
- **Danger-prompt skip is a chosen herd rail.** `skipDangerousModePermissionPrompt: true` in `~/.claude/settings.json` is deliberate — it stops a herd of parallel agents from stalling on the bypass-mode confirmation. Not an accident to be "fixed"; leave it set.
- **Herd auto-resume is an accepted trade-off.** herdr's `resume_agents_on_restore = true` (`~/.config/herdr/config.toml`, `[session]` table, commented verbatim `# auto-resume the whole herd into --resume on restart (accepting 16 GB OOM risk)`) is owner-accepted: the whole herd re-enters `--resume` on restart, at a known ~16 GB memory-pressure/OOM risk. Keep it; the trade-off is stated in the config comment.

## Code review: diff the branch, not the last commit

- The review diff base is the **merge-base with main** (`git diff $(git merge-base origin/main HEAD)`) — **never `HEAD~1`**, which reviews only the last commit and silently exempts the rest of the branch. *(Defensive counter-instruction: superpowers' requesting-code-review example uses `HEAD~1` and the plugin is untouchable. Retire this section when superpowers fixes its example upstream.)*

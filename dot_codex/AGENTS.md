# Global standards

Personal, cross-project instructions for Codex. They apply to every repository unless a closer project `AGENTS.md` or `AGENTS.override.md` supplies more specific guidance.

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

## Navigate code semantically when available

- For "where is X defined / who calls it / what's the type of Y", prefer an actually available semantic/LSP tool over text search. It resolves symbols across files and packages, and hover/documentation surfaces often carry the codebase's real intent.
- Use semantic tools only when they are exposed in the current session; otherwise use `rg` / `rg --files` and inspect the actual code and wiring. Never claim unavailable LSP tooling or diagnostics exist.
- Semantic navigation is read-only assistance, never a substitute for the repository's build, test, or smoke gates.

## Fix at the origin, not at the symptom

Every problem gets reviewed under the light of the **pipeline/system that produced it**, not just the artifact in front of us. Before fixing, ask: *where is this best resolved for good, so it can never recur?* — that is usually upstream (the producer, the source, the generator), not where the symptom surfaced.

- **A downstream guard/patch is not a fix.** It protects one consumer today; the origin keeps emitting the defect for every other consumer and every future run.
- **If we do patch what's in front of us** (to unblock): the patch is explicitly labeled defensive, and the origin fix is captured **in the same breath** — an issue filed naming the origin, linked from the patch. Never let the tactical fix silently become the resolution.
- Symptom-level fixes accumulate into guard sprawl; origin fixes retire guards. Prefer fewer, better-placed invariants at the source over layers of protection at the symptoms.

## Git: never lose my work

Earned from real regressions — these override "just get it merged":

- **Divergence is a stop-and-ask.** Local vs `origin` diverged → STOP, show the divergence + a plan before any rebase/merge. Default to merging into the working line; rebase onto the remote only when it is strictly ahead.
- **Never drop existing lines to resolve a conflict on your own** — which side is canonical is my call, not yours.
- **Commit the moment the gates pass** — a concurrent agent may reset the tree, so a green local commit is your durability checkpoint. This overrides a default of "commit only when asked" for **local commits**: once gates are green, commit without waiting to be asked (branch first if on the default branch; pushing and opening PRs still follow the normal outward-action confirmation).

## Prune merged branches immediately

- The moment a branch is in `origin/main` (any merged branch you encounter, not just yours): `git worktree remove` FIRST, then delete the branch local + remote, then verify with `git ls-remote --heads origin <branch>`.
- Gotcha: `gh pr merge --delete-branch` can abort branch deletion when a worktree still holds the branch — never trust it alone.
- Never prune unmerged branches.

## Commits: no AI attribution

- No `Co-Authored-By` line for Codex, Claude, OpenAI, or another model; no "generated with AI" trailer or tagline in commit messages or PR/MR descriptions. Write them as if I authored the work.
- Verify squash-merge messages before landing. If `gh pr merge --squash` injects an unwanted co-author stub, merge through the API with the intended verbatim message instead of accepting the generated text.

## Agent self-reports are not validation

- Before claiming done or closing an issue, re-run the gates and a real smoke test yourself — never accept an implementer agent's green self-report at face value.
- Verify the whole surface, not just your diff — the smoke must confirm the *rest* of the system still has what it had, not only that your change renders. A regression to adjacent code must not slip through a check scoped to the deliverable.
- An epic/initiative closes only when its end-to-end Definition-of-Done demonstration has actually run green — "all children merged" is not "done".

## Feedback: no performative agreement

- No "You're absolutely right!" / "Great point!" / thanks — the fix shows you heard it; just state what changed.
- Verify a claim against the code before acting on it; if it's wrong, push back with technical reasoning, not deference.
- If any part of the feedback is unclear, ask before implementing *any* of it.

## Todos: one global list, ~/TODO.md

- "Remember to do X" / "todo: X" / "add to my todos" — said in ANY project — is captured in the global `~/TODO.md`, never in a per-project file and never only in an ephemeral session task list.
- Follow the [TODO.md standard](https://github.com/todomd/todo.md): entries are tagged `#<project>` and include the capture date. "What's on my todo list?" reads this file back, optionally filtered to the current project.
- `~/TODO.md` is the authority. Use a Codex `todo` skill only when one is actually installed and exposed; otherwise read or edit the file directly.
- The file is live data — hand-editable, deliberately not chezmoi-managed.

## Authorities — one canonical entry point per intent

- **debug** → `systematic-debugging`.
- **review received feedback** → `receiving-code-review`.
- **validate completed implementation** → `verification-before-completion`, followed by `requesting-code-review` when an independent review is warranted.
- **review my diff or a PR** → a direct, findings-first review against the branch merge-base; do not substitute `HEAD~1`.
- **simplify** → a direct, tightly scoped simplification review.
- **epic / issue lifecycle work** → the `$ship` skill, with an explicit `$ship plan`, `$ship run`, `$ship scout`, or `$ship park` mode; never invoke it implicitly for ordinary implementation.
- **capture / check todos** → `~/TODO.md`, using a `todo` skill only if one is available.

Other surfaces exist; these win on ambiguity.

**Model routing.** The active Codex session/profile and role-specific config are the authority for model choice. Subagents use their configured role model when present and otherwise inherit the active/default configuration. The global model/profile in `~/.codex/config.toml` is shared by future sessions, so never persist a different default as an incidental task step. Read the active config when the exact default matters; do not duplicate a potentially stale model name here.

**Recurrence engines.** Current-thread waiting or monitoring uses the available Codex wait/monitor/continuation mechanism. Durable scheduled work uses Codex Automations when explicitly requested and available.

**Notification channels.** Configured Codex notifications and herdr status toasts may fire automatically. Manual sounds or out-of-band messages happen only when explicitly requested. Do not change `notify`, TUI notification, or herdr delivery settings as an incidental task step.

## Autonomy posture

Settled by the owner — these are the rails under which an orchestrator runs agents largely unattended.

- **Permission ≠ license.** Approval, sandbox, and allowlist settings remove prompts or grant capability; they do not authorize an action outside the task. A merge fires only after the orchestrator's own independent validation (re-run the gates + a real smoke test), never on an implementer's green self-report.
- **Global runtime settings are deliberate.** Do not change `~/.codex/config.toml` approval, permission, model, notification, or multi-agent defaults unless the task explicitly targets them.
- **Herd auto-resume is an accepted trade-off.** herdr's `resume_agents_on_restore = true` (`~/.config/herdr/config.toml`, `[session]` table) is owner-accepted: the whole herd re-enters resume on restart, at a known memory-pressure/OOM risk. Keep it; the trade-off is stated in the config comment.

## Code review: diff the branch, not the last commit

- The review diff base is the **merge-base with main** (`git diff $(git merge-base origin/main HEAD)`) — **never `HEAD~1`**, which reviews only the last commit and silently exempts the rest of the branch.

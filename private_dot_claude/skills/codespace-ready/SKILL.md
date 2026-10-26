---
name: codespace-ready
description: "Use when moving a project to a Codespace, \"bring this work to a codespace\", \"put anything uncommitted in .scratch\", or deleting or replacing a Codespace."
---

# Codespace ready

Only pushed commits and `.scratch/` (the setup syncs it) survive a deleted Codespace. Carry into `.scratch/` everything the work needs that Git does not hold. The Codespace is the owner's workspace, not a third party. Copy, never move. Never push without an explicit OK.

## What already travels

Do not copy these, and do not ask:

| What | How |
|---|---|
| Claude memory | Seeded at `.scratch/memory/claude`; `autoMemoryDirectory` points there |
| Conversations | Conversation sync |
| `.scratch/` markers | `.scratch/README.md` and `.scratch/.gitignore` are the setup's. Never edit or commit them |
| Gitignored `.env` files | Copied at `task work:cs`, never overwriting. Never print a key or copy one into `.scratch` |
| Agent sign-ins | Planned with the devcontainer setup, not here |

## Procedure

Inventory first. Read-only; it never writes, fetches or pushes:

```bash
python3 -I ~/.claude/skills/codespace-ready/scripts/inventory.py
```

Pass `--repo <path>` if this is not the project root. Repeat a `could not check` line; do not invent it.

1. **Inventory.** Result: the script's Markdown report, one section per check.

2. **Sort** each item into one group below. Result: a sorted list. Any owner question is one batch, not yet sent.

3. **Copy, never move.** Result: originals still exist. `inputs/` is what the code reads, mapped back. `reference/` is reference the owner gave. Working state, without bulk. `repo/` is the bundle and dirty-worktree patches. Outside the repo, copy results a tracked script reads, leave raw logs, and record the remap. Leave rebuildable caches.

4. **Unpushed work.** Result: the owner agreed and the push succeeded, or `.scratch/repo/` has a `git bundle --all` that `git bundle verify` accepts, plus a patch, status and untracked files for each dirty worktree. Otherwise nothing was pushed.

5. **Secrets check** on every copied text file. Result: file names and kinds only (key id, token, private-key block, or an assignment of `api_key`, `secret`, `password` or `token`). Never print the match. Remove a matching file from `.scratch`. Do not copy `.env`.

6. **`.scratch/RESTORE.md`**, updated in place. Result: the contract below. Not a dated file under `.scratch/tmp/`.

7. **Proof.** Result: a fresh clone or worktree, restored only from `.scratch` (and the bundle, if unpushed commits are required), passes the gates. If a gate fails, stop. That failure leads the report, with the missing item named.

8. **Branch-only tasks.** Result: each task that exists only on an unmerged branch is in the report's opening and in RESTORE.md. Annotate each `.scratch/memory/` mention in place with `(only on branch X; not on main)`. Do not rewrite it. Name the default branch if it is not `main`.

## Sorting

| Group | What | Action |
|---|---|---|
| Already in Git | Tracked files, pushed commits | Leave them. Say so |
| Carried by the setup | Memory, conversations, `.scratch` markers, `.env` | Do not copy. Name how they travel |
| Goes to `.scratch` | What the work reads, reference the owner gave, working state, outside-repo results, unpushed commits | Copy. Map each input back |
| Rebuildable | `node_modules`, `.venv`, `__pycache__`, `dist`, `build`, `.task`, `target`, other caches, raw logs | Leave them. Write how to rebuild |
| Owner's call | Client or licensed data, and anything large | One batched question |

Carry by default what the work reads and reference the owner gave (licensed pages a test reads, a reference PDF, a client extract, grading results). Only client or licensed data, and anything large, waits for one question: each item's size, and what breaks without it. Recommend copying what the work reads. If nobody can answer, hold it back. The report opens with **What won't work on the Codespace until you answer** (one line per item and the gate that fails). A failing proof uses that opening, not a footnote.

## `.scratch/RESTORE.md`

Update in place. Sections, in order:

1. **What is here** — path, what it is, why it is not in Git, where it maps back.
2. **Restore** — commands with Codespace paths (`/workspaces/<name>` unless the project says otherwise). Inputs land where the code reads them. Bundle fetch when one was written.
3. **Things that will bite** — absolute paths and the remap; branch-only tasks; rebuild commands; raw logs left out; anything held back.
4. **Restoring old branches** — only if a bundle was written; otherwise omit.

## Common mistakes

- Holding back licensed fixtures, a reference PDF, a client extract or grading results, as if the Codespace were a third party. The gates must be able to pass there.
- Accepting a failing proof. A red gate leads the report, with the missing item named.
- Telling the owner to make a key a Codespaces secret, or asking to commit `.scratch/README.md` and `.gitignore`. The setup carries both.
- Writing `.scratch/tmp/handoff-<date>/HANDOFF.md` instead of `.scratch/RESTORE.md`.
- Excluding `.env` by name and not scanning what was copied. Scan every copied text file. Names and kinds only.
- Burying `task cs:ports:up` (only on `feat/ports`) in a handoff. Opening of the report, RESTORE.md, and the memory note: `(only on branch feat/ports; not on main)`.
- Leaving out a folder outside the repo that a tracked script writes. Carry the results the work reads, leave raw logs, record the remap.

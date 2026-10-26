---
name: codespace-ready
description: "Use when moving a project to a Codespace, \"bring this work to a codespace\", \"put anything uncommitted in .scratch\", or deleting or replacing a Codespace."
---

# Codespace ready

Only pushed commits and `.scratch/` survive a deleted Codespace. Carry into `.scratch/` everything the work needs that Git does not hold. Copy, never move. Never push without an explicit OK.

## What already travels

Do not copy or ask:

| What | How |
|---|---|
| Claude memory | Seeded at `.scratch/memory/claude`; `autoMemoryDirectory` points there |
| Conversations | Conversation sync |
| `.scratch/` markers | `.scratch/README.md` and `.scratch/.gitignore` are the setup's. Never edit or commit them |
| Gitignored `.env` files | Copied at `task work:cs`, never overwriting. Never print or copy a key |
| Agent sign-ins | Planned with the devcontainer setup, not here |

## Procedure

Inventory first. It never writes, fetches or pushes:

```bash
python3 -I ~/.claude/skills/codespace-ready/scripts/inventory.py
```

Pass `--repo <path>` outside the project root. Repeat `could not check`; do not invent it.

1. **Inventory.** Result: the script's report.

2. **Sort** each item into one group below. Result: a sorted list. Any owner question is one batch, not yet sent.

3. **Copy, never move.** Result: originals still exist. Read-only inputs go in `inputs/` and are copied back. Reference the owner gave goes in `reference/`. Working state the next session writes goes into `.scratch/`; RESTORE.md symlinks the old path there (`ln -s ../.scratch/<name> <old-path>`). Outside the repo, copy results a script reads, leave raw logs, record the remap. Leave caches. `repo/` holds the bundle and dirty-worktree patches.

4. **Unpushed work.** Result: the owner agreed and the push succeeded, or `.scratch/repo/` has a `git bundle --all` that `git bundle verify` accepts, plus a patch and untracked files per dirty worktree. Before the bundle, point `refs/keep/<name>` at each commit on no branch. Otherwise nothing was pushed.

5. **Secrets check** on every copied text file. Result: file names and kinds only. Never print the match. Do not copy `.env`. Take a match out of `.scratch` and list it under the owner's call with the kind. If a gate needs it, name it in **What won't work…**. A fake password or stub key still matches; the owner decides.

6. **`.scratch/RESTORE.md`**, updated in place. Result: the contract below. Not a dated file under `.scratch/tmp/`.

7. **Proof.** Result: a fresh clone or worktree, restored only from `.scratch` (and the bundle, if unpushed commits are required), passes the gates. If a gate fails, stop. That failure leads the report, with the missing item named.

8. **Branch-only tasks.** Result: each task only on an unmerged branch is in the report's opening and in RESTORE.md. Annotate each memory mention: `(only on branch X; not on main)`. Do not rewrite it. If the default branch is not `main`, name it.

## Sorting

| Group | What | Action |
|---|---|---|
| Already in Git | Tracked files, pushed commits | Leave them |
| Carried by the setup | Memory, conversations, `.scratch` markers, `.env` | Do not copy. Say how |
| Goes to `.scratch` | What the work reads, reference the owner gave, working state, outside-repo results | Copy. Map each input back |
| Rebuildable | `node_modules`, `.venv`, `__pycache__`, `dist`, `build`, `.task`, `target`, other caches, raw logs | Leave them. Write how to rebuild |
| Owner's call | Client or licensed data, anything large, a needed file the secrets scan matched | One batched question |

Carry by default what the work reads and reference the owner gave (licensed pages, a reference PDF, a client extract, grading results). Only client or licensed data, and anything large, waits for one question: size, and what breaks without it. Recommend copying what the work reads. If nobody answers, hold it back. Open with **What won't work on the Codespace until you answer**, not a footnote.

## `.scratch/RESTORE.md`

Update in place. Sections, in order:

1. **What is here** — path, what it is, why it is not in Git, where it maps back.
2. **Restore** — Codespace paths (`/workspaces/<name>`). Read-only inputs are copied back. Working state is a symlink to the `.scratch` copy. Bundle fetch when one was written, including `refs/keep/*`.
3. **Things that will bite** — path remaps; branch-only tasks; rebuild commands; raw logs left out; anything held back; images the docker section lists (rebuild a Mac arm64 image on the Codespace); pinned tool versions.
4. **Restoring old branches** — only if a bundle was written; otherwise omit.

## Common mistakes

- Holding back what the work reads. The Codespace is the owner's workspace; the gates must pass there.
- Accepting a failing proof. A red gate leads the report, with the missing item named.
- Making a key a Codespaces secret, or committing `.scratch/README.md` and `.gitignore`. The setup carries both.
- A dated handoff under `.scratch/tmp/` instead of `.scratch/RESTORE.md`.
- Skipping the secrets scan, or deleting a match and moving on when a gate needs that file. Names and kinds only.
- Burying a task that exists only on an unmerged branch. Put it in the opening, in RESTORE.md, and on the note: `(only on branch X; not on main)`.
- Leaving out a folder outside the repo that a tracked script writes. Carry the results, leave raw logs, record the remap.
- Copying working state back into a path that does not sync. Symlink that path at the `.scratch` copy.

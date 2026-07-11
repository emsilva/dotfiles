---
name: todo
description: Use when the user says "remember to do X", "add that to my todos", "todo: X", types /todo, asks what's on their todo list or what their pending todos are, or wants to mark a todo done, started, or dropped.
---

# Todo — global cross-project capture

## Overview

One global list at `~/TODO.md` holds todos from every project, in the [TODO.md standard](https://github.com/todomd/todo.md) format. Capture there — NOT the session task list (evaporates on session end) and NOT a per-project `./TODO.md` (invisible from every other project).

## Quick reference

| Intent | Action |
|---|---|
| Capture ("remember to do X") | Append `- [ ] X #<project> yyyy-mm-dd` + two trailing spaces at the TOP of `### Todo` |
| List ("what's on my list?") | Read `~/TODO.md`, summarize open items; filter by `#<project>` when asked about one project |
| Start | Move the line to `### In Progress` |
| Done | Flip `[ ]` → `[x]`, move to `### Done ✓` |
| Drop | Delete the line and say so |

## Format rules

- `#<project>` = current project directory name (e.g. `#my-project`); `#global` when no project applies.
- Date = capture date, `yyyy-mm-dd`.
- Every entry line ends with two trailing spaces (TODO.md-standard line breaks).
- Title is the actionable task, keeping the user's constraints verbatim ("this week", "before the demo").
- Edit the one line/section in place — never rewrite the whole file.
- After capturing, confirm in one line what was saved and where.

## Common mistakes

- Capturing only via TaskCreate/TodoWrite — session-scoped, lost on exit. Fine as a working copy; `~/TODO.md` is the durable record.
- Writing `./TODO.md` in the current repo — scatters todos where no other session looks.
- Turning capture into action (cron, /schedule, doing the task now) — a todo is a note; act only when asked.

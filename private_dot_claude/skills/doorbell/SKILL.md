---
name: doorbell
description: Use only when the user explicitly types /doorbell or asks to ring a bell / play a notification or alert sound in the terminal (macOS). Manual trigger — never auto-invoke after a task.
---

# Doorbell

Play a short notification chime in the macOS terminal.

Run:

```bash
afplay /System/Library/Sounds/Hero.aiff
```

Then carry on. To use a different tone, swap `Hero` for any sound in `/System/Library/Sounds/`
(e.g. `Glass`, `Ping`, `Submarine`, or `Basso` for a "something failed" note).

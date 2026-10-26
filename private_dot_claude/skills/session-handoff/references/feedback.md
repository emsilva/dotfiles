# Pickup gaps → owner-approved skill changes

## Detect

Whenever, as a successor (relay or plain `/pickup`), you find the note lacked
something you needed:
- 3 or more searches for something the note does not name;
- a question to the owner about knowledge from before the handoff;
- verification contradicting the note;
- re-deriving something the predecessor had already stated;
- the predecessor's tasks not matching the checklist.

During a relay, one you need answered is a receipt `question` for the
predecessor, and a note claim your evidence contradicts is a `disagreement`
(both block the compare until answered); one you resolved yourself goes in
the receipt's `gaps`, one sentence each, which do not block it. After the
hand-over, record all of them as below; outside a relay, record each straight
away.

## Record

1. Append one JSON line to `~/.claude/handoff-feedback/gaps.jsonl`:

       {"date": "YYYY-MM-DD", "project": "<repo basename>", "relay_id": "<id or null>",
        "predecessor_session": "<id>", "successor_session": "<id>",
        "missing": "<what was missing, one sentence>",
        "cost": "<calls and tokens, or 'asked the owner'>",
        "section": "<template section that should have held it, or 'none'>",
        "kind": "no-slot | slot-empty | stale-or-wrong | check-cannot-fail | protocol",
        "severity": "serious | minor", "fixed_by": null}

2. Add one line under the consumed note's `## Pickup gaps`.

Kinds: **no-slot**, the template has no place for it; **slot-empty**, the place
exists but was left empty or incomplete; **stale-or-wrong**, present but stale
or wrong; **check-cannot-fail**, a recorded check that passes whatever happens;
**protocol**, a relay or pickup step missing or wrong.

**Serious**: an owner question the predecessor could have answered; a wrong or
duplicate action; a safety check that could not fail. Everything else is minor.

On the Mac, before the Fire step, run
`python3 -I ~/.claude/skills/session-handoff/scripts/feedback-import.py <project>`
for the current project when `<project>/.scratch/handoff-feedback/` exists.

## Fire

Draft a proposal when the new gap is serious, or when `gaps.jsonl` already
holds a gap with the same `kind` and `section` from a different handoff (a
different `predecessor_session`). A recurring gap whose earlier line has
`fixed_by` set is a regression: always propose, and say so.

## Propose, never apply

1. Write `~/.claude/handoff-feedback/proposals/<YYYY-MM-DD>-<slug>.md`: the
   gap lines (evidence), the change in one sentence, and a unified diff against
   the chezmoi source `~/.local/share/chezmoi/private_dot_claude/skills/session-handoff/`
   (never the deployed copy).
2. Add a `~/TODO.md` entry tagged `#session-handoff` pointing at it, in the
   `todo` skill's format.
3. Mention it in your next report to the owner. Applying it is the owner's
   call; once approved, a separate session applies it with
   `superpowers:writing-skills` and commits it in the dotfiles repo.

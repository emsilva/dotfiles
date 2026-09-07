#!/usr/bin/env bash
# PreCompact insurance: mechanical git/port snapshot. MUST never block
# compaction — every realistic path exits 0, and the registration in
# settings.json carries a `timeout` (the harness default ceiling is 10 MINUTES,
# and PreCompact awaits its hooks, so wall-clock is the real risk, not exit code).
# Project dir: taken from the payload's transcript_path, whose dirname IS the
# harness encoding verbatim. The sed fallback applies the harness rule (every
# non-alphanumeric -> '-') but not its >200-char truncate+hash, so an exotic cwd
# lands the snapshot orphaned (harmless, unread) rather than in the wrong place.
set -u
input="$(cat 2>/dev/null || true)"
jget() { printf '%s' "$input" | sed -n "s/.*\"$1\"[[:space:]]*:[[:space:]]*\"\([^\"]*\)\".*/\1/p"; }
cwd="$(jget cwd)"
[ -n "$cwd" ] || cwd="$PWD"
tp="$(jget transcript_path)"
sid="$(jget session_id)"
trg="$(jget trigger)"
if [ -n "$tp" ] && [ -d "$(dirname "$tp")" ]; then
  dir="$(dirname "$tp")/memory/handoffs"
else
  dir="$HOME/.claude/projects/$(printf '%s' "$cwd" | LC_ALL=C sed 's/[^a-zA-Z0-9]/-/g')/memory/handoffs"
fi
mkdir -p "$dir" 2>/dev/null || exit 0
f="$dir/EMERGENCY-$(date +%Y-%m-%d-%H%M%S)-$$.md"
{
  echo "---"
  echo "kind: emergency-snapshot"
  echo "date: $(date +%Y-%m-%d)"
  echo "cwd: $cwd"
  echo "session_id: ${sid:-unknown}"
  echo "transcript: ${tp:-unknown}"
  echo "trigger: ${trg:-unknown}"
  echo "---"
  echo "## git"
  if git -C "$cwd" rev-parse --git-dir >/dev/null 2>&1; then
    git -C "$cwd" rev-parse --abbrev-ref HEAD 2>/dev/null
    git -C "$cwd" log --oneline -3 2>/dev/null
    git -C "$cwd" status --porcelain=v1 2>/dev/null | head -100
    # An unguarded `log @{u}..` prints nothing whether the branch is in sync or
    # has no upstream — and no-upstream is when the count matters most. Every
    # section states its emptiness, so a reader can tell "nothing to report"
    # from "this section never ran" (a timeout kill truncates the file).
    echo "## ahead of upstream"
    if git -C "$cwd" rev-parse --abbrev-ref '@{u}' >/dev/null 2>&1; then
      git -C "$cwd" log --oneline '@{u}..' 2>/dev/null | head -20
    else
      echo "(no upstream — the commits under ## git are unpushed)"
    fi
  else
    echo "(not a git repo)"
    echo "## ahead of upstream"
    echo "(not a git repo)"
  fi
  echo "## worktrees"
  git -C "$cwd" worktree list 2>/dev/null
  echo "## listening ports"
  lsof -iTCP -sTCP:LISTEN -P -n 2>/dev/null | head -30
} > "$f" 2>/dev/null || true
# Retain the 5 newest. A `while read` loop, not `xargs -r`: xargs word-splits on
# spaces in the project path (silent no-op, since `rm -f` eats the errors) and
# `-r` is a GNU extension BSD/macOS xargs rejects.
ls -1t "$dir"/EMERGENCY-*.md 2>/dev/null | tail -n +6 | while IFS= read -r old; do rm -f "$old"; done
exit 0

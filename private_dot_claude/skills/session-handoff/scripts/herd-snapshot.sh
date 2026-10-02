#!/usr/bin/env bash
# Read-only herd snapshot for SAVE and RESUME: the herdr panes whose cwd is this
# repo, one of its worktrees, or an extra root passed as an argument (a front
# that launched panes elsewhere, e.g. a grading dir, names that dir). It never
# prompts, focuses or writes to a pane. Mine vs not-mine is the note writer's
# call; this only says what is there.
# Usage: bash herd-snapshot.sh [extra-root ...]
set -u
if [ "${HERDR_ENV:-}" != 1 ]; then
  echo "herd: not inside herdr (HERDR_ENV unset), nothing to record"
  exit 0
fi
roots="$(git worktree list --porcelain 2>/dev/null | sed -n 's/^worktree //p')"
[ -n "$roots" ] || roots="$PWD"
for r in "$@"; do roots="$roots
$r"; done
panes="$(herdr pane list 2>&1)" || { echo "herd: herdr pane list failed: $panes"; exit 0; }
# pane list carries no agent name; agent list does.
agents="$(herdr agent list 2>/dev/null)" || agents='{"result":{"agents":[]}}'
AGENTS="$agents" ROOTS="$roots" NEXTRA="$#" SELF="${HERDR_PANE_ID:-}" python3 -c '
import json, os, subprocess, sys, time
roots = [r.rstrip("/") for r in os.environ["ROOTS"].splitlines() if r.strip()]
def inscope(cwd):
    cwd = (cwd or "").rstrip("/")
    return any(cwd == r or cwd.startswith(r + "/") for r in roots)
names = {a["pane_id"]: a.get("name", "-") for a in json.loads(os.environ["AGENTS"])["result"]["agents"]}
panes = [p for p in json.load(sys.stdin)["result"]["panes"] if inscope(p.get("cwd"))]
nextra = int(os.environ["NEXTRA"])
print("herd snapshot %s: %d pane(s) under %s + %d worktree(s) + %d extra root(s)" % (
    time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime()), len(panes), roots[0],
    len(roots) - 1 - nextra, nextra))
for p in sorted(panes, key=lambda p: (p["tab_id"], p["pane_id"])):
    sess = (p.get("agent_session") or {}).get("value", "-")
    line = "%s  tab=%s  %s  name=%s  kind=%s  status=%s  session=%s  cwd=%s" % (
        p["pane_id"], p["tab_id"], "SELF" if p["pane_id"] == os.environ["SELF"] else "",
        names.get(p["pane_id"], "-"), p.get("agent", "none"), p.get("agent_status", "-"), sess, p.get("cwd"))
    if p.get("label"): line += "  label=" + repr(p["label"])
    if p.get("terminal_title_stripped"): line += "  title=" + repr(p["terminal_title_stripped"])
    print(line)
    if "agent" not in p:
        # A shell pane carries no command field: its last visible lines are the evidence.
        out = subprocess.run(["herdr", "pane", "read", p["pane_id"], "--source", "visible", "--lines", "40"],
                             capture_output=True, text=True).stdout
        tail = [l for l in out.splitlines() if l.strip()][-2:]
        for l in tail: print("    | " + l[:160])
' <<<"$panes"
exit 0

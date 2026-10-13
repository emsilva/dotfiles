#!/usr/bin/env bash
# Close a relay's predecessor, by fact. The successor runs this after the hand-over.
# Usage: bash relay-close.sh <relay-dir> [--slug SLUG]
# Refuses (exit 1, pane left open) unless handover.md exists, the predecessor's
# pane reports idle or done, the pane still hosts the session it hosted when
# the checklist was written, and no prompt reached the predecessor after
# handover.md. When herdr knew no session for the predecessor (a lead started
# by hand), the checklist's predecessor pid must also be a live claude process.
# Then closes the pane, confirms the pane and the predecessor's process are
# gone (exit 1 if either outlives RELAY_CLOSE_WAIT seconds, default 10),
# renames this agent lead-<project>, and writes <relay-dir>/closed.json and
# <relay-dir>/../lead.json (exit 1 if they cannot be written). Exit 2, before
# any close, outside herdr, without CLAUDE_CODE_SESSION_ID, for a checklist
# that names no repo, or for arguments that give no lead name.
set -uo pipefail
[ $# -ge 1 ] || { echo "usage: relay-close.sh <relay-dir> [--slug SLUG]" >&2; exit 2; }
dir=$1
shift
here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
wait_s=${RELAY_CLOSE_WAIT:-10}
case "$wait_s" in ''|*[!0-9]*) echo "relay-close: RELAY_CLOSE_WAIT must be whole seconds, not '$wait_s'" >&2; exit 2 ;; esac
refuse() { echo "relay-close: refusing: $1 (pane left open)" >&2; exit 1; }
field() {
  python3 -I -c 'import json, sys
d = json.load(open(sys.argv[1]))
for key in sys.argv[2].split("."):
    d = d.get(key) if isinstance(d, dict) else None
print("" if d is None else d)' "$dir/checklist.json" "$1"
}
oneline() { printf '%s' "$1" | tr -s '\n\t' '  '; }
# herdr answers on stdout and reports errors on stderr with exit 1. Under pipefail a
# `herdr ... | grep -q` pipeline carries herdr's exit 1 even when grep matches, so
# every herdr answer is captured first and examined afterwards.
pane_gone() {
  local err
  err=$(herdr agent get "$pane" 2>&1 >/dev/null) && return 1
  case "$err" in *agent_not_found*) return 0 ;; esac
  return 1
}

{ [ "${HERDR_ENV:-}" = 1 ] && [ -n "${HERDR_PANE_ID:-}" ]; } || { echo "relay-close: not inside herdr" >&2; exit 2; }
[ -n "${CLAUDE_CODE_SESSION_ID:-}" ] \
  || { echo "relay-close: CLAUDE_CODE_SESSION_ID is not set; run this inside the Claude session" >&2; exit 2; }
[ -f "$dir/checklist.json" ] || { echo "relay-close: no checklist.json in $dir" >&2; exit 2; }
[ -f "$dir/handover.md" ] || refuse "no handover.md in $dir"
pane=$(field predecessor.pane_id)
want_session=$(field predecessor.herdr_session)
old_session=$(field predecessor.session_id)
old_pid=$(field predecessor.pid)
repo=$(field repo)
relay_id=$(field relay_id)
# Settle the lead name now: once the pane is closed, a usage error could only be recorded, not refused.
[ -n "$repo" ] || { echo "relay-close: the checklist names no repo" >&2; exit 2; }
name=$(python3 -I "$here/relay-check.py" name --repo "$repo" "$@") && [ -n "$name" ] \
  || { echo "relay-close: could not settle the lead name (arguments: ${*:-none})" >&2; exit 2; }
[ -n "$pane" ] || refuse "the checklist names no predecessor pane"
[ "$pane" != "$HERDR_PANE_ID" ] || refuse "the predecessor pane $pane is this agent's own pane"

# The answer's JSON is read from stdout only; herdr's error (stderr) becomes the refusal's reason.
state=$(python3 -I -c 'import json, subprocess, sys
try:
    r = subprocess.run(["herdr", "agent", "get", sys.argv[1]], capture_output=True, text=True)
except OSError as e:
    sys.exit("herdr: %s" % e)
if r.returncode != 0:
    sys.exit(" ".join(r.stderr.split()) or "herdr agent get exited %d" % r.returncode)
try:
    agent = (json.loads(r.stdout).get("result") or {}).get("agent") or {}
except (ValueError, AttributeError):
    agent = {}
print(agent.get("agent_status") or "-", (agent.get("agent_session") or {}).get("value") or "")' "$pane" 2>&1) \
  || refuse "could not read predecessor pane $pane: $(oneline "$state")"
read -r status session <<<"$state"
case "$status" in idle|done) ;; *) refuse "predecessor pane $pane is '$status', not idle or done" ;; esac
[ "${session:-}" = "$want_session" ] || refuse "pane $pane hosts session '${session:-none}', not '${want_session:-none}'"
if [ -z "$want_session" ]; then
  # Two blank sessions compare equal, which proves nothing: the recorded pid must be a live claude.
  why="the checklist records no herdr session for pane $pane"
  case "$old_pid" in ''|*[!0-9]*) refuse "$why, and no predecessor pid" ;; esac
  kill -0 "$old_pid" 2>/dev/null || refuse "$why, and predecessor pid $old_pid is not alive"
  read -r argv0 _ <<<"$(ps -o command= -p "$old_pid" 2>/dev/null)"
  [ "${argv0##*/}" = claude ] || refuse "$why, and predecessor pid $old_pid runs '${argv0##*/}', not claude"
fi
python3 -I "$here/relay-check.py" quiet "$dir" >&2 || refuse "a prompt reached the predecessor after the hand-over"

herdr pane close "$pane" >/dev/null 2>&1
waited=0
until pane_gone; do
  [ "$waited" -lt "$wait_s" ] || { echo "relay-close: pane $pane still answers after the close" >&2; exit 1; }
  sleep 1
  waited=$((waited + 1))
done
if [ -n "$old_pid" ]; then
  waited=0
  while kill -0 "$old_pid" 2>/dev/null; do
    [ "$waited" -lt "$wait_s" ] || { echo "relay-close: predecessor pid $old_pid is still alive" >&2; exit 1; }
    sleep 1
    waited=$((waited + 1))
  done
fi

if ! err=$(herdr agent rename "$HERDR_PANE_ID" "$name" 2>&1 >/dev/null); then
  # Record the name this agent actually kept, not the one it was meant to get.
  kept=$(herdr agent get "$HERDR_PANE_ID" 2>/dev/null | python3 -I -c 'import json, sys
try:
    print(((json.load(sys.stdin).get("result") or {}).get("agent") or {}).get("name") or "")
except (ValueError, AttributeError):
    print("")')
  echo "relay-close: could not rename this agent to $name ($(oneline "$err")); it keeps the name '${kept:-unknown}'" >&2
  name=$kept
fi
python3 -I -c 'import datetime, json, os, sys
d, pane, old, new_pane, new_session, name, relay_id = sys.argv[1:8]
now = datetime.datetime.now(datetime.timezone.utc).isoformat()
json.dump({"closed_at": now, "predecessor": {"pane_id": pane, "session_id": old},
           "successor": {"pane_id": new_pane, "session_id": new_session, "name": name or None}},
          open(os.path.join(d, "closed.json"), "w"), indent=1)
json.dump({"session_id": new_session, "pane_id": new_pane, "name": name or None, "since": now, "relay_id": relay_id},
          open(os.path.join(os.path.dirname(os.path.abspath(d)), "lead.json"), "w"), indent=1)' \
  "$dir" "$pane" "$old_session" "$HERDR_PANE_ID" "$CLAUDE_CODE_SESSION_ID" "$name" "$relay_id" \
  || { echo "relay-close: closed $pane but could not write the records" >&2; exit 1; }
echo "relay-close: closed $pane; this agent is ${name:-unnamed}"

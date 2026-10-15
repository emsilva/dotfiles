#!/usr/bin/env bash
# Start a relay's successor: split this pane down, launch Claude with the
# predecessor's model, effort and permission mode, check the banner, and send
# /pickup relay=<dir>.
# Usage: bash relay-launch.sh <relay-dir> [--slug SLUG]
# Success: prints the new pane id and writes <relay-dir>/launch.json.
# Failure (split failed, two failed starts, a banner unread or without the
# model or effort, /pickup not sent): closes the pane it created, writes
# <relay-dir>/failed.json and exits 1. Exit 2 outside herdr or without a checklist.
# A start that herdr answers with agent_pane_busy (the new pane's shell is not
# ready yet) is retried every second for up to RELAY_LAUNCH_BUSY_WAIT seconds
# (default 15) before it counts as a failed attempt.
set -uo pipefail
dir=${1:?usage: relay-launch.sh <relay-dir> [--slug SLUG]}
shift
here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
busy_wait=${RELAY_LAUNCH_BUSY_WAIT:-15}
case "$busy_wait" in ''|*[!0-9]*) echo "relay-launch: RELAY_LAUNCH_BUSY_WAIT must be whole seconds, not '$busy_wait'" >&2; exit 2 ;; esac
[ "${HERDR_ENV:-}" = 1 ] || { echo "relay-launch: not inside herdr" >&2; exit 2; }
[ -f "$dir/checklist.json" ] || { echo "relay-launch: no checklist.json in $dir" >&2; exit 2; }

field() {
  python3 -I -c 'import json, sys
d = json.load(open(sys.argv[1]))
for key in sys.argv[2].split("."):
    d = d.get(key) if isinstance(d, dict) else None
print("" if d is None else d)' "${2:-$dir/checklist.json}" "$1"
}

pane=""
attempt=0
start_report="$dir/.start-$$.json"
fail() {
  trap '' INT TERM HUP   # a second signal must neither re-enter fail nor cut its clean-up short
  echo "relay-launch: $1" >&2
  [ -n "$pane" ] && herdr pane close "$pane" >/dev/null 2>&1
  [ -f "$start_report" ] && attempt=$(field attempts "$start_report")
  python3 -I -c 'import datetime, json, sys
json.dump({"stage": "launch", "reason": sys.argv[2], "attempts": int(sys.argv[3]),
           "at": datetime.datetime.now(datetime.timezone.utc).isoformat()}, open(sys.argv[1], "w"), indent=1)' \
    "$dir/failed.json" "$1" "$attempt"
  rm -f "$start_report" "$start_report.tmp"
  exit 1
}

model=$(field predecessor.model)
effort=$(field predecessor.effort)
mode=$(field predecessor.permission_mode)
repo=$(field repo)
[ -n "$model" ] || { echo "relay-launch: the checklist names no model" >&2; exit 2; }
name=$(python3 -I "$here/relay-check.py" name --repo "$repo" --suffix next "$@")
sid=$(python3 -I -c 'import uuid; print(uuid.uuid4())')
args=(--model "$model" --session-id "$sid")
[ -n "$effort" ] && args+=(--effort "$effort")
[ "$mode" = bypassPermissions ] && args+=(--dangerously-skip-permissions)

# From the split on, a kill (Ctrl-C, a caller's timeout) still closes the pane and writes failed.json.
# bash defers the trap until the running command returns, so a pane id already printed is assigned first.
trap 'fail "interrupted"' INT TERM HUP
pane=$(herdr pane split "$HERDR_PANE_ID" --direction down --cwd "$repo" --no-focus 2>/dev/null \
  | python3 -I -c 'import json, sys; print(json.load(sys.stdin)["result"]["pane"]["pane_id"])' 2>/dev/null) || pane=""
[ -n "$pane" ] || fail "pane split failed"

# A pane fresh from the split may not host a shell yet: herdr then answers agent_pane_busy, which relaylib
# retries inside the attempt; any other error ends the attempt.
attempt=1
python3 -I "$here/relaylib.py" start-agent "$name" claude "$pane" "$busy_wait" --report "$start_report" -- "${args[@]}" \
  || fail "agent start failed: $(field last_error "$start_report")"

# The banner must show the model and the effort (a whole word, so "high" is not found in "xhigh effort").
# relaylib reads the pane again for up to 10 s while it does not: a pane fresh from the start can read blank.
problem=$(python3 -I "$here/relaylib.py" check-banner "$pane" claude "$model" "$effort") \
  || fail "${problem:-the banner check failed}"

session=$(herdr agent get "$name" 2>/dev/null | python3 -I -c 'import json, sys
agent = (json.load(sys.stdin).get("result") or {}).get("agent") or {}
print((agent.get("agent_session") or {}).get("value", ""))' 2>/dev/null)
herdr agent prompt "$name" "/pickup relay=$dir" >/dev/null 2>&1 || fail "could not send /pickup"

python3 -I -c 'import datetime, json, sys
keys = ["pane_id", "name", "session_id", "requested_session_id", "model", "effort", "permission_mode"]
data = dict(zip(keys, sys.argv[2:]))
data["session_id"] = data["session_id"] or data["requested_session_id"]
data["at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
json.dump(data, open(sys.argv[1], "w"), indent=1)' \
  "$dir/launch.json" "$pane" "$name" "$session" "$sid" "$model" "$effort" "$mode"
trap - INT TERM HUP   # launched: a kill from here on must not close the successor
rm -f "$start_report" "$start_report.tmp"
echo "$pane"

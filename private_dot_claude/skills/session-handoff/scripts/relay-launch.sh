#!/usr/bin/env bash
# Start a relay's successor: split this pane down, launch Claude with the
# predecessor's model, effort and permission mode, check the banner, and send
# /pickup relay=<dir>.
# Usage: bash relay-launch.sh <relay-dir> [--slug SLUG]
# Success: prints the new pane id and writes <relay-dir>/launch.json.
# Failure (split failed, two failed starts, a banner unread or without the
# model or effort, /pickup not sent): closes the pane it created, writes
# <relay-dir>/failed.json and exits 1. Exit 2 outside herdr or without a checklist.
set -uo pipefail
dir=${1:?usage: relay-launch.sh <relay-dir> [--slug SLUG]}
shift
here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
[ "${HERDR_ENV:-}" = 1 ] || { echo "relay-launch: not inside herdr" >&2; exit 2; }
[ -f "$dir/checklist.json" ] || { echo "relay-launch: no checklist.json in $dir" >&2; exit 2; }

field() {
  python3 -I -c 'import json, sys
d = json.load(open(sys.argv[1]))
for key in sys.argv[2].split("."):
    d = d.get(key) if isinstance(d, dict) else None
print("" if d is None else d)' "$dir/checklist.json" "$1"
}

pane=""
attempt=0
fail() {
  echo "relay-launch: $1" >&2
  [ -n "$pane" ] && herdr pane close "$pane" >/dev/null 2>&1
  python3 -I -c 'import datetime, json, sys
json.dump({"stage": "launch", "reason": sys.argv[2], "attempts": int(sys.argv[3]),
           "at": datetime.datetime.now(datetime.timezone.utc).isoformat()}, open(sys.argv[1], "w"), indent=1)' \
    "$dir/failed.json" "$1" "$attempt"
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

pane=$(herdr pane split "$HERDR_PANE_ID" --direction down --cwd "$repo" --no-focus 2>/dev/null \
  | python3 -I -c 'import json, sys; print(json.load(sys.stdin)["result"]["pane"]["pane_id"])' 2>/dev/null) || pane=""
[ -n "$pane" ] || fail "pane split failed"

started=""
while [ "$attempt" -lt 2 ]; do
  attempt=$((attempt + 1))
  if out=$(herdr agent start "$name" --kind claude --pane "$pane" --timeout 90000 -- "${args[@]}" 2>&1); then
    started=1
    break
  fi
  echo "relay-launch: start attempt $attempt failed: $out" >&2
done
[ -n "$started" ] || fail "agent start failed twice"

want=$(python3 -I -c 'import sys
parts = sys.argv[1].removeprefix("claude-").split("-")
print(parts[0].capitalize() + " " + ".".join(parts[1:]))' "$model")
# herdr answers on stdout and reports errors on stderr: a failed read is not a banner.
banner=$(herdr pane read "$pane" --source visible 2>/dev/null) || fail "could not read the new pane"
case "$banner" in *"$want"*) ;; *) fail "banner does not show model '$want'" ;; esac
if [ -n "$effort" ]; then
  case "$banner" in *"$effort"*) ;; *) fail "banner does not show effort '$effort'" ;; esac
fi

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
echo "$pane"

#!/usr/bin/env bash
# Kept for older notes that say "re-run herd-snapshot.sh": it is `herd.py status` now (read-only). Its arguments
# are extra roots, as they always were.
# Usage: bash herd-snapshot.sh [extra-root ...]
exec python3 -I "$(dirname "$0")/herd.py" status "$@"

#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

# The bridge stays private on loopback; Flask is the only public HTTP service.
node whatsapp/bridge.js &
bridge_pid=$!
python src/main.py &
app_pid=$!

cleanup() {
  trap - EXIT INT TERM
  kill -TERM "$bridge_pid" "$app_pid" 2>/dev/null || true
  wait "$bridge_pid" "$app_pid" 2>/dev/null || true
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

# Do not leave Flask serving an offline bridge if either process exits.
status=0
wait -n "$bridge_pid" "$app_pid" || status=$?
echo "An application service stopped; shutting down both services." >&2
if [[ "$status" -eq 0 ]]; then status=1; fi
exit "$status"

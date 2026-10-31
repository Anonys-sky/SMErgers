#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

# The bridge stays private on loopback; Flask is the only public HTTP service.
node whatsapp/bridge.js &
bridge_pid=$!
if command -v python >/dev/null 2>&1; then
  python src/main.py &
elif [[ -x .venv/bin/python ]]; then
  .venv/bin/python src/main.py &
else
  python3 src/main.py &
fi
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
# macOS ships Bash 3, which has no wait -n. Bash reaps completed background
# children; poll their existence, then collect the first observed exit status.
while kill -0 "$bridge_pid" 2>/dev/null && kill -0 "$app_pid" 2>/dev/null; do
  sleep 0.2
done
status=0
if ! kill -0 "$bridge_pid" 2>/dev/null; then
  wait "$bridge_pid" || status=$?
else
  wait "$app_pid" || status=$?
fi
echo "An application service stopped; shutting down both services." >&2
if [[ "$status" -eq 0 ]]; then status=1; fi
exit "$status"

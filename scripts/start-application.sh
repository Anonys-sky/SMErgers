#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

# The bridge stays private on loopback; Flask is the only public HTTP service.
node whatsapp/bridge.js &
bridge_pid=$!
if [[ "${SMERGERS_WSGI:-0}" == "1" ]]; then
  # One worker owns the prototype's in-memory store and bridge polling thread.
  gunicorn --workers 1 --threads 8 --timeout 300 --bind "0.0.0.0:${PORT:-5000}" app:app &
elif command -v python >/dev/null 2>&1; then
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

# By default, do not leave Flask serving an offline bridge: if either process exits, stop both.
# Set SMERGERS_KEEP_APP_UP=1 to keep the app serving when only the bridge stops (the WhatsApp page then
# says "Bridge not running" and the rest of the product, including Import chat, keeps working).
# macOS ships Bash 3, which has no wait -n. Bash reaps completed background
# children; poll their existence, then collect the first observed exit status.
keep_app="${SMERGERS_KEEP_APP_UP:-0}"
warned=""
while kill -0 "$app_pid" 2>/dev/null; do
  if ! kill -0 "$bridge_pid" 2>/dev/null; then
    [[ "$keep_app" == "1" ]] || break
    [[ -n "$warned" ]] || { echo "The WhatsApp bridge stopped; the app keeps running without it." >&2; warned=1; }
  fi
  sleep 0.2
done
status=0
if [[ "$keep_app" != "1" ]] && ! kill -0 "$bridge_pid" 2>/dev/null; then
  wait "$bridge_pid" || status=$?
else
  wait "$app_pid" || status=$?
fi
echo "An application service stopped; shutting down both services." >&2
if [[ "$status" -eq 0 ]]; then status=1; fi
exit "$status"

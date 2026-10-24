#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

# Use Nix's Chromium, which includes its Linux shared libraries. The downloaded
# Chrome binary alone cannot run in this environment.
PUPPETEER_SKIP_DOWNLOAD=true npm ci --no-audit --no-fund
node whatsapp/browser.js

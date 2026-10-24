#!/usr/bin/env bash
set -euo pipefail

npm ci --no-audit --no-fund
python -m pip install \
  --disable-pip-version-check \
  --no-input \
  --upgrade \
  --target=.pythonlibs/lib/python3.12/site-packages \
  -r requirements.txt

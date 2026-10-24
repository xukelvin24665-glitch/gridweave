#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
.venv/bin/python -m pip install --disable-pip-version-check -r requirements.txt -e .
exec .venv/bin/python -m gridweave serve "$@"

#!/usr/bin/env bash
set -euo pipefail
command -v python3 >/dev/null || { echo "Python 3 is required"; exit 1; }
python3 - <<'PY'
import sys
if sys.version_info < (3, 11): raise SystemExit("Python 3.11+ required")
print("Using Python", sys.version.split()[0])
PY
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
[[ -f .env ]] || cp .env.example .env
mkdir -p data/raw data/processed artifacts logs
pytest
echo "Bootstrap complete. Edit .env, then run: source .venv/bin/activate"

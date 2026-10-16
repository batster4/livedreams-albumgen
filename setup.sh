#!/usr/bin/env bash
# One-time setup: a virtual environment in .venv, albumgen installed into it, .env created from .env.example.
set -euo pipefail
cd "$(dirname "$0")"

PY=""
for c in python3.13 python3.12 python3.11 python3.10 python3; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(sys.version_info < (3, 10))'; then
    PY="$c"; break
  fi
done
if [ -z "$PY" ]; then
  echo "Python 3.10+ is required. macOS: brew install python@3.12 · Ubuntu/Debian: sudo apt install python3 python3-venv"
  exit 1
fi

echo "Using $($PY --version)"
"$PY" -m venv .venv
.venv/bin/python -m pip install --quiet --upgrade pip
.venv/bin/python -m pip install --quiet -e .
[ -f .env ] || cp .env.example .env
.venv/bin/albumgen doctor

echo
echo "Done. Next:"
echo "  1. Put your API key in .env:  LIVEDREAMS_API_KEY=ldk_..."
echo "  2. source .venv/bin/activate"
echo "  3. albumgen doctor --ping && albumgen new -n 1 && albumgen render"

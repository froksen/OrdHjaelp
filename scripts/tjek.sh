#!/usr/bin/env bash
# Kør det samme som GitHub Actions gør på Linux, før der pushes.
# Brug: scripts/tjek.sh
set -euo pipefail
cd "$(dirname "$0")/.."

echo "== ruff check"
uv run ruff check .
echo "== ruff format"
uv run ruff format --check .
echo "== pytest (også vagten mod Windows-fejl i tests/test_platform_imports.py)"
QT_QPA_PLATFORM=offscreen uv run pytest -q

if command -v Xvfb >/dev/null && command -v xdotool >/dev/null; then
  echo "== læs under musen mod rigtig AT-SPI"
  ORDHJAELP_ATSPI_TEST=1 uv run pytest -q tests/integration/test_atspi.py
else
  echo "== AT-SPI-testen springes over (Xvfb eller xdotool mangler)"
fi

if ! command -v hunspell >/dev/null; then
  echo "ADVARSEL: hunspell mangler, så ordforslagstesten med København fejler her" >&2
fi
echo "Alt i orden"

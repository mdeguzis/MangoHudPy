#!/usr/bin/env bash
# dev-setup.sh -- Set up a local development environment using uv
#
# Usage:
#   ./dev-setup.sh

set -euo pipefail

PACKAGE_DIR="$(cd "$(dirname "$0")" && pwd)"

# Install uv if not present
if ! command -v uv &>/dev/null; then
    echo "==> Installing uv..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
fi

echo "==> Creating virtual environment..."
uv venv "$PACKAGE_DIR/.venv"

echo "==> Installing package in editable mode with all optional deps..."
uv pip install --python "$PACKAGE_DIR/.venv/bin/python" -e "$PACKAGE_DIR[graphs,gui]"

echo ""
echo "==> Done. Activate with:"
echo "    source .venv/bin/activate"
echo ""
echo "==> Run CLI:"
echo "    mangohud-py --help"
echo ""
echo "==> Run GUI:"
echo "    mangohud-py-gui"

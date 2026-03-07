#!/usr/bin/env bash
# upload-to-pypi.sh -- Build and upload mangohudpy to PyPI
#
# Prerequisites:
#   uv (https://astral.sh/uv)
#
# First-time setup:
#   Create ~/.pypirc with your API token:
#     [distutils]
#     index-servers = pypi testpypi
#
#     [pypi]
#     username = __token__
#     password = pypi-<your-token>
#
#     [testpypi]
#     repository = https://test.pypi.org/legacy/
#     username = __token__
#     password = pypi-<your-test-token>
#
# Usage:
#   ./upload-to-pypi.sh           # upload to PyPI
#   ./upload-to-pypi.sh --test    # upload to TestPyPI first

set -euo pipefail

PACKAGE_DIR="$(cd "$(dirname "$0")" && pwd)"
DIST_DIR="$PACKAGE_DIR/dist"
VENV_DIR="$PACKAGE_DIR/.venv-publish"
TWINE="$VENV_DIR/bin/twine"
USE_TEST_PYPI=0

for arg in "$@"; do
    case "$arg" in
        --test) USE_TEST_PYPI=1 ;;
        *) echo "Unknown argument: $arg" >&2; exit 1 ;;
    esac
done

# Ensure twine is available in a dedicated venv
if [[ ! -x "$TWINE" ]]; then
    echo "==> Setting up twine via uv..."
    uv venv "$VENV_DIR" --quiet
    uv pip install --python "$VENV_DIR/bin/python" twine --quiet
fi

echo "==> Cleaning previous builds..."
rm -rf "$DIST_DIR" "$PACKAGE_DIR/build" "$PACKAGE_DIR"/*.egg-info

echo "==> Building source distribution and wheel..."
uv build "$PACKAGE_DIR"

echo ""
echo "==> Built packages:"
ls -lh "$DIST_DIR"

echo ""
if [[ $USE_TEST_PYPI -eq 1 ]]; then
    echo "==> Uploading to TestPyPI..."
    "$TWINE" upload --repository testpypi "$DIST_DIR"/*
    echo ""
    echo "==> Done. Install with:"
    echo "    pip install --index-url https://test.pypi.org/simple/ mangohudpy"
else
    echo "==> Uploading to PyPI..."
    "$TWINE" upload "$DIST_DIR"/*
    echo ""
    echo "==> Done. Install with:"
    echo "    pip install mangohudpy"
fi

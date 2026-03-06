#!/usr/bin/env bash
# upload-to-pypi.sh -- Build and upload mangohudpy to PyPI
#
# Prerequisites:
#   pip install build twine
#
# First-time setup:
#   1. Register at https://pypi.org and create an API token
#   2. Save credentials in ~/.pypirc:
#        [pypi]
#        username = __token__
#        password = pypi-<your-token>
#      Or pass --token below.
#
# Usage:
#   ./upload-to-pypi.sh           # upload to PyPI
#   ./upload-to-pypi.sh --test    # upload to TestPyPI first

set -euo pipefail

PACKAGE_DIR="$(cd "$(dirname "$0")" && pwd)"
DIST_DIR="$PACKAGE_DIR/dist"
USE_TEST_PYPI=0

for arg in "$@"; do
    case "$arg" in
        --test) USE_TEST_PYPI=1 ;;
        *) echo "Unknown argument: $arg" >&2; exit 1 ;;
    esac
done

echo "==> Cleaning previous builds..."
rm -rf "$DIST_DIR" "$PACKAGE_DIR/build" "$PACKAGE_DIR"/*.egg-info

echo "==> Building source distribution and wheel..."
python3 -m build "$PACKAGE_DIR"

echo ""
echo "==> Built packages:"
ls -lh "$DIST_DIR"

echo ""
if [[ $USE_TEST_PYPI -eq 1 ]]; then
    echo "==> Uploading to TestPyPI..."
    python3 -m twine upload \
        --repository-url https://test.pypi.org/legacy/ \
        "$DIST_DIR"/*
    echo ""
    echo "==> Done. Install with:"
    echo "    pip install --index-url https://test.pypi.org/simple/ mangohudpy"
else
    echo "==> Uploading to PyPI..."
    python3 -m twine upload "$DIST_DIR"/*
    echo ""
    echo "==> Done. Install with:"
    echo "    pip install mangohudpy"
fi

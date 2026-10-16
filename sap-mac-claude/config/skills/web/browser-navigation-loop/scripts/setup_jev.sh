#!/usr/bin/env bash
# Clone and install browser-use/jev-ultrafast so it can be run as an external
# fast-path browser agent. Idempotent: re-running just re-syncs deps.
#
# Usage:  setup_jev.sh [target_dir]
# Default target_dir: ~/.cache/jev-ultrafast
set -euo pipefail

TARGET_DIR="${1:-$HOME/.cache/jev-ultrafast}"
REPO="https://github.com/browser-use/jev-ultrafast.git"

if ! command -v uv >/dev/null 2>&1; then
  echo "error: 'uv' is required but not installed. Install from https://docs.astral.sh/uv/ and re-run." >&2
  exit 1
fi

if [ -d "$TARGET_DIR/.git" ]; then
  echo "jev-ultrafast already cloned at $TARGET_DIR — pulling latest."
  git -C "$TARGET_DIR" pull --ff-only
else
  echo "Cloning jev-ultrafast into $TARGET_DIR"
  git clone "$REPO" "$TARGET_DIR"
fi

cd "$TARGET_DIR"
echo "Running uv sync (installs deps incl. Browser Harness)…"
uv sync

if [ ! -f .env ]; then
  cp .env.example .env
  echo
  echo ">>> Created $TARGET_DIR/.env from the example."
  echo ">>> Edit it and set TYPESAFE_API_KEY and TEXT_MODEL_API_KEY before running."
else
  echo ".env already exists — leaving it untouched."
fi

echo
echo "Done. Verify the browser connection with:"
echo "  (cd \"$TARGET_DIR\" && uv run browser-harness --doctor)"
echo "Then run a task with scripts/run_jev.py (see references/jev-agent.md)."

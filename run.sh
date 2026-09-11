#!/usr/bin/env bash
# NOVA Launcher Script

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [ -f ".venv/bin/python" ]; then
    exec .venv/bin/python main.py "$@"
else
    echo "Virtual environment not found at .venv"
    exit 1
fi

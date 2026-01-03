#!/bin/bash
# csvtoxml GUI Launcher
# ダブルクリックで起動

cd "$(dirname "$0")"

# Check if running in virtual environment
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

python3 csvtoxml_gui.py

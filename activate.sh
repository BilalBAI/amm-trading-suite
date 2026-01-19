#!/bin/bash
# Activation script for amm-tools virtual environment
# Usage: source activate.sh

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "$SCRIPT_DIR/venv/bin/activate"
echo "✓ Virtual environment activated"
echo "✓ Working directory: $SCRIPT_DIR"
echo "✓ Python: $(which python)"
echo ""


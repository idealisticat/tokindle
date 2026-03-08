#!/usr/bin/env bash
# Usage: cd to project root, then run:  ./start.sh   or  bash start.sh
set -e

echo "=== TOKINDLE Quick Start ==="
echo ""

# Check Python 3
if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 not found. Install Python 3.9+ first."
    exit 1
fi
echo "[OK] Python 3 found: $(python3 --version)"

# Create venv if missing
if [ ! -d "venv" ]; then
    echo "[..] Creating virtual environment..."
    python3 -m venv venv
    echo "[OK] venv created."
else
    echo "[OK] venv already exists."
fi

# Activate venv
source venv/bin/activate
echo "[OK] venv activated."

# Install / update dependencies (use python3 -m pip so pip need not be on PATH)
echo "[..] Installing dependencies..."
python3 -m pip install -q -r requirements.txt
echo "[OK] Dependencies installed."

# Create .env from example if missing
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo "[!!] .env created from .env.example — edit it with your SMTP credentials."
    else
        echo "[!!] No .env file found. Create one (see .env.example) or configure via the Admin UI."
    fi
else
    echo "[OK] .env exists."
fi

# Launch Admin UI
echo ""
echo "=== Launching TOKINDLE Admin UI ==="
echo "Use the sidebar to start FastAPI and the RSS Worker."
echo ""
exec streamlit run admin_ui.py

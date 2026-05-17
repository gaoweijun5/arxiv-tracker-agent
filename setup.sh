#!/bin/bash
set -e

echo "=== ArXiv Tracker Agent Setup ==="

# Create .env if not exists
if [ ! -f .env ]; then
    cp .env.example .env
    echo "[OK] Created .env from .env.example"
    echo "[!] Please edit .env and add your OPENAI_API_KEY"
else
    echo "[OK] .env already exists"
fi

# Setup Python backend
echo "[...] Setting up Python backend..."
uv venv 2>/dev/null || python3 -m venv .venv
source .venv/bin/activate
uv pip install -e . 2>/dev/null || pip install -e .
echo "[OK] Backend dependencies installed"

# Setup frontend
echo "[...] Setting up frontend..."
cd frontend
npm install --silent
cd ..
echo "[OK] Frontend dependencies installed"

# Create data directories
mkdir -p data/papers data/vectors
echo "[OK] Data directories created"

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "  1. Edit .env and add your OPENAI_API_KEY"
echo "  2. Run: make dev"
echo ""

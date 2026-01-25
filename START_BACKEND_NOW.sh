#!/bin/bash
# This script will start the backend for you

echo "=========================================="
echo "Starting DSE Sniper Backend..."
echo "=========================================="
echo ""

cd "$(dirname "$0")/backend"

echo "📍 Current directory: $(pwd)"
echo "📦 Installing dependencies..."
pip3 install -q -r ../requirements.txt 2>&1 | grep -v "Requirement already satisfied" || true

echo ""
echo "🚀 Starting backend..."
echo "⏳ Analysis will run (takes ~20 seconds)..."
echo ""
echo "Keep this terminal open!"
echo "=========================================="
echo ""

python3 main.py

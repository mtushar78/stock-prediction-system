#!/bin/bash
# DSE Sniper - Portfolio UI Launcher
# Runs at 2:45 PM (after market close at 2:30 PM)
# Opens the Portfolio Guardian web interface

echo "========================================"
echo "DSE SNIPER - Portfolio UI Starting"
echo "Time: $(date)"
echo "========================================"

# Change to project directory
cd "$(dirname "$0")"

echo ""
echo "Starting Portfolio Guardian UI..."
echo "Access at: http://localhost:8080"
echo ""
echo "Press CTRL+C to stop the server"
echo "========================================"
echo ""

python portfolio_ui.py

exit 0

#!/bin/bash
# DSE Sniper - Morning Update Script
# Runs at market open (10:00 AM Bangladesh Time)
# This script runs update and analyze sequentially

echo "========================================"
echo "DSE SNIPER - Morning Update Started"
echo "Time: $(date)"
echo "========================================"

# Change to project directory
cd "$(dirname "$0")"

echo ""
echo "[1/2] Updating stock data..."
python main.py update
if [ $? -ne 0 ]; then
    echo "ERROR: Data update failed!"
    exit 1
fi

echo ""
echo "[2/2] Analyzing stocks and generating signals..."
python main.py analyze
if [ $? -ne 0 ]; then
    echo "ERROR: Analysis failed!"
    exit 1
fi

echo ""
echo "========================================"
echo "DSE SNIPER - Morning Update Completed"
echo "Time: $(date)"
echo "========================================"
echo ""

exit 0

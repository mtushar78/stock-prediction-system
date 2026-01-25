#!/bin/bash
# Start FastAPI Backend

echo "🚀 Starting DSE Sniper Backend..."
echo "=================================="
echo ""

cd "$(dirname "$0")"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "⚠️  Virtual environment not found. Creating one..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install/upgrade backend dependencies
echo "📦 Installing/updating dependencies..."
pip install -q --upgrade pip
pip install -q -r requirements.txt
pip install -q -r backend/requirements.txt

echo ""
echo "✅ Backend starting at http://localhost:8000"
echo "📚 API Documentation: http://localhost:8000/docs"
echo "⏰ Scheduler: Daily update at 2:45 PM (Bangladesh Time)"
echo ""
echo "Press CTRL+C to stop the server"
echo "=================================="
echo ""

# Start the backend
cd backend
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

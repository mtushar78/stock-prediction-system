#!/bin/bash
# Start Next.js Frontend

echo "🚀 Starting DSE Sniper Frontend..."
echo "=================================="
echo ""

cd "$(dirname "$0")/frontend"

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "📦 Installing dependencies (first time setup)..."
    npm install
fi

echo ""
echo "✅ Frontend starting at http://localhost:3000"
echo "🖥️  Dashboard will open in your browser"
echo ""
echo "Press CTRL+C to stop the server"
echo "=================================="
echo ""

# Start the frontend
npm run dev

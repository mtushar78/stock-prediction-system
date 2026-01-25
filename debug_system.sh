#!/bin/bash
# Debug Script for DSE Sniper System

echo "========================================"
echo "🔍 DSE Sniper System Debug"
echo "========================================"
echo ""

# Check if backend is running
echo "1. Checking if backend is running..."
if curl -s http://localhost:8000/ > /dev/null 2>&1; then
    echo "   ✅ Backend is running on port 8000"
    
    # Test API endpoints
    echo ""
    echo "2. Testing API endpoints..."
    
    echo "   - Testing / (health check)..."
    curl -s http://localhost:8000/ | python3 -m json.tool 2>/dev/null || echo "   ⚠️  Response not JSON"
    
    echo ""
    echo "   - Testing /api/sniper-signals..."
    SIGNALS=$(curl -s http://localhost:8000/api/sniper-signals)
    SIGNAL_COUNT=$(echo "$SIGNALS" | python3 -c "import sys, json; data=json.load(sys.stdin); print(len(data))" 2>/dev/null || echo "0")
    echo "   📊 Found $SIGNAL_COUNT signals"
    
    if [ "$SIGNAL_COUNT" -gt "0" ]; then
        echo "   ✅ API is serving data correctly!"
    else
        echo "   ⚠️  No signals found. Run: python3 main.py analyze"
    fi
    
else
    echo "   ❌ Backend is NOT running!"
    echo ""
    echo "   To start backend, run:"
    echo "   cd backend && python3 main.py"
    echo ""
fi

echo ""
echo "3. Checking if frontend is running..."
if curl -s http://localhost:3000/ > /dev/null 2>&1; then
    echo "   ✅ Frontend is running on port 3000"
else
    echo "   ❌ Frontend is NOT running!"
    echo ""
    echo "   To start frontend, run:"
    echo "   cd frontend && npm run dev"
    echo ""
fi

echo ""
echo "4. Checking database..."
if [ -f "data/dse_history.db" ]; then
    DB_SIZE=$(du -h data/dse_history.db | cut -f1)
    echo "   ✅ Database exists: $DB_SIZE"
else
    echo "   ❌ Database not found!"
fi

echo ""
echo "5. Browser console check..."
echo "   Open browser console (F12) and look for:"
echo "   - API Error messages"
echo "   - CORS errors"
echo "   - Network failures"

echo ""
echo "========================================"
echo "📝 Summary:"
echo "========================================"
echo ""

# Final recommendation
if ! curl -s http://localhost:8000/ > /dev/null 2>&1; then
    echo "🔴 ISSUE: Backend is not running"
    echo ""
    echo "FIX: Open a terminal and run:"
    echo "  cd backend"
    echo "  python3 main.py"
    echo ""
elif ! curl -s http://localhost:3000/ > /dev/null 2>&1; then
    echo "🔴 ISSUE: Frontend is not running"
    echo ""
    echo "FIX: Open another terminal and run:"
    echo "  cd frontend"
    echo "  npm run dev"
    echo ""
else
    echo "✅ Both services are running!"
    echo ""
    echo "If you still see 'No data' in frontend:"
    echo "1. Check browser console (F12) for errors"
    echo "2. Verify: http://localhost:8000/api/sniper-signals"
    echo "3. Run: python3 main.py analyze (to generate signals)"
fi

echo "========================================"

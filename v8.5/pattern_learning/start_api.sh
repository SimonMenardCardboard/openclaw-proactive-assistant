#!/bin/bash
# Start V8.5 Pattern Learning API

cd "$(dirname "$0")"

export PORT=5006
echo "🚀 Starting V8.5 Pattern Learning API on port $PORT..."

# Kill any existing process on this port
lsof -t -i:$PORT | xargs kill -9 2>/dev/null || true
sleep 1

# Start the API
nohup python3 api/pattern_learning_api.py > api.log 2>&1 &
API_PID=$!

echo "API started with PID: $API_PID"
echo "Logs: $(pwd)/api.log"

# Wait for API to be ready
sleep 3

# Health check
curl -s http://localhost:$PORT/api/v8.5/health > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✅ API is healthy and responding"
else
    echo "⚠️  API may still be starting. Check api.log for errors"
fi

echo ""
echo "📊 Available endpoints:"
echo "  POST   /api/v8.5/interactions/track"
echo "  POST   /api/v8.5/interactions/batch"
echo "  GET    /api/v8.5/recommendations/personalized/:userId"
echo "  GET    /api/v8.5/patterns/:userId"
echo "  GET    /api/v8.5/effectiveness/:userId"
echo "  GET    /api/v8.5/health"
echo ""

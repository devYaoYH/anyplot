#!/bin/bash
# Start script for AnyPlot - brings up both frontend and backend

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cleanup() {
    echo ""
    echo "Shutting down..."
    kill $SERVER_PID $APP_PID 2>/dev/null || true
    exit 0
}

trap cleanup SIGINT SIGTERM

echo "Starting AnyPlot..."

# Start backend server
echo "Starting backend server on http://localhost:8000"
cd "$SCRIPT_DIR/server"
uv run uvicorn src.main:app --reload --port 8000 &
SERVER_PID=$!

# Start frontend dev server
echo "Starting frontend on http://localhost:5173"
cd "$SCRIPT_DIR/app"
npm run dev &
APP_PID=$!

echo ""
echo "AnyPlot is running:"
echo "  Frontend: http://localhost:5173"
echo "  Backend:  http://localhost:8000"
echo ""
echo "Press Ctrl+C to stop"

wait

#!/bin/bash

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# Start the API server in the background
echo "Starting API server on port 5000..."
python api.py &
API_PID=$!

# Wait a moment for the API to start
sleep 2

# Check if API started successfully
if ! kill -0 $API_PID 2>/dev/null; then
    echo "Error: API server failed to start"
    exit 1
fi

echo "API server started (PID: $API_PID)"

# Start the frontend
echo "Starting frontend development server..."
cd frontend
npm run dev

# When frontend exits, kill the API server
echo "Shutting down API server..."
kill $API_PID 2>/dev/null


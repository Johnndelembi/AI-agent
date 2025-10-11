#!/bin/bash
# Script to run the FastAPI application

echo "Starting AI Agent FastAPI Server..."
echo "API will be available at: http://localhost:8000"
echo "API Documentation: http://localhost:8000/docs"
echo ""

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Run the FastAPI application
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000


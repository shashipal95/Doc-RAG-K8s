#!/bin/bash

# Development server startup script

echo "🚀 Starting DocChat Backend..."
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ .env file not found!"
    echo "Please copy .env.example to .env and fill in your credentials:"
    echo "  cp .env.example .env"
    exit 1
fi

# Start the server
echo "Starting server at http://localhost:8000"
echo "API Docs available at http://localhost:8000/docs"
echo ""

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

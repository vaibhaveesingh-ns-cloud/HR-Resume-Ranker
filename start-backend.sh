#!/bin/bash

# Start the FastAPI backend server
echo "Starting HR Resume Ranker Backend..."

# Navigate to backend directory
cd backend

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "Warning: .env file not found. Please copy .env.example to .env and add your OpenAI API key."
    echo "Creating .env from .env.example..."
    cp .env.example .env
    echo "Please edit .env and add your OPENAI_API_KEY before running the server."
    exit 1
fi

# Start the server
echo "Starting FastAPI server on http://localhost:8000"
python main.py

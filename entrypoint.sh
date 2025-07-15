#!/bin/bash
set -e

echo "Installing Python dependencies..."
pip install -r requirements.txt

echo "Installing Playwright browsers..."
playwright install chromium

echo "Starting the application..."
uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}
#!/bin/bash
# Build script for Railway deployment

echo "Installing Python dependencies..."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo "Installing Playwright browsers..."
python -m playwright install --with-deps chromium

echo "Build completed successfully!"

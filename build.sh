#!/bin/bash
# Build script for Railway deployment

echo "Installing Python dependencies..."
pip install -r requirements.txt

echo "Installing Playwright browsers..."
playwright install --with-deps chromium

echo "Build completed successfully!"

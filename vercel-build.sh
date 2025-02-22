#!/bin/bash

# Install Python dependencies
pip install -r requirements.txt

# Create necessary directories if they don't exist
mkdir -p app/static/css
mkdir -p app/static/js

# Copy static files if needed
cp -r app/static/* ./static/ 2>/dev/null || true 
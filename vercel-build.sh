#!/bin/bash

# Install Python dependencies
pip install -r requirements.txt

# Create necessary directories
mkdir -p .vercel/output/static
mkdir -p .vercel/output/functions/app

# Copy static files
cp -r app/static/* .vercel/output/static/

# Copy Python files
cp -r app/* .vercel/output/functions/app/

# Create Vercel output configuration
cat > .vercel/output/config.json << EOF
{
    "version": 3,
    "routes": [
        {
            "src": "/static/(.*)",
            "dest": "/static/$1"
        },
        {
            "src": "/(.*)",
            "dest": "/functions/app/main"
        }
    ]
}
EOF 
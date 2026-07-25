#!/bin/bash
# Run embroidery converter locally
cd "$(dirname "$0")"

# Check venv
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    ./venv/bin/pip install -r requirements.txt
fi

echo "🚀 Starting Embroidery Converter..."
echo "   Open http://localhost:8000"
./venv/bin/python backend/main.py

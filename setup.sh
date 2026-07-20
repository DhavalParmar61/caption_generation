#!/bin/bash

echo "=============================================================================="
echo "🚀 Setting up Social Media Caption Generator"
echo "=============================================================================="
echo

# Check for Python
if ! command -v python3 &> /dev/null; then
    echo "[ERROR] Python 3 is not installed."
    echo "Please install Python 3.8+ and try again."
    exit 1
fi

# Create Virtual Environment
if [ ! -d ".venv" ]; then
    echo "[+] Creating virtual environment in .venv..."
    python3 -m venv .venv
    if [ $? -ne 0 ]; then
        echo "[ERROR] Failed to create virtual environment."
        exit 1
    fi
else
    echo "[.] Virtual environment (.venv) already exists."
fi

# Copy .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo "[+] Copying .env.example to .env..."
    cp .env.example .env
    echo
    echo "[IMPORTANT] A '.env' file has been created."
    echo "Please open it and add your Gemini, OpenAI, or Anthropic API key."
else
    echo "[.] '.env' file already exists."
fi

# Activate environment and install requirements
echo
echo "[+] Activating virtual environment and installing dependencies..."
source .venv/bin/activate
if [ $? -ne 0 ]; then
    echo "[ERROR] Failed to activate virtual environment."
    exit 1
fi

python3 -m pip install --upgrade pip
pip install -r requirements.txt
if [ $? -ne 0 ]; then
    echo "[ERROR] Failed to install dependencies."
    exit 1
fi

echo
echo "=============================================================================="
echo "🎉 Setup completed successfully!"
echo "=============================================================================="
echo
echo "To run the tool:"
echo "1. Make sure you add your API key to the '.env' file."
echo "2. Run the tool interactively:"
echo "   source .venv/bin/activate"
echo "   python caption_gen.py"
echo
echo "Or run with arguments:"
echo "   .venv/bin/python caption_gen.py -d \"Product Description\" -k \"key1, key2\""
echo "=============================================================================="
echo

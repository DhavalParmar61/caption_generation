@echo off
setlocal enabledelayedexpansion

echo ==============================================================================
echo 🚀 Setting up Social Media Caption Generator
echo ==============================================================================
echo.

:: Check for Python
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Python is not installed or not added to your PATH.
    echo Please install Python 3.8+ from https://www.python.org/ and try again.
    pause
    exit /b 1
)

:: Create Virtual Environment
if not exist .venv (
    echo [+] Creating virtual environment in .venv...
    python -m venv .venv
    if !ERRORLEVEL! neq 0 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
) else (
    echo [.] Virtual environment (.venv) already exists.
)

:: Copy .env file if it doesn't exist
if not exist .env (
    echo [+] Copying .env.example to .env...
    copy .env.example .env >nul
    echo.
    echo [IMPORTANT] A '.env' file has been created.
    echo Please open it and add your Gemini, OpenAI, or Anthropic API key.
) else (
    echo [.] '.env' file already exists.
)

:: Activate environment and install requirements
echo.
echo [+] Activating virtual environment and installing dependencies...
call .venv\Scripts\activate
if !ERRORLEVEL! neq 0 (
    echo [ERROR] Failed to activate virtual environment.
    pause
    exit /b 1
)

python -m pip install --upgrade pip
pip install -r requirements.txt
if !ERRORLEVEL! neq 0 (
    echo [ERROR] Failed to install dependencies.
    pause
    exit /b 1
)

echo.
echo ==============================================================================
echo 🎉 Setup completed successfully!
echo ==============================================================================
echo.
echo To run the tool:
echo 1. Make sure you add your API key to the '.env' file.
echo 2. Run the tool interactively:
echo    .venv\Scripts\python caption_gen.py
echo.
echo Or run with arguments:
echo    .venv\Scripts\python caption_gen.py -d "Product Description" -k "key1, key2"
echo ==============================================================================
echo.

pause

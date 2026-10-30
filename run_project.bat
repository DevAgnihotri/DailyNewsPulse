@echo off
setlocal
title PulsePersona - Multi-Agent Weekly News Intelligence Engine
color 0B

echo ======================================================================
echo           PulsePersona - Multi-Agent AI News Intelligence
echo ======================================================================
echo.

cd /d "%~dp0"

REM Check if virtual environment exists
set "PYTHON_EXE=python"
if exist ".venv\Scripts\python.exe" (
    echo [INFO] Found virtual environment in .venv
    set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
) else (
    echo [WARNING] .venv not found, using system python
)

REM Check for .env file
if not exist ".env" (
    echo [WARNING] .env file not found. Copying from .env.example
    if exist ".env.example" (
        copy /y ".env.example" ".env" >nul
        echo [NOTICE] Created .env template. Please configure your API keys.
    )
)

echo [INFO] Starting FastAPI server on http://localhost:8000
echo [INFO] Opening web browser at http://localhost:8000
start "" "http://localhost:8000"

echo.
echo ======================================================================
echo  Server is running! Press Ctrl+C in this terminal to stop.
echo ======================================================================
echo.

"%PYTHON_EXE%" -m uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload

pause

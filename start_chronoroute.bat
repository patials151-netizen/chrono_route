@echo off
setlocal enabledelayedexpansion
title ChronoRoute - Emergency Vehicle Preemption and Route Optimizer

echo =====================================================================
echo   CHRONOROUTE - TACTICAL CAD DISPATCH ^& ROUTE OPTIMIZER
echo =====================================================================
echo.

cd /d "%~dp0"

:: 1. Search for Python executable
set "PYTHON_EXE="

if exist "C:\Users\Sahil\AppData\Local\Programs\Python\Python315\python.exe" (
    set "PYTHON_EXE=C:\Users\Sahil\AppData\Local\Programs\Python\Python315\python.exe"
    set "PATH=C:\Users\Sahil\AppData\Local\Programs\Python\Python315;C:\Users\Sahil\AppData\Local\Programs\Python\Python315\Scripts;%PATH%"
) else if exist "%LOCALAPPDATA%\Programs\Python\Python315\python.exe" (
    set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python315\python.exe"
    set "PATH=%LOCALAPPDATA%\Programs\Python\Python315;%LOCALAPPDATA%\Programs\Python\Python315\Scripts;%PATH%"
)

if "!PYTHON_EXE!"=="" (
    for /d %%D in ("%LOCALAPPDATA%\Programs\Python\Python*") do (
        if exist "%%D\python.exe" (
            set "PYTHON_EXE=%%D\python.exe"
            set "PATH=%%D;%%D\Scripts;%PATH%"
        )
    )
)

if "!PYTHON_EXE!"=="" (
    where py.exe >nul 2>&1
    if !errorlevel! equ 0 (
        set "PYTHON_EXE=py"
    )
)

if "!PYTHON_EXE!"=="" (
    where python.exe >nul 2>&1
    if !errorlevel! equ 0 (
        set "PYTHON_EXE=python"
    )
)

if "!PYTHON_EXE!"=="" (
    echo [ERROR] Python was not found on your system!
    echo Please install Python 3.10+ from https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

echo [*] Using Python: !PYTHON_EXE!

:: 2. Check dependencies
echo [*] Checking dependencies (Flask, NetworkX, Flask-CORS)...
"!PYTHON_EXE!" -c "import flask, networkx, flask_cors" >nul 2>&1
if !errorlevel! neq 0 (
    echo [*] Installing missing dependencies from requirements.txt...
    "!PYTHON_EXE!" -m pip install -r requirements.txt
    if !errorlevel! neq 0 (
        echo [ERROR] Failed to install dependencies.
        pause
        exit /b 1
    )
)

:: 3. Launch ChronoRoute Server & CAD Dashboard
echo [*] Launching ChronoRoute Command Center...
echo [*] Server: http://localhost:8080
echo [*] Opening browser automatically...
echo [*] Press Ctrl+C in this window to stop the server.
echo.

"!PYTHON_EXE!" server.py %*

if !errorlevel! neq 0 (
    echo.
    echo [WARNING] Server stopped or exited with code !errorlevel!
)

pause

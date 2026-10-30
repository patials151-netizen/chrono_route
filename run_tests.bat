@echo off
title ChronoRoute - Algorithmic Test Suite
echo =====================================================================
echo   CHRONOROUTE - VERIFICATION TEST SUITE
echo =====================================================================
echo.

cd /d "%~dp0"

set "PYTHON_EXE="
if exist "C:\Users\Sahil\AppData\Local\Programs\Python\Python315\python.exe" (
    set "PYTHON_EXE=C:\Users\Sahil\AppData\Local\Programs\Python\Python315\python.exe"
) else if exist "%LOCALAPPDATA%\Programs\Python\Python315\python.exe" (
    set "PYTHON_EXE=%LOCALAPPDATA%\Programs\Python\Python315\python.exe"
)

if "%PYTHON_EXE%"=="" (
    set "PYTHON_EXE=python"
)

"%PYTHON_EXE%" test_engine.py

echo.
pause


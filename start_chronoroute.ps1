# ChronoRoute PowerShell Launcher
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$pythonCandidates = @(
    "C:\Users\Sahil\AppData\Local\Programs\Python\Python315\python.exe",
    "$env:LOCALAPPDATA\Programs\Python\Python315\python.exe"
)

$foundPython = $null
foreach ($path in $pythonCandidates) {
    if (Test-Path $path) {
        $foundPython = $path
        $pyDir = Split-Path $path
        $env:Path = "$pyDir;$pyDir\Scripts;" + $env:Path
        break
    }
}

if (-not $foundPython) {
    $dynamicPaths = Get-ChildItem -Path "$env:LOCALAPPDATA\Programs\Python" -Filter "python.exe" -Recurse -ErrorAction SilentlyContinue
    if ($dynamicPaths) {
        $foundPython = $dynamicPaths[0].FullName
        $pyDir = Split-Path $foundPython
        $env:Path = "$pyDir;$pyDir\Scripts;" + $env:Path
    }
}

if (-not $foundPython) {
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCmd) { $foundPython = $pythonCmd.Source }
}

if (-not $foundPython) {
    Write-Host "[ERROR] Python 3.10+ was not found on your PC!" -ForegroundColor Red
    Write-Host "Please install Python from https://www.python.org/downloads/" -ForegroundColor Yellow
    exit 1
}

Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host "  CHRONOROUTE - EMERGENCY VEHICLE PREEMPTION & ROUTE OPTIMIZER       " -ForegroundColor Yellow
Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host "[*] Python interpreter: $foundPython" -ForegroundColor Gray
Write-Host "[*] Launching server on http://localhost:8080 ..." -ForegroundColor Green
Write-Host "[*] Web browser will open automatically." -ForegroundColor White
Write-Host "[*] Press Ctrl+C to terminate the server." -ForegroundColor DarkGray
Write-Host "---------------------------------------------------------------------"

& $foundPython server.py

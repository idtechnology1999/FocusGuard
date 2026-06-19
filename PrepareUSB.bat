@echo off
:: Self-elevate to Administrator if not already
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting Administrator rights...
    powershell -Command "Start-Process '%~f0' -Verb RunAs"
    exit /b
)

:: Run the PowerShell script with execution policy bypassed
:: The window stays open so you can read any error message
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0PrepareUSB.ps1"

:: If PowerShell exited with an error, pause so the message stays visible
if %errorlevel% neq 0 (
    echo.
    echo ERROR: Script failed with code %errorlevel%
    pause
)

@echo off
setlocal

:: Re-launch as administrator if not already elevated
net session >nul 2>&1
if %errorLevel% neq 0 (
    powershell -Command "Start-Process cmd -ArgumentList '/c \"%~f0\"' -Verb RunAs"
    exit /b
)

set "D=%~d0"
set "EXE=%D%\FocusGuard_installed\FocusGuard.exe"

echo.
echo  Focus Guard Setup
echo  Adding Windows Defender exclusions...
powershell -NonInteractive -ExecutionPolicy Bypass -Command "Add-MpPreference -ExclusionPath '%D%\FocusGuard_installed\' -ErrorAction SilentlyContinue; Add-MpPreference -ExclusionProcess 'FocusGuard.exe' -ErrorAction SilentlyContinue; Unblock-File '%EXE%' -ErrorAction SilentlyContinue"

if not exist "%EXE%" (
    echo.
    echo  ERROR: FocusGuard_installed\FocusGuard.exe is missing from %D%
    echo  Make sure you used CopyFolderToUSB.bat to prepare this USB.
    echo.
    pause
    exit /b 1
)

echo  Launching Focus Guard...
echo.

:: Use PowerShell Start-Process WITHOUT -Verb RunAs so the already-elevated
:: token is inherited directly -- this avoids a second UAC prompt.
powershell -NonInteractive -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%EXE%'"
exit /b 0

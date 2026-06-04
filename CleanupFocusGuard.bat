@echo off
:: Run as Administrator — removes every trace of Focus Guard from this PC
:: After this runs, do a fresh install from the USB.

echo ============================================
echo   Focus Guard — Complete Cleanup
echo ============================================
echo.

:: 1. Delete Task Scheduler tasks
echo [1/8] Removing scheduled tasks...
schtasks /delete /tn "FocusGuardWatchdog"   /f >nul 2>&1
schtasks /delete /tn "FocusGuardUSBLaunch"  /f >nul 2>&1
echo       Done.

:: 2. Remove startup registry entry
echo [2/8] Removing startup registry entry...
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v "FocusGuard" /f >nul 2>&1
echo       Done.

:: 3. Delete startup folder shortcut
echo [3/8] Removing startup folder shortcut...
del /f /q "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\FocusGuard.lnk" >nul 2>&1
echo       Done.

:: 4. Remove AutoPlay registry keys
echo [4/8] Removing AutoPlay registry keys...
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\AutoplayHandlers\Handlers\FocusGuardHandler" /f >nul 2>&1
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\AutoplayHandlers\EventHandlers\StorageOnArrival" /v "FocusGuardHandler" /f >nul 2>&1
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\AutoplayHandlers\UserChosenExecuteHandlers\StorageOnArrival" /f >nul 2>&1
echo       Done.

:: 5. Remove Programs & Features entry
echo [5/8] Removing Programs and Features entry...
reg delete "HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\FocusGuard" /f >nul 2>&1
reg delete "HKCU\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\FocusGuard" /f >nul 2>&1
echo       Done.

:: 6. Remove CA certificate
echo [6/8] Removing trusted certificate...
certutil -delstore Root "Focus Guard CA"    >nul 2>&1
certutil -delstore Root "focusguard.local"  >nul 2>&1
echo       Done.

:: 7. Disable the driver event log (was enabled for USB auto-launch)
echo [7/8] Disabling driver event log...
wevtutil set-log "Microsoft-Windows-DriverFrameworks-UserMode/Operational" /enabled:false >nul 2>&1
echo       Done.

:: 8. Delete installed folder and shortcuts
echo [8/8] Deleting installed files and shortcuts...
if exist "%ProgramFiles%\FocusGuard" (
    rd /s /q "%ProgramFiles%\FocusGuard"
    echo       Deleted %ProgramFiles%\FocusGuard
) else (
    echo       Folder not found, skipping.
)
del /f /q "%USERPROFILE%\Desktop\Focus Guard.lnk"  >nul 2>&1
del /f /q "%USERPROFILE%\Desktop\Focus Guard.exe"  >nul 2>&1
del /f /q "%APPDATA%\Microsoft\Windows\Start Menu\Programs\Focus Guard.lnk" >nul 2>&1
echo       Done.

echo.
echo ============================================
echo   Cleanup complete.
echo   You can now do a fresh install from USB.
echo ============================================
echo.
pause

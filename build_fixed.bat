@echo off
echo ========================================
echo   Focus Guard - Build Script
echo ========================================
echo.

echo [1/3] Building executable...
python -m PyInstaller --onefile --windowed --name "FocusGuard" --add-data "config.json;." main.py

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo ERROR: Build failed!
    echo.
    echo Make sure PyInstaller is installed:
    echo   python -m pip install pyinstaller
    echo.
    pause
    exit /b 1
)

echo.
echo [2/3] Copying required files...
copy config.json dist\
copy SYSTEM_DOCUMENTATION.md dist\
copy USB_README.txt dist\
copy autorun.inf dist\

echo.
echo [3/3] Creating USB package folder...
if not exist "USB_Package" mkdir USB_Package
copy dist\FocusGuard.exe USB_Package\
copy config.json USB_Package\
copy SYSTEM_DOCUMENTATION.md USB_Package\
copy USB_README.txt USB_Package\
copy autorun.inf USB_Package\

echo.
echo ========================================
echo   BUILD COMPLETE!
echo ========================================
echo.
echo Executable: dist\FocusGuard.exe
echo USB Package: USB_Package\
echo.
echo TO CREATE USB KEY:
echo 1. Copy everything from USB_Package\ to your USB drive
echo 2. Safely eject USB
echo 3. Insert USB into target computer
echo 4. Run FocusGuard.exe from USB
echo.
pause

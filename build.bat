@echo off
cd /d "%~dp0"

rem ===== Change the exe name here =====
set NAME=Timer
rem ====================================

echo [1/4] Installing dependencies...
rem PyInstaller 6.22.1+ adds onefile parent-process validation that breaks startup
rem with "Security validation failure" when the exe sits in a non-ASCII path and
rem the build/run is elevated.  Pinned until that is fixed upstream.
python -m pip install "pyinstaller==6.22.0" PyQt6 pygame numpy
if errorlevel 1 goto error

echo [2/5] Backing up previous build...
if exist "dist\%NAME%.exe" (
    if not exist backup mkdir backup
    copy /y "dist\%NAME%.exe" "backup\%NAME%_prev.exe" >nul
    echo Previous build saved to backup\%NAME%_prev.exe
)

echo [3/5] Cleaning old build...
rem Only the old exe is removed: dist also holds the MSIX and the release note.
if exist build rmdir /s /q build
if exist "dist\%NAME%.exe" del /q "dist\%NAME%.exe"

echo [4/5] Building %NAME%.exe...
python -m PyInstaller --noconfirm --clean --onefile --windowed --name %NAME% --icon "%~dp0icon.ico" timer.py
if errorlevel 1 goto error

echo [5/5] Refreshing Windows icon cache...
ie4uinit.exe -show

echo.
echo Result: %~dp0dist\%NAME%.exe
pause
exit /b 0

:error
echo.
echo Build failed. See the messages above.
pause
exit /b 1

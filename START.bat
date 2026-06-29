@echo off
setlocal
cd /d "%~dp0"

echo Starting Telegram Giveaway Bot control panel...
echo.

set "PYTHON_CMD="
call :detect_python
if defined PYTHON_CMD goto run_panel

echo Compatible Python was not found.
echo This bot requires Python 3.10 or Python 3.11.
echo.
choice /C YN /M "Install Python 3.11 automatically now?"
if errorlevel 2 goto manual_python

call :install_python
set "PYTHON_CMD="
call :detect_python
if defined PYTHON_CMD goto run_panel

echo.
echo Python installation finished, but Windows cannot see it yet.
echo Close this window and run RUN_BOT_WINDOWS.bat again.
echo.
pause
exit /b 1

:run_panel
echo Using: %PYTHON_CMD%
echo The browser should open automatically.
echo Keep this window open while the bot is running.
echo.
%PYTHON_CMD% control_panel.py
echo.
echo The control panel has stopped or failed to start.
echo Take a photo of this window if an error is shown above.
pause
exit /b 1

:detect_python
py -3.11 --version >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_CMD=py -3.11"
    exit /b 0
)

py -3.10 --version >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_CMD=py -3.10"
    exit /b 0
)

python -c "import sys; raise SystemExit(0 if sys.version_info[:2] in ((3, 10), (3, 11)) else 1)" >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_CMD=python"
    exit /b 0
)

exit /b 0

:install_python
where winget >nul 2>nul
if errorlevel 1 goto no_winget

echo.
echo Installing Python 3.11 through Windows Package Manager...
echo Confirm the Windows installation prompt if it appears.
echo.
winget install --id Python.Python.3.11 -e --source winget --accept-package-agreements --accept-source-agreements
if errorlevel 1 goto install_failed
exit /b 0

:no_winget
echo.
echo Windows Package Manager was not found.
goto manual_python

:install_failed
echo.
echo Automatic Python installation failed.
goto manual_python

:manual_python
start "" "https://www.python.org/downloads/windows/"
echo.
echo Download and install Python 3.11.
echo Enable the Add Python to PATH option during installation.
echo Then run RUN_BOT_WINDOWS.bat again.
echo.
pause
exit /b 1

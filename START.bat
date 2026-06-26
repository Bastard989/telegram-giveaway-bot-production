@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo Запуск панели Telegram Giveaway Bot...
echo.

set "PYTHON_CMD="
call :detect_python
if defined PYTHON_CMD goto run_panel

echo Python не найден.
echo.
echo Боту нужен Python 3.10 или новее.
echo Можно попробовать установить Python автоматически.
echo.
choice /C YN /M "Установить Python автоматически сейчас?"
if errorlevel 2 goto manual_python

call :install_python
set "PYTHON_CMD="
call :detect_python
if defined PYTHON_CMD goto run_panel

echo.
echo Python установлен или установка была запущена, но текущая консоль пока не видит команду Python.
echo Закройте это окно и снова откройте START.bat.
echo.
pause
exit /b 1

:run_panel
echo Используется: %PYTHON_CMD%
echo.
%PYTHON_CMD% control_panel.py
goto end

:detect_python
py -3.11 --version >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_CMD=py -3.11"
    exit /b 0
)

py -3 --version >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_CMD=py -3"
    exit /b 0
)

python --version >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_CMD=python"
    exit /b 0
)

exit /b 0

:install_python
where winget >nul 2>nul
if errorlevel 1 goto no_winget

echo.
echo Устанавливаю Python 3.11 через Windows Package Manager...
echo Если Windows спросит разрешение, подтвердите установку.
echo.
winget install --id Python.Python.3.11 -e --source winget --accept-package-agreements --accept-source-agreements
if errorlevel 1 goto install_failed
exit /b 0

:no_winget
echo.
echo Автоустановщик winget не найден.
echo Сейчас откроется страница скачивания Python.
start "" "https://www.python.org/downloads/windows/"
echo.
echo Скачайте Python 3.11 или новее.
echo Во время установки обязательно включите галочку "Add Python to PATH".
echo После установки снова откройте START.bat.
echo.
pause
exit /b 1

:install_failed
echo.
echo Автоматическая установка Python не завершилась.
echo Сейчас откроется страница скачивания Python.
start "" "https://www.python.org/downloads/windows/"
echo.
echo Скачайте Python 3.11 или новее.
echo Во время установки обязательно включите галочку "Add Python to PATH".
echo После установки снова откройте START.bat.
echo.
pause
exit /b 1

:manual_python
echo.
echo Сейчас откроется страница скачивания Python.
start "" "https://www.python.org/downloads/windows/"
echo.
echo Скачайте Python 3.11 или новее.
echo Во время установки обязательно включите галочку "Add Python to PATH".
echo После установки снова откройте START.bat.
echo.
pause
exit /b 1

:end
if errorlevel 1 (
    echo.
    echo Панель не запустилась.
    echo Проверьте, установлен ли Python 3.10 или новее.
    echo Если ошибка повторяется, откройте руководство по использованию.
    echo.
    pause
)

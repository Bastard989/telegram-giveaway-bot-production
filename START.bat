@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo Запуск панели Telegram Giveaway Bot...
echo.

where py >nul 2>nul
if %errorlevel%==0 (
    py -3 control_panel.py
    goto end
)

where python >nul 2>nul
if %errorlevel%==0 (
    python control_panel.py
    goto end
)

echo Python не найден.
echo.
echo Что сделать:
echo 1. Установите Python 3.10 или новее с сайта https://www.python.org/downloads/
echo 2. При установке обязательно включите галочку "Add Python to PATH".
echo 3. После установки снова откройте START.bat.
echo.
pause
exit /b 1

:end
if errorlevel 1 (
    echo.
    echo Панель не запустилась. Проверьте, установлен ли Python 3.10 или новее.
    echo Если ошибка повторяется, откройте руководство по использованию.
    echo.
    pause
)

@echo off
cd /d "%~dp0"
py control_panel.py
if errorlevel 1 python control_panel.py

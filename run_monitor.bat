@echo off
chcp 65001 >nul

REM === Переход в папку проекта ===
cd /d "%~dp0"

REM === Активация venv ===
call venv\Scripts\activate.bat

REM === Запуск monitor.py ===
echo [RUN] Starting Folder AI Monitor...
python monitor.py

pause

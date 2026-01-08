@echo off

REM ============================================================
REM Activate virtual environment for Folder AI Monitor
REM ============================================================

if not exist venv\Scripts\activate.bat (
    echo [ERROR] Virtual environment not found.
    echo Run install script first.
    pause
    exit /b 1
)

call venv\Scripts\activate.bat

echo.
echo ===============================================
echo  Virtual environment activated
echo ===============================================
echo.

cmd

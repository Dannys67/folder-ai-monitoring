@echo off

REM Переходим в папку проекта
cd /d "%~dp0"

REM Активируем виртуальное окружение
call venv\Scripts\activate.bat

REM Проверка, что venv активирован
where python

REM Пауза, чтобы увидеть ошибки (если будут)
pause

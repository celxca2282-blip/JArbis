@echo off
chcp 65001 >nul
cd /d "%~dp0"

set "ROOT=%~dp0"

REM Общий .env с C++ сборкой (соседняя папка или legacy путь)
if not exist ".env" (
    if exist "%ROOT%..\JArbisC++\.env" copy "%ROOT%..\JArbisC++\.env" ".env" >nul
    if not exist ".env" if exist "C:\JArbisC++\.env" copy "C:\JArbisC++\.env" ".env" >nul
)

set JARBIS_HYBRID=1
set "CPP_EXE="
if exist "%ROOT%..\JArbisC++\build\Release\jarbis.exe" set "CPP_EXE=%ROOT%..\JArbisC++\build\Release\jarbis.exe"
if exist "C:\JArbisC++\build\Release\jarbis.exe" set "CPP_EXE=C:\JArbisC++\build\Release\jarbis.exe"
if defined CPP_EXE set JARBIS_CPP_EXE=%CPP_EXE%

echo JArbis Polyglot: Python + C++ + Node + Go + PowerShell
if not exist "%ROOT%services\node_edge_tts\node_modules" (
    echo Опционально: services\install_sidecars.bat ^(Node Edge-TTS, Go LLM proxy^)
)

if exist "%ROOT%venv\Scripts\python.exe" (
    "%ROOT%venv\Scripts\python.exe" "%ROOT%main.py" %*
) else (
    python "%ROOT%main.py" %*
)
if errorlevel 1 (
    echo.
    echo Ошибка запуска. Сначала: install.bat
    pause
)

@echo off
chcp 65001 >nul
title JArbis — установка
cd /d "%~dp0"

echo.
echo  ========================================
echo   JArbis — установка в один клик
echo  ========================================
echo.

where py >nul 2>&1
if %errorlevel%==0 (
    py -3 scripts\install.py %*
    goto :done
)

where python >nul 2>&1
if %errorlevel%==0 (
    python scripts\install.py %*
    goto :done
)

echo  Не найден Python. Установите Python 3.11 или 3.12:
echo  https://www.python.org/downloads/
echo  При установке включите "Add python.exe to PATH"
echo.
pause
exit /b 1

:done
echo.
pause

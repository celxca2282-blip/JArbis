@echo off
chcp 65001 >nul
cd /d "%~dp0.."
set ZIP=releases\JArbis-v1.0.0-beta.6-win64.zip
if not exist "%ZIP%" (
    echo Сначала соберите релиз:
    echo   venv\Scripts\python.exe scripts\build_exe.py
    echo   venv\Scripts\python.exe scripts\make_release_zip.py
    pause
    exit /b 1
)
echo.
echo === Публикация beta.6 на GitHub ===
echo.
echo 1. Откроется страница New Release
echo 2. Tag: v1.0.0-beta.6
echo 3. Title: JArbis v1.0.0-beta.6 — Public Beta (Windows x64)
echo 4. Включи Pre-release
echo 5. Описание: скопируй из docs\RELEASE_NOTES_v1.0.0-beta.6.md
echo 6. Прикрепи файл: %CD%\%ZIP%
echo.
start "" "https://github.com/celxca2282-blip/JArbis/releases/new?tag=v1.0.0-beta.6&title=JArbis+v1.0.0-beta.6"
explorer /select,"%CD%\%ZIP%"
pause

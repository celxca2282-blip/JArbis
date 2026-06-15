@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo === JArbis sidecar'ы ===

where node >nul 2>&1
if errorlevel 1 (
    echo [Node] не найден — Edge-TTS через Python edge-tts
) else (
    echo [Node] npm install Edge-TTS...
    cd node_edge_tts
    call npm install
    if errorlevel 1 (
        echo Ошибка npm install
        cd ..
        pause
        exit /b 1
    )
    cd ..
    echo [Node] OK
)

where go >nul 2>&1
if errorlevel 1 (
    echo [Go] не найден — LLM напрямую через Python OpenRouter
    echo       Скачать: https://go.dev/dl/
) else (
    echo [Go] сборка LLM proxy...
    cd go_llm_proxy
    call go build -ldflags="-s -w" -o go_llm_proxy.exe .
    if errorlevel 1 (
        echo Ошибка go build
        cd ..
        pause
        exit /b 1
    )
    cd ..
    echo [Go] OK
)

echo.
echo Готово. Запускайте ZAPUSTIT.bat
pause

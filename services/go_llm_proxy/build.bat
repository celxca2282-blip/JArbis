@echo off
chcp 65001 >nul
cd /d "%~dp0"
where go >nul 2>&1
if errorlevel 1 (
    echo Go не найден. Скачайте: https://go.dev/dl/
    exit /b 1
)
go build -ldflags="-s -w" -o go_llm_proxy.exe .
if errorlevel 1 exit /b 1
echo go_llm_proxy.exe готов

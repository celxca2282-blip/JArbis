# JArbis — полигlot-архитектура

JArbis не «переписан на C++». Каждый язык делает то, в чём силён.

| Язык | Роль | Где в проекте |
|------|------|----------------|
| **Python** | HUD (CustomTkinter), LLM/AI, редакторы ярлыков и сценариев, fallback-движок | `C:\JArbis\` |
| **C++** | Real-time голос (Whisper/Vosk/Piper), команды Windows, core-server | `C:\JArbisC++\` TCP **17847** |
| **Node.js** | Edge-TTS (онлайн озвучка Microsoft — лучший npm-стек) | `services/node_edge_tts/` TCP **17848** |
| **Go** | LLM HTTP-прокси к OpenRouter (keep-alive, таймауты) | `services/go_llm_proxy/` TCP **17849** |
| **PowerShell** | Глубокая интеграция с Windows (UWP, аудио, система) | `services/powershell/win_bridge.ps1` |
| **CMake + PowerShell** | Сборка, модели, релиз | `JArbisC++\scripts\` |

## Схема

```
┌──────────────── Python HUD (main.py) ────────────────┐
│  CustomTkinter · настройки · сценарии · ярлыки        │
└────────────┬───────────────────────┬──────────────────┘
             │ TCP 17847             │ SidecarManager
             ▼                       ▼
┌── C++ jarbis.exe ──┐    ┌─ Node Edge-TTS :17848 ─┐
│ Whisper · Piper    │    │ edge-tts npm           │
│ команды · LLM HTTP │    └────────────────────────┘
└─────────┬──────────┘    ┌─ Go LLM proxy :17849 ──┐
          │               │ OpenRouter forward      │
          │               └────────────────────────┘
          │               ┌─ PowerShell bridge ────┐
          └───────────────┴ win_bridge.ps1         ┘
                    data/  ·  .env  (общие)
```

## Запуск

`ZAPUSTIT.bat` → Python HUD + автозапуск sidecar'ов (Node/Go, если установлены).

## Порты

| Порт | Сервис |
|------|--------|
| 17847 | C++ core-server |
| 17848 | Node Edge-TTS |
| 17849 | Go LLM proxy |

## Переменные

| Переменная | Назначение |
|------------|------------|
| `JARBIS_HYBRID=1` | Python UI + C++ core |
| `JARBIS_PYTHON_ROOT` | Путь к `C:\JArbis` для общего `data/` |
| `JARBIS_CPP_EXE` | Путь к `jarbis.exe` |
| `JARBIS_EDGE_TTS_PORT` | Порт Node Edge-TTS (17848) |
| `JARBIS_LLM_PROXY_PORT` | Порт Go LLM proxy (17849) |

## Установка sidecar'ов (опционально)

```bat
C:\JArbis\services\install_sidecars.bat
```

Без Node — Edge-TTS через Python `edge-tts`. Без Go — LLM напрямую через Python OpenRouter SDK.

## Почему не «только Python + C++»

| Задача | Лучший инструмент | Почему |
|--------|-------------------|--------|
| GUI, LLM, редакторы | **Python** | CustomTkinter, богатая AI-экосистема |
| Real-time STT/TTS, команды | **C++** | Низкая задержка, Whisper/Piper in-process |
| Edge-TTS (Microsoft) | **Node.js** | Официальный npm `edge-tts`, изолирован от GIL |
| LLM HTTP к OpenRouter | **Go** | Лёгкий прокси с keep-alive, не блокирует Python |
| UWP, аудио, Win32 API | **PowerShell** | Нативный доступ к Windows без COM в Python |
| Сборка C++ | **CMake + PowerShell** | Кросс-платформенная сборка + скрипты моделей |

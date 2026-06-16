# JArbis v1.0.0-beta.6 — Public Beta (Windows x64)

**Hybrid polyglot:** Python HUD + опционально C++ движок в папке `engine/`.

## Что нового

- **Гибридный режим** — CustomTkinter HUD + C++ core-server (голос/команды быстрее)
- **Sidecar'ы** — Node Edge-TTS, Go LLM proxy, PowerShell bridge (опционально)
- **Исправления GUI** — пустой dashboard, вкладка ярлыков, зависание Stop
- **install.bat** — корректное обновление pip на Windows

## Установка

1. Скачай **`JArbis-v1.0.0-beta.6-win64.zip`** (не Source code)
2. Распакуй папку `JArbis`
3. **`УСТАНОВИТЬ.bat`** → **`ЗАПУСТИТЬ.bat`**
4. Читай `КАК_ТЕСТИРОВАТЬ.txt` внутри архива

## C++ движок

Если в архиве есть `engine/jarbis.exe` — гибрид включится автоматически.  
Без него работает Python fallback (медленнее STT, но всё функционирует).

Отдельный репозиторий движка: https://github.com/celxca2282-blip/JArbisCpp

## Обратная связь

- [Сообщить о баге](https://github.com/celxca2282-blip/JArbis/issues/new?template=bug_report.md)
- [Идея / feedback](https://github.com/celxca2282-blip/JArbis/issues/new?template=feature_request.md)

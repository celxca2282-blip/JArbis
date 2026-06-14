# JArbis — полный отчёт о проделанной работе

**Проект:** голосовой ассистент для Windows (Python 3.11/3.12)  
**Версия:** 1.0.0  
**Репозиторий:** https://github.com/celxca2282-blip/JArbis  
**Период работы:** 14 июня 2026 (сессии Ask mode + Agent mode)  
**Дата отчёта:** 14 июня 2026  

---

## Содержание

1. [Краткое резюме](#1-краткое-ресюме)
2. [Хронология по фазам](#2-хронология-по-фазам)
3. [Ядро: STT, wake-word, LLM, TTS](#3-ядро-stt-wake-word-llm-tts)
4. [Команды, сценарии, приложения](#4-команды-сценарии-приложения)
5. [GUI и UX](#5-gui-и-ux)
6. [Голоса (TTS) — эволюция](#6-голоса-tts--эволюция)
7. [Сборка exe и релизы](#7-сборка-exe-и-релизы)
8. [Подготовка для тестера и VM](#8-подготовка-для-тестера-и-vm)
9. [GitHub, CI, установка в 1 клик](#9-github-ci-установка-в-1-клик)
10. [Большой аудит и рефакторинг](#10-большой-аудит-и-рефакторинг)
11. [Исправления багов (полный список)](#11-исправления-багов-полный-список)
12. [Тестирование](#12-тестирование)
13. [Git-коммиты](#13-git-коммиты)
14. [Структура проекта (итог)](#14-структура-проекта-итог)
15. [Безопасность и секреты](#15-безопасность-и-секреты)
16. [Что не сделано / отложено](#16-что-не-сделано--отложено)
17. [Артефакты сборки](#17-артефакты-сборки)
18. [Приложение: индекс запросов пользователя](#18-приложение-индекс-запросов-пользователя)

---

## 1. Краткое резюме

За одну интенсивную сессию проект прошёл путь от **минимального CLI-скрипта** («попугай с эхо») до **полноценного голосового ассистента** с:

- wake-word («Джарвис») через Vosk / openWakeWord
- распознаванием речи (faster-whisper)
- LLM через OpenRouter (DeepSeek и др.)
- озвучкой Piper HD (офлайн) + Edge TTS + SAPI
- GUI в стиле Luxify / Iron Man HUD (CustomTkinter)
- управлением Windows, ярлыками, сценариями, сканом игр
- быстрым режимом без LLM
- системным треем
- **Windows exe** (~1.4 ГБ) без установки Python
- **GitHub-ready** код с CI, тестами, документацией

**Тесты на конец работ:** **107 passed** (`python -m pytest tests/`).

---

## 2. Хронология по фазам

| Фаза | Время (ориентир) | Суть |
|------|------------------|------|
| **0. Прототип** | ночь 14.06 | STT + LLM + TTS + wake-word, базовый main.py |
| **1. Архитектура** | утро 14.06 | config.py, logging, response_processor, memory, search, tests |
| **2. Команды Windows** | утро 14.06 | whitelist, SYSTEM_TARGETS, app scanner, STT normalize |
| **3. GUI v1** | день 14.06 | CustomTkinter, dashboard, настройки, трей |
| **4. Luxify HUD** | день 14.06 | 2200+ строк UI, theme, орб, страницы |
| **5. Голоса** | день 14.06 | Silero → Piper HD, voice picker, scroll fix |
| **6. Exe** | вечер 14.06 | PyInstaller, иконки, bundle fixes |
| **7. Тестер + GitHub** | вечер 14.06 | очистка dist, гайд, Releases workflow |
| **8. Аудит + релиз** | вечер 14.06 | requirements split, LLM fallback, CI, install.bat |
| **9. VM-сборка** | вечер 14.06 | пересборка exe, zip для виртуалки |

---

## 3. Ядро: STT, wake-word, LLM, TTS

### 3.1. Speech-to-Text (`jarvis/voice/stt_module.py`)

| Изменение | Детали |
|-----------|--------|
| Whisper на CPU | Убрана принудительная CUDA; `device=cpu`, `compute_type=int8` по умолчанию на CPU |
| Модель | Дефолт повышен с `base` → `small` → `medium` (quality mode); в exe hook — `small` |
| CUDA fallback | При ошибке GPU — автоматический откат на CPU |
| VAD | Silero VAD v6; fallback без `vad_filter` если модель недоступна в bundle |
| Микрофон | `list_input_devices()`, выбор в GUI, `STT_INPUT_DEVICE`, тест уровня сигнала |
| Скорость прослушивания | Уменьшена пауза тишины (~1.0 с), `beam_size=3`, margin для confidence |
| initial_prompt | Динамический prompt с wake-word и топом приложений (меньше галлюцинаций) |
| Нормализация | Пост-обработка типичных ошибок Whisper (настройки, wifi, блютуз и т.д.) |
| Frozen exe | `STT_FORCE_CPU=1` через runtime hook `pyi_rth_jarbis.py` |

### 3.2. Wake-word (`jarvis/voice/wake_word_module.py`)

| Изменение | Детали |
|-----------|--------|
| openWakeWord | Модель `jarvis`, pyaudio 16 kHz, порог 0.5 |
| ONNX вместо TFLite | `inference_framework='onnx'` (TFLite не ставится на Win + Py 3.11) |
| Авто-скачивание моделей | `openwakeword.utils.download_models()` (ручной URL давал 404) |
| Два движка | `WAKE_WORD_ENGINE`: `vosk` (дефолт) / `openwakeword` |
| Имя wake-word | `WAKE_WORD_NAME`: «джарвис» / «прием» и т.д. |
| Vosk RU | Русская модель, KaldiRecognizer, распознавание слова из partial/final |
| Единый микрофон | Wake-word использует тот же `STT_INPUT_DEVICE`, что и STT |
| Отображение | TTS и логи показывают «Джарвис», не «прием» |

### 3.3. LLM (`jarvis/ai/llm_module.py`)

| Изменение | Детали |
|-----------|--------|
| DeepSeek API | Первоначально `api.deepseek.com`, модель `deepseek-reasoner` |
| OpenRouter | `https://openrouter.ai/api/v1`, модель `deepseek/deepseek-r1` → `deepseek/deepseek-chat` |
| Ключ | `OPENAI_API_KEY` (OpenRouter), загрузка через `python-dotenv` |
| Заголовки | `HTTP-Referer`, `X-Title` для OpenRouter |
| System prompt | Много итераций: ирония → без ролеплея → лаконичность 1–2 предложения → теги SEARCH/EXEC |
| Время | Текущее время в каждом запросе (`datetime.now()`) |
| Поиск | Тег `[SEARCH:...]` → `search_module` → `get_final_answer` |
| Память | Интеграция с `memory_module`, фразы очистки памяти |
| Graceful fallback | **Не падает** без ключа: `LlmUnavailableError`, `friendly_llm_error()`, локальные команды работают |
| История | `CONVERSATION_HISTORY` для контекста |

### 3.4. TTS — базовый (`jarvis/voice/tts_module.py`)

| Изменение | Детали |
|-----------|--------|
| Edge-TTS | `ru-RU-DmitryNeural`, pygame для воспроизведения |
| Temp-файлы | UUID-имена `temp_audio_*.mp3`, cleanup при старте |
| WinError 32 | try-except вокруг `os.remove`, не удалять пока pygame держит файл |
| Маршрутизация | `piper` / `edge` / `sapi` / `silero` через `resolve_tts_engine()` |
| Fast mode | Piper HD вместо Edge/SAPI |
| Stop | Кнопка «Стоп» в GUI прерывает озвучку |
| reload | `reload_tts_settings()` после смены голоса в GUI |

### 3.5. Точка входа (`main.py`)

| Изменение | Детали |
|-----------|--------|
| GUI по умолчанию | `python main.py` → `JarvisApp` |
| CLI | `python main.py --cli` → `engine.run_cli_loop()` |
| Логирование | `logging.basicConfig` в начале, консоль + `data/jarvis.log` |
| DEBUG_TEXT_MODE | Текстовый ввод вместо STT/wake-word для отладки |
| Ctrl+Z откат | Восстановлен GUI-лаунчер после случайного отката на старый CLI-цикл |
| Размер | ~94 строки (логика в `assistant_engine`) |

---

## 4. Команды, сценарии, приложения

### 4.1. `jarvis/commands/commands_module.py`

- Whitelist `ALLOWED_COMMANDS` (блокировка опасных команд)
- Локальные триггеры (ступень 1, до LLM)
- `execute_system_command()`, `execute_workflow()`
- Точечные URI Windows: `SYSTEM_TARGETS` (wifi, bluetooth, display, звук и т.д.)
- Команды: блокировка ПК, калькулятор, блокнот, громкость, скриншот и др.
- Thread lock для потокобезопасности (аудит)

### 4.2. `jarvis/ai/response_processor.py`

- Парсинг `[EXEC:...]`, `[SAVE_MEMORY:...]`, `[OPEN_APP:...]`, `[SEARCH:...]`
- Возврат `(clean_text, commands, memories)` — теги не озвучиваются

### 4.3. `jarvis/ai/memory_module.py`

- Профиль пользователя `data/user_profile.json`
- Сохранение/чтение фактов из LLM-тегов

### 4.4. `jarvis/ai/search_module.py`

- Веб-поиск через `ddgs` (миграция с `duckduckgo-search`)
- Результаты передаются в `get_final_answer(original_query=...)`

### 4.5. App scanner (`jarvis/commands/app_scanner.py`)

- Индекс установленных приложений `data/apps_index.json`
- Кэш, перескан из GUI
- Голосовое `[OPEN_APP:name]` через fuzzy match
- Кнопка «Удалить индекс» в настройках

### 4.6. User apps (`jarvis/commands/user_apps_store.py`)

- Ярлыки: exe / url / folder + голосовые триггеры
- `data/user_apps.json`
- Тройное подтверждение для «удалить все ручные ярлыки»

### 4.7. Game scanner (`jarvis/commands/game_scanner.py`)

- Steam, Epic, папки Games
- Превью с чекбоксами перед импортом
- Кнопка «Удалить скан» — только игры из скана

### 4.8. Сценарии (`jarvis/commands/scenario_store.py`, `scenario_runner.py`)

- Визуальный редактор в GUI
- Шаги: exe, url, app_index, command, user_app, delay
- Preset «Начать работу» при первом запуске
- `data/scenarios.json`

### 4.9. STT utils (`jarvis/core/stt_text_utils.py`)

- `normalize_stt_text()` — исправление типичных ошибок Whisper
- Вынесено из commands для чистоты архитектуры

### 4.10. Assistant engine (`jarvis/core/assistant_engine.py`)

- Центральный цикл: wake → STT → local → LLM → TTS
- Event bus, app state, performance profiles
- Fast mode / quality mode
- Рефакторинг main.py → engine (аудит)

---

## 5. GUI и UX

### 5.1. Luxify HUD (`jarvis/gui/`)

- **~2200+ строк** UI-кода
- `theme.py` — палитра, типографика, `panel_frame`, `accent_panel`, `ghost_button`, `badge_label`
- `hud_background.py`, `status_orb.py` — анимированный орб (idle/wake/listening/thinking/speaking)
- Страницы: dashboard, apps, scenarios, settings, logs
- Top bar, nav, stat tiles, conversation bubble
- **Баг #00d4ff22:** CustomTkinter не поддерживает `#RRGGBBAA` → `blend_colors()`, `soft_tint()`

### 5.2. Dashboard

- Орб статуса, последняя STT-фраза, ответ, мини-лог
- Анимация индикатора речи пользователя
- Бейдж `⚡ FAST` / `◆ QUALITY`
- Refresh после автозапуска движка

### 5.3. Настройки

- Wake-word, STT/TTS, LLM, микрофон (combobox), перескан индекса
- Voice picker (см. раздел 6)
- Быстрый режим

### 5.4. UX-исправления

| Проблема | Решение |
|----------|---------|
| Тест микрофона «ломался» | Переработан UI теста, понятный feedback |
| Меню некрасивое | Минималистичный редизайн навигации |
| Скролл колёсиком в голосах | `scroll_utils.py`, `SmartScrollableFrame`, изоляция вложенного скролла |
| Срезанные углы у тестера | Подгонка окна под экран, масштаб 100% Windows |
| Трей | Клик по иконке открывает окно; закрытие X → сворачивание |
| Логи | Auto-refresh на `logs_page`, экспорт |
| Уровень микрофона | `MIC_LEVEL` на орбе |

### 5.4. Иконки (`jarvis/gui/assets/`, `scripts/build_icons.py`)

- Из `source_icon.png`: `icon.png`, `icon.ico`, `icon_512.png`
- Tray: `tray_idle.png`, `tray_listen.png`
- UI: app, mic, play, scenario, settings

---

## 6. Голоса (TTS) — эволюция

```
Edge-TTS only
    → + Windows SAPI
    → + Silero v3/v4/v5 (15 пресетов)
    → Piper HD (финал, дефолт)
```

### 6.1. Silero (legacy)

- `jarvis/voice/silero_tts.py`
- Скачивание с `models.silero.ai` (обход 403 GitHub / баг torch.hub)
- Проблемы: дубли пресетов, «под кайфом» (speed 0.85), заторможенность, качество
- Опционально: `requirements-optional-silero.txt` (~2 ГБ torch)

### 6.2. Piper HD (основной)

- `jarvis/voice/piper_tts.py`
- Голоса: ruslan (дефолт), dmitri, denis, irina (~60 МБ каждый)
- HuggingFace `rhasspy/piper-voices`
- 7 уникальных пресетов в UI
- `scripts/download_voice.py`
- Миграция `silero` → `piper` в `load_gui_settings()`

### 6.3. Voice picker (`jarvis/gui/widgets/voice_picker.py`)

- Hero-карточка + «Прослушать»
- Фильтры: Все / Офлайн / RU / EN
- Сетка кликабельных карточек
- Свёрнутая «Тонкая настройка» (Edge, SAPI)

### 6.4. Стек озвучки (итог)

```
speak() → resolve_tts_engine()
    ├── piper   → piper_tts.speak()     [по умолчанию]
    ├── edge    → speak_edge()          [онлайн]
    ├── sapi    → _speak_sapi()         [запасной]
    └── silero  → speak_silero()        [legacy]
```

---

## 7. Сборка exe и релизы

### 7.1. Инструменты

| Файл | Назначение |
|------|------------|
| `jarbis.spec` | PyInstaller spec, onedir bundle |
| `scripts/build_exe.py` | Запуск сборки |
| `scripts/pyi_rth_jarbis.py` | Runtime hook: cwd, DLL paths, STT CPU/small |
| `scripts/exe_bundle_manifest.py` | Список критичных файлов в bundle |
| `scripts/verify_exe_bundle.py` | Автопроверка dist |
| `scripts/make_release_zip.py` | Zip для Releases / VM |
| `scripts/prepare_tester_dist.py` | Очистка dist для тестера |

### 7.2. Исправления exe (критичные)

| # | Симптом | Причина | Исправление |
|---|---------|---------|-------------|
| 1 | Exe сразу закрывается | Нет `piper/espeak-ng-data` | Добавлен в `jarbis.spec` |
| 2 | Wake-word не работает | Нет `libvosk.dll` | Полный пакет `vosk` в spec |
| 3 | STT падает после wake | Нет `silero_vad_v6.onnx` | `faster_whisper/assets` в spec |
| 4 | scipy / DLL errors | Неполный bundle | ctranslate2, onnxruntime, certifi |
| 5 | «Не слышит» | CUDA в exe, другой микрофон | `STT_FORCE_CPU`, единый input device |
| 6 | Долго «слушает» | Длинная пауза VAD | silence 1.0s, beam 3, confidence margin |
| 7 | scipy hidden import | PyInstaller | hiddenimports в spec |

### 7.3. config.py для frozen

```python
if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys.executable).resolve().parent
```

Данные, `.env`, логи — рядом с `JArbis.exe`.

### 7.4. Bundle — обязательные пути

- `_internal/piper/espeak-ng-data/`
- `_internal/vosk/libvosk.dll`
- `_internal/faster_whisper/assets/silero_vad_v6.onnx`
- `_internal/jarvis/gui/assets/icon.ico`
- `_internal/customtkinter/assets/`
- `_internal/ctranslate2/`, `_internal/onnxruntime/capi/`
- `_internal/certifi/cacert.pem`

---

## 8. Подготовка для тестера и VM

### 8.1. `prepare_tester_dist.py` удаляет

**Корень dist:**
- `.env`, `crash.log`

**data/:**
- `jarvis.log`, `gui_settings.json`, `user_profile.json`
- `user_apps.json`, `apps_index.json`, `.tray_hint_shown`

**_internal/:**
- `.env`, `.env.example` (копия в корне через `.env.example`)

### 8.2. Добавляет в dist

- `КАК_ТЕСТИРОВАТЬ.txt` — полный гайд
- `УСТАНОВИТЬ.bat` — создаёт `.env` из шаблона
- `ЗАПУСТИТЬ.bat` — запуск exe
- `.env.example` в корне

### 8.3. Артефакты (14.06.2026, вечер)

| Путь | Размер |
|------|--------|
| `dist/JArbis/` | ~1.4 ГБ |
| `releases/JArbis-v1.0.0-win64.zip` | ~1.37 ГБ (1 466 671 983 байт) |
| `dist/JArbis/JArbis.exe` | ~35 МБ |

### 8.4. Инструкция для VM

1. Скопировать zip или папку `dist/JArbis`
2. `УСТАНОВИТЬ.bat` → `.env`
3. При необходимости — `OPENAI_API_KEY` в `.env`
4. `ЗАПУСТИТЬ.bat`
5. Python не нужен; Windows 10/11 x64, микрофон, интернет на первом запуске

---

## 9. GitHub, CI, установка в 1 клик

### 9.1. GitHub

- Репозиторий: `celxca2282-blip/JArbis`
- `docs/GITHUB.md` — workflow с тестером
- `.gitignore` — `.env`, `dist/`, `build/`, логи, модели, личные data
- `.github/ISSUE_TEMPLATE/bug_report.md`
- `.github/workflows/ci.yml` — pytest на push
- `CONTRIBUTING.md`

### 9.2. Releases workflow

```powershell
python scripts/build_exe.py
python scripts/make_release_zip.py --version 1.0.0
```

Exe **не в git** — только в GitHub Releases (~2 ГБ).

### 9.3. Установка в 1 клик (исходники)

| Файл | Действие |
|------|----------|
| `install.bat` | venv + pip + `.env` + Piper voice |
| `scripts/install.py` | Логика установки (177 строк) |
| `ЗАПУСТИТЬ.bat` | Запуск через venv |

### 9.4. Git push (14.06.2026)

3 коммита на `origin/main` (см. раздел 13).

---

## 10. Большой аудит и рефакторинг

Промпт «JArbis — большой аудит» (вечер 14.06):

### 10.1. Requirements

| Файл | Содержимое |
|------|------------|
| `requirements.txt` | Runtime (prod) |
| `requirements-dev.txt` | + pytest, dev tools |
| `requirements-optional-silero.txt` | torch, torchaudio |

### 10.2. config.py + jarvis/config_env.py

- `env_str`, `env_bool`, `env_int`, `env_float`
- `apply_gui_mapping()` — GUI settings ↔ env
- `has_api_key()`, `VERSION = "1.0.0"`
- Единая загрузка `.env` из `BASE_DIR`

### 10.3. LLM graceful degradation

- Без ключа — сообщение пользователю, не crash
- `friendly_llm_error()`, `LlmUnavailableError`

### 10.4. Тесты

- `pytest.ini`, `tests/conftest.py`
- Новые: `test_config.py`, `test_llm.py`, `test_engine.py`, `test_install.py`, `test_release_tools.py`
- Часть тестов вынесена из монолитного `test_jarvis.py`

### 10.5. assistant_engine

- Рефакторинг цикла из main
- Тесты engine без GUI

### 10.6. Прочее

- TTS Silero optional (не в base requirements)
- commands lock
- README обновлён
- `.env.example` актуализирован

---

## 11. Исправления багов (полный список)

| ID | Область | Проблема | Решение |
|----|---------|----------|---------|
| B01 | STT | CUDA float16 в консоли | Принудительный CPU int8 / auto с fallback |
| B02 | STT | CUDA DLL crash на первой фразе | STT_FORCE_CPU, fallback на CPU |
| B03 | STT | Галлюцинации initial_prompt | Динамический prompt, модель small/medium |
| B04 | STT | «Не слышит» в exe | Единый микрофон, CPU, тест peak energy |
| B05 | STT | Долго слушает после команды | silence_duration ↓, beam ↓, confidence margin |
| B06 | Wake | tflite не ставится | inference_framework='onnx' |
| B07 | Wake | 404 при скачивании модели | download_models() |
| B08 | Wake | «прием» vs «Джарвис» | WAKE_WORD_NAME=джарвис, display name |
| B09 | Wake | Срабатывает в длинной фразе | Улучшена логика детекции |
| B10 | LLM | Ролеплей, звёздочки | Жёсткий SYSTEM_PROMPT |
| B11 | LLM | Crash без API key | Graceful fallback |
| B12 | LLM | DEBUG prints | Убраны, заменены на logging |
| B13 | TTS | WinError 32 на temp mp3 | UUID имена, try-except remove |
| B14 | TTS | temp файлы не удаляются | cleanup() при старте |
| B15 | Search | duckduckgo-search deprecated | pip install ddgs |
| B16 | GUI | TclError #RRGGBBAA | blend_colors, soft_tint |
| B17 | GUI | Ctrl+Z откат main.py | Восстановлен GUI launcher |
| B18 | GUI | DEBUG_TEXT_MODE включён | Исправлен .env / config default False |
| B19 | GUI | Скролл всей страницы в voice picker | SmartScrollableFrame |
| B20 | GUI | Срезанный UI у тестера | window geometry, DPI |
| B21 | GUI | Dashboard crash TclError | Исправлены цвета/виджеты |
| B22 | Exe | Мгновенное закрытие | Piper espeak-ng-data в bundle |
| B23 | Exe | Vosk DLL missing | vosk package в spec |
| B24 | Exe | VAD onnx missing | faster_whisper assets |
| B25 | Exe | scipy / hidden imports | jarbis.spec hiddenimports |
| B26 | Dist | API key у тестера | prepare_tester_dist, no .env |
| B27 | Dist | gui_settings.json с ключом | Удаляется из dist |
| B28 | Zip | UnicodeEncodeError в print | Косметический баг в make_release_zip (→ стрелки) |
| B29 | Silero | Authorization при download | Прямая загрузка models.silero.ai |
| B30 | Voice | Дубли, slow, «под кайфом» | Piper HD, 7 пресетов |
| B31 | Mic test | Странное поведение | Переработан UI теста |
| B32 | Stop button | Речь не останавливается | stop_speech() в TTS/engine |

---

## 12. Тестирование

### 12.1. Итог

```
python -m pytest tests/
107 passed in ~11s
```

### 12.2. Файлы тестов

| Файл | Покрытие |
|------|----------|
| `tests/test_jarvis.py` | Основной набор (~88+ тестов): commands, STT utils, TTS, wake, GUI helpers |
| `tests/test_config.py` | config, env helpers |
| `tests/test_llm.py` | LLM fallback, prompts |
| `tests/test_engine.py` | assistant_engine |
| `tests/test_install.py` | install.py |
| `tests/test_release_tools.py` | bundle verify, release scripts |
| `tests/conftest.py` | fixtures, temp paths |

### 12.3. История счётчика

- ~90 тестов — после Piper/GUI сессии
- 107 тестов — после аудита + install/release tests

---

## 13. Git-коммиты

| Hash | Дата | Сообщение |
|------|------|-----------|
| `f001712` | 2026-06-14 | Initial commit: JArbis voice assistant (~84 файла, +13263 строк) |
| `58b5f0a` | 2026-06-14 | Коротко что изменилось (аудит: requirements, config_env, LLM, CI, tests) |
| `57baf3a` | 2026-06-14 | Установка в один клик: install.bat, ЗАПУСТИТЬ.bat, bat для exe |

**Remote:** `origin/main` — push выполнен 14.06.2026.

---

## 14. Структура проекта (итог)

```
JArbis/
├── main.py                 # Точка входа GUI/CLI
├── config.py               # Конфиг, VERSION, пути frozen
├── install.bat             # Установка в 1 клик
├── ЗАПУСТИТЬ.bat           # Запуск из venv
├── jarbis.spec             # PyInstaller
├── requirements.txt
├── requirements-dev.txt
├── requirements-optional-silero.txt
├── .env.example
├── jarvis/
│   ├── ai/                 # llm, search, memory, response_processor
│   ├── commands/           # commands, scanner, scenarios, user_apps
│   ├── core/               # assistant_engine, stt_text_utils, event_bus
│   ├── gui/                # HUD, pages, widgets, theme, tray
│   ├── voice/              # stt, tts, piper, silero, wake_word
│   └── config_env.py
├── scripts/                # build, install, release, icons, voice download
├── tests/
├── docs/
│   ├── CHANGELOG.md        # Лог GUI/голосов/exe (сессия до аудита)
│   ├── GITHUB.md
│   └── WORK_REPORT_FULL.md # Этот файл
└── data/                   # user data (не в git)
    ├── jarvis.log
    ├── user_profile.json
    ├── apps_index.json
    ├── user_apps.json
    ├── scenarios.json
    └── temp/
```

---

## 15. Безопасность и секреты

| Правило | Статус |
|---------|--------|
| `.env` в `.gitignore` | ✅ |
| `data/gui_settings.json` в `.gitignore` | ✅ |
| API key не в dist для тестера | ✅ (prepare_tester_dist) |
| Старый dist светил ключ в gui_settings | ⚠️ Рекомендована **смена ключа** OpenRouter |
| Личные user_apps/profile не копируются в dist | ✅ |
| exe zip не коммитится | ✅ |

---

## 16. Что не сделано / отложено

- [ ] LICENSE (MIT и т.д.) — не выбран пользователем
- [ ] GitHub Release с zip — инструкция есть, загрузка вручную
- [ ] Полный split `test_jarvis.py` на модули
- [ ] Глубокий рефактор `app_scanner.py` / `commands_module.py`
- [ ] `confirm_utils.py` — тройное подтверждение удаления (частично в user_apps)
- [ ] Piper EN / Coqui XTTS / модель ~500 МБ male RU
- [ ] RVC / клонирование голоса
- [ ] Исправление UnicodeEncodeError в `make_release_zip.py` (стрелки → ASCII)
- [ ] Скриншоты в `docs/screenshots/`

---

## 17. Артефакты сборки

### Команды сборки

```powershell
cd C:\JArbis
python scripts/build_exe.py
python scripts/prepare_tester_dist.py
python scripts/verify_exe_bundle.py
python scripts/make_release_zip.py --version 1.0.0
```

### Результат

- `C:\JArbis\dist\JArbis\` — готовая папка
- `C:\JArbis\releases\JArbis-v1.0.0-win64.zip` — архив для VM/тестера/Releases

### Содержимое dist (корень)

- `JArbis.exe`
- `_internal/`
- `.env.example`
- `УСТАНОВИТЬ.bat`
- `ЗАПУСТИТЬ.bat`
- `КАК_ТЕСТИРОВАТЬ.txt`

---

## 18. Приложение: индекс запросов пользователя

Полный список задач из сессии (128 user_query в transcript). Сгруппировано по темам.

### Ядро и API
1. Whisper CPU int8 вместо CUDA
2. Создать llm_module.py (DeepSeek)
3. main.py — убрать эхо, вызов get_ai_response
4. OpenRouter вместо DeepSeek direct
5. OPENAI_API_KEY, debug headers
6. python-dotenv
7. Полноценный ассистент: LLM + speak()
8. SYSTEM_PROMPT без ролеплея + время
9. openWakeWord wake-word
10. ONNX inference framework
11. Авто-скачивание wake models
12. download_models() вместо ручного URL
13. Логирование во всём проекте
14. vosk + openwakeword dual engine
15. Лаконичность LLM, задержки, починка ответов
16. response_processor.py
17. config.py единый + .gitignore
18. DEBUG_TEXT_MODE
19. tests.py / pytest
20. search_module + [SEARCH:]
21. ddgs вместо duckduckgo-search
22. Workflow «Начать работу»
23. SYSTEM_TARGETS Windows URI
24. normalize_stt_text после STT
25. STT quality upgrade (small, VAD, mic)
26. Wake-word «Джарвис» вместо «прием»

### GUI
27. GUI CustomTkinter
28. TclError dashboard fix
29. Тест микрофона + минималистичное меню
30. Анимация индикатора речи
31. Режим вопроса — реализация планов
32. Удаление сканированных игр
33. Stop — прервать TTS
34. Удалить индекс / triple confirm user apps
35. Идеал fast mode
36. Luxify HUD 1000+ строк
37. Терминал — диагностика ошибок

### Голоса
38. «делай голоса» (Edge/SAPI/Silero)
39. Ctrl+Z проверка, оптимизация
40. «делай silero»
41. Больше озвучек
42. Voice picker UI
43. Scroll bug в voice menu
44. Piper HD вместо Silero
45. CHANGELOG.md

### Exe и релиз
46. Иконки + exe
47. Exe закрывается — fix bundle
48. Новые ошибки exe (scipy, vosk, vad)
49. Не слышит микрофон
50. Проверка всех файлов bundle
51. Долго слушает — STT tuning
52. Подготовка dist для тестера + гайд
53. Баги у тестера (UI, библиотеки)
54. GitHub организация
55. Большой аудит промпт
56. install.bat в 1 клик
57. git push
58. exe для виртуалки
59. Как перенести на VM (VirtualBox shared folder)
60. **Полный отчёт** (этот документ)

---

## Связанные документы

- `docs/CHANGELOG.md` — детальный лог GUI/голосов/exe (сессия до GitHub-аудита)
- `docs/GITHUB.md` — workflow с тестером и Releases
- `README.md` — быстрый старт
- `CONTRIBUTING.md` — для контрибьюторов
- `КАК_ТЕСТИРОВАТЬ.txt` — в dist для тестера

---

*Документ сгенерирован по истории разработки, git log, transcript сессии и состоянию кодовой базы на 14.06.2026.*

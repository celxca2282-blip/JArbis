# Джарвис — голосовой ассистент для Windows

Голосовой помощник с wake-word, распознаванием речи (Whisper), LLM (OpenRouter) и управлением Windows.

## Установка

```bash
pip install -r requirements.txt
```

Скопируйте `.env.example` в `.env` и укажите `OPENAI_API_KEY` (ключ OpenRouter).

## Запуск

```bash
python main.py          # GUI (по умолчанию) — тёмный интерфейс Jarvis HUD
python main.py --cli    # консольный режим (отладка)
```

Скажите wake-word **«Джарвис»**, затем команду. Для выхода: «стоп», «выход», «пока».

### GUI

Тёмная тема в стиле Iron Man / Jarvis HUD (CustomTkinter):

- **Панель** — статус-орб (idle / wake / listening / thinking / speaking), последняя STT-фраза, ответ, мини-лог
- **Ярлыки** — программы (`.exe`), ссылки (`url`) и папки с голосовыми триггерами; опциональный скан игр
- **Сценарии** — визуальный редактор цепочек: EXE, URL, приложение из индекса, системная команда, пауза
- **Настройки** — wake-word, STT/TTS, LLM, выбор микрофона из списка, перескан индекса
- **Логи** — просмотр `data/jarvis.log` с автообновлением, экспорт

Закрытие окна (X) сворачивает в **системный трей** — голосовой ассистент продолжает работать. **Клик по иконке** в трее открывает окно (ПКМ — меню).

**Быстрый режим** (`Настройки → Общее`): Whisper `small`, локальный **Piper HD**, только заготовленные команды без LLM. На обзоре — бейдж `⚡ FAST` / `◆ QUALITY`.

Скриншоты: положите PNG в `docs/screenshots/` (dashboard, apps, scenarios).

### Сравнение с Luxify Assistant

| Возможность | JArbis |
|---|---|
| Open source | Да |
| Свои ярлыки (exe / url / папка) + голосовые триггеры | Да (`data/user_apps.json`) |
| Редактор сценариев | Да (`data/scenarios.json`) |
| LLM + локальные команды | Да |
| Быстрый режим (без LLM) | Да |
| Системный трей | Да |

## Пользовательские ярлыки

В GUI: **Ярлыки → + Добавить** — выберите тип:

| Тип | Поле | Пример триггера |
|---|---|---|
| Программа | путь к `.exe` | «открой мою игру» |
| Ссылка | `https://…` | «открой ютуб» |
| Папка | абсолютный путь | «открой проекты» |

**Скан игр** (кнопка на той же вкладке) — опциональный поиск в Steam, Epic и папках `Games`. Перед импортом показывается превью с чекбоксами. Кнопка **«Удалить скан»** убирает все ярлыки, добавленные через скан; ручные ярлыки не затрагиваются.

Хранилище: `data/user_apps.json`. Голосовая команда срабатывает **до LLM** (ступень 1).

## Сценарии

В GUI: **Сценарии** — конструктор шагов, голосовые триггеры, кнопка «Запустить».

Типы шагов: `exe`, `url`, `app_index`, `command`, `user_app`, `delay`.

Preset **«Начать работу»** создаётся автоматически при первом запуске. Голосом: «начать работу», «рабочий режим». LLM: `[EXEC:start_work]`.

Хранилище: `data/scenarios.json`.

## Настройки (.env)

| Переменная | Описание |
|---|---|
| `WAKE_WORD_NAME` | Кодовое слово (по умолчанию `джарвис`) |
| `STT_MODEL_NAME` | Модель Whisper (`medium` по умолчанию; `small` быстрее, но менее точна) |
| `STT_FORCE_CPU` | Принудительно CPU для STT |
| `STT_USE_VAD_FILTER` | Фильтр тишины faster-whisper (`true`) |
| `STT_LOW_CONFIDENCE_THRESHOLD` | Порог avg_logprob (−0.82); ниже — «Не расслышал» |
| `STT_RETRY_ON_LOW_CONFIDENCE` | Одна повторная запись при низкой уверенности |
| `TTS_VOICE` | Голос edge-tts (см. раздел «Голос и микрофон») |
| `TTS_RATE` | Скорость речи (`+8%` по умолчанию) |
| `DEBUG_TEXT_MODE` | Текстовый ввод без микрофона |

Полный список переменных — в `.env.example`.

## Голос и микрофон

### STT: модель и железо

| Режим | Когда использовать |
|---|---|
| `STT_MODEL_NAME=medium` | Рекомендуется: лучше распознаёт имена приложений |
| `STT_MODEL_NAME=small` | Слабый CPU, если medium тормозит |
| GPU (CUDA) | `STT_FORCE_CPU=false`, `STT_COMPUTE_TYPE=auto` → float16 |
| CPU | `STT_FORCE_CPU=true` → int8, без CUDA |

**Ошибка CUDA** (`cublas64_12.dll` not found):

```bash
pip install nvidia-cublas-cu12
```

или в `.env`: `STT_FORCE_CPU=true`.

### Микрофон

- Предпочтительно USB-микрофон, уровень записи Windows **70–90%**
- Отключите агрессивное шумоподавление Windows (Параметры → Звук → Свойства микрофона → доп. устройства)
- При старте в лог пишется sample rate и peak energy тестовой записи — если «слишком тихо», поднимите уровень

### TTS: голоса

**По умолчанию — Piper HD «Руслан»** (мужской русский, офлайн, ~60 МБ, без замедления и без «нейро-робота»).

1. `pip install piper-tts onnxruntime`
2. `python scripts/download_voice.py`
3. GUI: **Настройки → Голоса** → **«Джарвис HD — Руслан»** → **Прослушать** → **Сохранить**

| Движок | Описание |
|---|---|
| **Piper HD** | Мужской русский, локально, рекомендуется |
| **Edge-TTS** | Онлайн Neural (Дмитрий, Guy EN) |
| **SAPI** | Запасной робот Windows |

7 уникальных образов (без дублей): Руслан, Дмитрий, Денис, Ирина, Edge, Guy EN, SAPI.

`TTS_ENGINE=piper`, `PIPER_VOICE=ru_RU-ruslan-medium`. Fast mode — Piper HD.

### Чеклист регрессии (голосовые команды)

| # | Сказать | Ожидание |
|---|---|---|
| 1 | «Откроем WARP» | Cloudflare WARP, не Wand |
| 2 | «Крой Яндекс Музыку» | Yandex Music, не браузер |
| 3 | «Открой Yandex Music» | Music, не Wand |
| 4 | «Троек капкат» / «проект cupcut» | CapCut |
| 5 | «Открой V-моды» | WeMod |
| 6 | «Открой ванда» | Riot Client / Valorant |
| 7 | «Microsoft Store» | Store, не Edge |
| 8 | «Открой Spotify» | Spotify |
| 9 | Речь не идеально чётко | Реже «Не расслышал» |
| 10 | Любая фраза | TTS естественный темп, не «бурундук» |

## Основные команды

- **Windows:** «открой настройки», «открой калькулятор», «настройки wifi», «диспетчер задач»
- **Медиа:** «пауза», «следующий трек», «выключи звук»
- **Браузер:** «открой браузер»
- **Погода:** «какая погода»
- **Время:** «который час», «сколько времени»
- **Память:** «забудь меня» — очистка профиля (только локально)
- **Сценарий:** «начать работу» — пользовательский сценарий из `scenarios.json`

## Открытие программ

Скажите **«открой [название программы]»** — Discord, Steam, Telegram и любое приложение из меню «Пуск». Джарвис сканирует ярлыки при первом запуске и кэширует индекс в `data/apps_index.json` (обновление раз в 24 часа).

| Переменная | Описание |
|---|---|
| `APP_SCAN_ON_STARTUP` | Сканировать при старте (`true` по умолчанию) |
| `APP_SCAN_UWP` | Включать UWP-приложения через PowerShell (`true`) |
| `APP_INDEX_MAX_AGE_HOURS` | Срок жизни кэша в часах (24 по умолчанию) |
| `APP_FUZZY_MIN_SCORE` | Порог совпадения для одного слова (0.6) |
| `APP_FUZZY_MIN_SCORE_MULTIWORD` | Порог для многословных запросов (0.72) |

Системные команды (`открой настройки`, `открой калькулятор` и т.д.) по-прежнему работают через whitelist и имеют приоритет над сканером.

## Тесты

```bash
python -m pytest tests/
```

или

```bash
python tests/test_jarvis.py
```

## Иконки и сборка JArbis.exe

Иконки лежат в `jarvis/gui/assets/` (HUD-орб). Исходник: `source_icon.png`.

```bash
# Пересобрать PNG + ICO + трей из source_icon.png
python scripts/build_icons.py

# Собрать папку dist/JArbis/ с JArbis.exe (нужен PyInstaller)
pip install pyinstaller
python scripts/build_exe.py

# Zip для тестера / GitHub Release
python scripts/make_release_zip.py --version 1.0.0

# Проверить, что в exe попали vosk/piper/VAD и прочие критичные файлы
python scripts/verify_exe_bundle.py
```

После сборки скопируйте всю папку `dist/JArbis/` куда угодно или выложите `releases/JArbis-v*-win64.zip` в **GitHub Releases**. Рядом с `JArbis.exe` положите `.env` (из `.env.example`). Голос Piper скачивается при первом запуске или: `python scripts/download_voice.py`.

## GitHub и тестирование

Полная инструкция: **[docs/GITHUB.md](docs/GITHUB.md)** — репозиторий, Releases для тестера, Issues, без пересылки zip вручную.


## Структура проекта

```
JArbis/
  main.py              — точка входа: GUI (default) | --cli
  config.py            — конфигурация, gui_settings.json
  jarvis/
    core/
      assistant_engine.py  — голосовой цикл
      event_bus.py         — события GUI ↔ Engine
      app_state.py         — статусы ассистента
      stt_text_utils.py
    gui/
      app.py, theme.py, tray.py
      pages/             — dashboard, apps, scenarios, settings, logs
      widgets/           — status_orb
      assets/            — icon.ico, tray icons
    voice/               — stt, tts, wake_word
    commands/            — commands_module, user_apps_store, scenario_*
    ai/                  — llm, search, memory
  data/
    user_apps.json       — пользовательские .exe
    scenarios.json       — сценарии
    gui_settings.json    — настройки из GUI
    apps_index.json, jarvis.log
  tests/test_jarvis.py
  docs/screenshots/      — скриншоты GUI (опционально)
```

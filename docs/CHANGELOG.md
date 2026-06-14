# CHANGELOG — JArbis

Лог работ, выполненной в сессии разработки (Ask / Agent mode).  
Дата: **14 июня 2026**.

---

## Обзор

За сессию проект прошёл путь от базового GUI и CLI до полноценного HUD-интерфейса с выбором голосов, локальной озвучкой и исправлением UX-багов. Голосовой стек менялся несколько раз по обратной связи: **Silero → Piper HD** как основной офлайн-движок.

**Тесты на конец сессии:** 90 passed (`python -m pytest tests/test_jarvis.py -q`).

---

## 1. GUI — Luxify HUD

- Переработан интерфейс в стиле премиального тёмного HUD (~2200+ строк в `jarvis/gui/`).
- Добавлены: HUD-фон, top bar, dashboard с метриками и орбом, переработанные страницы настроек, ярлыков, сценариев, логов.
- Дизайн-система в `jarvis/gui/theme.py`: палитра, типографика, `panel_frame`, `accent_panel`, `ghost_button`, `badge_label`, `scroll_area`.

### Исправление падения при запуске

- **Ошибка:** `TclError: invalid color name "#00d4ff22"` — CustomTkinter не поддерживает `#RRGGBBAA`.
- **Решение:** функции `blend_colors()` и `soft_tint()` в `theme.py`; замена полупрозрачных цветов во всех бейджах, hover-состояниях и HUD-канвасе.

---

## 2. Точка входа `main.py`

- После Ctrl+Z файл откатился с GUI-лаунчера (~60 строк) на старый CLI-цикл (~328 строк).
- **Восстановлено:**
  - `python main.py` → GUI (`JarvisApp`)
  - `python main.py --cli` → `engine.run_cli_loop()`
- Тесты переведены на прямой вызов `assistant_engine.handle_post_llm` где нужно.

---

## 3. Голоса — первая итерация (Edge / SAPI / Silero)

### Настройки озвучки

- Панель в `jarvis/gui/pages/settings_page.py`:
  - Combobox Edge-TTS (русские голоса)
  - Combobox Windows SAPI
  - Кнопки «Прослушать», «Скачать», «Обновить Edge-голоса»
- `TTS_SAPI_VOICE` в `config.py`
- `reload_tts_settings()` в `tts_module.py`
- Тесты 73–77 (голоса, preview, reload).

### Silero TTS (первая версия)

- **Новые файлы:**
  - `jarvis/voice/silero_tts.py` — Silero v4_ru, дикторы eugene/aidar/baya/kseniya
  - `scripts/download_voice.py` — скачивание модели
- **Изменения:**
  - `config.py`: `TTS_ENGINE`, `SILERO_SPEAKER`, `SILERO_SPEED`, `VOICES_DIR`
  - `tts_module.py`: маршрутизация silero / edge / sapi; fast mode → Silero
  - `requirements.txt`: `torch`, `torchaudio`
  - `.env.example`, `README.md`

### Баг: скачивание Silero (`Authorization`)

- **Симптом:** `python scripts/download_voice.py` → `Не удалось загрузить Silero: 'Authorization'`.
- **Причина:** лимит GitHub API (403) + баг PyTorch 2.12 в `torch.hub`.
- **Решение:** прямая загрузка с `models.silero.ai` (~40 МБ), без `torch.hub` + GitHub API.
- Путь кэша: `data/voices/silero/model/v4_ru.pt`.

---

## 4. Голоса — расширение пресетов

- 15 готовых образов в `tts_module.VOICE_PRESETS` (Silero v3/v4/v5, Edge RU/EN, SAPI).
- Несколько моделей Silero: `v3_1_ru`, `v4_ru`, `v5_ru`.
- `list_edge_voices(locale)` — фильтр RU / EN / Все.
- `EDGE_TTS_LOCALE` в config.
- Тесты 78–87 (пресеты, локали, Silero models).

---

## 5. GUI выбора голосов — карточки

- **Новый виджет:** `jarvis/gui/widgets/voice_picker.py`
  - Hero-карточка текущего голоса + «Прослушать»
  - Фильтры: Все / Офлайн / RU / EN
  - Сетка кликабельных карточек (клик = выбор + превью)
  - Свёрнутая «Тонкая настройка» (Edge, SAPI, параметры)
- `settings_page.py` упрощён — делегирует в `VoicePickerPanel`.

---

## 6. Баг: прокрутка колесом мыши

- **Симптом:** при наведении на сетку голосов крутится вся страница настроек, а не внутренний список.
- **Причина:** вложенные `CTkScrollableFrame` с глобальным `bind_all("<MouseWheel>")`.
- **Решение:**
  - `jarvis/gui/scroll_utils.py` — `SmartScrollableFrame`, `register_nested_scroll()`
  - `theme.scroll_area()` использует умный скролл
  - Сетка голосов регистрируется как вложенная зона
- Тест 89: `test_scroll_nested_isolation`.

---

## 7. Голоса — Piper HD (финальная итерация)

По обратной связи: дубли пресетов, «под кайфом», заторможенность, низкое качество Silero.

### Проблемы Silero

| Симптом | Причина |
|--------|---------|
| Повторяющиеся голоса | 15 пресетов, много одинаковых Silero |
| «Под кайфом» | `SILERO_SPEED` 0.85–0.92 + pitch/rate |
| Заторможенность | `_apply_speed()` после синтеза |
| Низкое качество | лёгкая модель ~40 МБ |

### Решение: Piper HD

- **Новый модуль:** `jarvis/voice/piper_tts.py`
  - Голоса: `ru_RU-ruslan-medium` (дефолт), `dmitri`, `denis`, `irina`
  - Скачивание с HuggingFace (`rhasspy/piper-voices`), ~60 МБ на голос
  - Без torch, без замедления, rate/pitch `+0%`
- **Дефолт:** `TTS_ENGINE=piper`, `PIPER_VOICE=ru_RU-ruslan-medium`
- **Пресеты сокращены до 7 уникальных:** Джарвис HD, Дмитрий, Денис, Ирина, Edge Дмитрий, Guy EN, SAPI
- Fast mode → Piper HD (не Edge, не SAPI-робот)
- `scripts/download_voice.py` — качает Piper (ruslan + dmitri + denis)
- `requirements.txt`: `piper-tts`, `onnxruntime` (torch — опционально для legacy Silero)
- Миграция в `config.load_gui_settings()`: `silero` → `piper` автоматически
- Тесты 78–90 обновлены под Piper

### Зависимости

```bash
pip install piper-tts onnxruntime
python scripts/download_voice.py
```

---

## 8. Прочие улучшения сессии (из более ранних задач)

- **Микрофон:** `list_input_devices`, уровень на орб (`MIC_LEVEL`), combobox в настройках.
- **Логи:** auto-refresh на `logs_page`.
- **Трей:** клик по иконке открывает окно.
- **Тесты:** 90 unit-тестов в `tests/test_jarvis.py`.

---

## Структура голосового стека (текущая)

```
speak() → resolve_tts_engine()
    ├── piper   → piper_tts.speak()     [по умолчанию, HD офлайн]
    ├── edge    → speak_edge()          [онлайн Neural]
    ├── sapi    → _speak_sapi()         [запасной робот]
    └── silero  → speak_silero()        [legacy, нужен torch]
```

| Файл | Назначение |
|------|------------|
| `jarvis/voice/piper_tts.py` | Piper HD, основной офлайн |
| `jarvis/voice/tts_module.py` | Маршрутизация, Edge, SAPI, пресеты |
| `jarvis/voice/silero_tts.py` | Legacy Silero |
| `jarvis/gui/widgets/voice_picker.py` | UI выбора голоса |
| `jarvis/gui/scroll_utils.py` | Изоляция вложенного скролла |
| `scripts/download_voice.py` | Скачивание Piper HD |
| `data/voices/piper/` | Кэш ONNX-моделей |

---

## Что не вошло / отложено

- `confirm_utils.py` — тройное подтверждение удаления (планировалось, не внедрено)
- Расширенная панель скана на Apps (игры отдельно) — базовая версия
- Piper EN / Coqui XTTS / модели ~500 МБ — не найдено готового русского male HD такого размера в открытом доступе
- RVC / клонирование голоса — не реализовано

---

## Быстрый старт после обновления

```bash
pip install -r requirements.txt
python scripts/download_voice.py
python main.py
```

В GUI: **Настройки → Голоса озвучки → «◆ Джарвис HD — Руслан» → Прослушать → Сохранить**.

Если голос странный после старых настроек: **Сбросить по умолчанию** в настройках и выбрать пресет заново.

---

## 9. Иконки и сборка JArbis.exe

- Из HUD-арта пользователя (`source_icon.png`) сгенерированы: `icon.png`, `icon.ico`, `icon_512.png`, `tray_idle.png`, `tray_listen.png`, UI-иконки.
- Скрипт: `scripts/build_icons.py`.
- Сборка Windows: `scripts/build_exe.py` + `jarbis.spec` (PyInstaller, папка `dist/JArbis/`).
- `config.py`: при frozen-режиме `BASE_DIR` = папка с `JArbis.exe` (данные и `.env` рядом с exe).
- Runtime hook: `scripts/pyi_rth_jarbis.py`.
- README: раздел «Иконки и сборка JArbis.exe».

### Исправление закрытия exe после старта

- Причина: в PyInstaller-сборку не попадали данные Piper (`piper/espeak-ng-data`), из-за чего процесс мог завершаться во время первого синтеза приветствия без Python traceback.
- `jarbis.spec`: добавлен сбор data/dll для пакета `piper`.
- `jarbis.spec`: добавлен полный пакет `vosk` (`libvosk.dll` и зависимости) для wake-word.
- `jarbis.spec`: добавлен `faster_whisper/assets/silero_vad_v6.onnx` для STT после wake-word.
- `stt_module.py`: fallback STT без `vad_filter`, если VAD-модель недоступна.
- `wake_word_module.py`: wake-word использует тот же микрофон, что и STT (`STT_INPUT_DEVICE`).
- `scripts/exe_bundle_manifest.py` + `scripts/verify_exe_bundle.py`: автопроверка критичных файлов в `dist/JArbis/`.
- `jarbis.spec`: полный bundle для `jarvis`, `vosk`, `piper`, `faster_whisper`, `ctranslate2`, `onnxruntime`, `customtkinter`, `certifi`, `openwakeword`.
- `pyi_rth_jarbis.py`: DLL-пути для vosk/whisper/onnx в frozen exe.
- Проверка: `JArbis.exe` запущен на 45+ секунд, Vosk загружается, движок ждёт «Джарвис» без статуса `Ошибка`.

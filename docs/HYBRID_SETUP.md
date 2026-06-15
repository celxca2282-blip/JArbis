# Гибридный режим JArbis — чеклист для тестирования

Версия **1.0.0-beta.6** — polyglot: Python HUD + C++ core + опционально Node/Go/PowerShell.

## Структура на диске

Рекомендуемая раскладка (обе папки **рядом**):

```
C:\
├── JArbis\          ← этот репозиторий (Python HUD)
└── JArbisC++\       ← репозиторий движка (jarbis.exe)
```

## Быстрый старт (разработка)

### 1. Python (HUD)

```bat
cd C:\JArbis
install.bat
```

### 2. C++ (движок, опционально но рекомендуется)

```bat
cd C:\JArbisC++
scripts\setup.bat
```

Скачает Piper/Vosk, соберёт `build\Release\jarbis.exe`.

### 3. Sidecar'ы (опционально)

```bat
cd C:\JArbis\services
install_sidecars.bat
```

Нужны Node.js и/или Go. Без них — fallback на Python edge-tts и прямой OpenRouter.

### 4. Запуск

```bat
C:\JArbis\ZAPUSTIT.bat
```

или после `install.bat`:

```bat
C:\JArbis\ЗАПУСТИТЬ.bat
```

## Что проверить в логах (`data/jarvis.log`)

| Строка | Значение |
|--------|----------|
| `Гибрид: UI Python + движок C++` | C++ подключён ✅ |
| `Гибрид: fallback на Python` | Нет jarbis.exe — только Python |
| `Node Edge-TTS sidecar :17848` | Edge-TTS через Node ✅ |
| `Go LLM proxy sidecar :17849` | LLM через Go ✅ |
| `Sidecar'ы: Node=… Go=… PowerShell=…` | Статус при старте GUI |

## Чеклист тестирования

- [ ] Окно GUI открывается без белого экрана на «Обзор»
- [ ] Статус **«Готов»** при idle (не «Слушаю» на старте)
- [ ] Wake-word «Джарвис» → команда → ответ
- [ ] Кнопка **Стоп** не зависает
- [ ] Вкладка **Ярлыки** — список и «Обновить»
- [ ] **Настройки** — превью голоса, смена STT/TTS
- [ ] **Сценарии** — запуск preset
- [ ] Закрытие (X) → трей → клик открывает окно
- [ ] Без C++: всё работает (медленнее STT)

## Порты (localhost)

| Порт | Сервис |
|------|--------|
| 17847 | C++ core-server |
| 17848 | Node Edge-TTS |
| 17849 | Go LLM proxy |

## Переменные

| Переменная | По умолчанию | Назначение |
|------------|--------------|------------|
| `JARBIS_HYBRID=1` | включено | Python UI + C++ core |
| `JARBIS_HYBRID=0` | — | только Python |
| `JARBIS_CPP_EXE` | авто-поиск | путь к jarbis.exe |

Подробнее: [POLYGLOT.md](POLYGLOT.md)

## GitHub — два репозитория

| Репозиторий | Содержимое |
|-------------|------------|
| `JArbis` | Python HUD, sidecar'ы, гибридный клиент |
| `JArbisCpp` (или `JArbisC++`) | C++ движок, CMake, scripts |

**Не удаляйте JArbisC++** — без него гибрид деградирует в чистый Python.

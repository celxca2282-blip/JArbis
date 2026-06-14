# JArbis — публичная beta

Документ для **публикации открытой beta** на GitHub: что ожидать пользователям, как принимать feedback и как выкладывать релиз.

**Текущая версия:** см. `config.VERSION` (например `1.0.0-beta.1`).

---

## Статус проекта

| | |
|---|---|
| **Стадия** | Public Beta |
| **Платформа** | Windows 10/11 x64 |
| **Стабильность** | Экспериментальная — возможны баги, регрессии, медленный STT на CPU |
| **Поддержка** | Best effort — Issues на GitHub, без SLA |

---

## Что написать пользователям (кратко)

> **JArbis — beta.** Голосовой ассистент для Windows: wake-word, Whisper, Piper HD, управление ПК, опционально LLM через OpenRouter.  
> Проект в активной разработке: **баги ожидаемы**. Пожалуйста, оставляйте feedback через [Issues](https://github.com/celxca2282-blip/JArbis/issues).  
> Скачивайте **exe из [Releases](https://github.com/celxca2282-blip/JArbis/releases)**, не «Source code» zip с GitHub (там нет собранного приложения).

---

## Известные ограничения beta

- STT на CPU может **медленно слушать** или **ошибочно распознавать** имена приложений.
- Первый запуск **1–5 минут** — скачивание Piper, моделей Whisper/Vosk.
- Exe **~1.4 ГБ**; на слабых VM возможны тормоза и обрезанный GUI (масштаб Windows 100%).
- LLM **требует ключ** OpenRouter; без ключа — только локальные команды.
- Переключение аудиоустройств через голос **может не работать** на части конфигураций Windows.
- Нет macOS / Linux.

---

## Feedback: куда писать

| Тип | Куда |
|-----|------|
| Баг | Issues → **Сообщение о баге** |
| Идея / пожелание | Issues → **Идея или feedback** |
| Вопрос по установке | Issue или Discussions (если включите) |

**Обязательно в баге:** версия, Windows, шаги, `data/jarvis.log`. **Не прикладывать `.env`.**

---

## Чеклист публикации beta на GitHub

### Репозиторий (один раз)

- [ ] Репозиторий **Public**
- [ ] В описании репо: *«Voice assistant for Windows — public beta»*
- [ ] Topics: `voice-assistant`, `windows`, `python`, `whisper`, `beta`
- [ ] README с beta-баннером (см. корень репо)
- [ ] `LICENSE` (MIT — если исходники открыты)
- [ ] `.env` **не** в git (`git status` чистый от секретов)

### Релиз

```powershell
cd C:\JArbis
python -m pytest tests/
python scripts/build_exe.py
python scripts/prepare_tester_dist.py
python scripts/make_release_zip.py
python scripts/verify_exe_bundle.py
```

- [ ] Tag: `v1.0.0-beta.1` (совпадает с `config.VERSION`)
- [ ] Title: `JArbis v1.0.0-beta.1 — Public Beta (Windows x64)`
- [ ] Release notes: см. шаблон ниже
- [ ] Asset: `releases/JArbis-v1.0.0-beta.1-win64.zip`
- [ ] Отметить **Pre-release** на GitHub (рекомендуется для beta)

### Шаблон Release notes

```markdown
## JArbis Public Beta

⚠️ **Beta** — возможны баги. Feedback: https://github.com/celxca2282-blip/JArbis/issues

### Установка
1. Скачай **JArbis-v…-win64.zip** (не Source code)
2. Распакуй → `УСТАНОВИТЬ.bat` → `ЗАПУСТИТЬ.bat`
3. Python не нужен

### Требования
- Windows 10/11 x64, микрофон, интернет на первом запуске
- Опционально: `OPENAI_API_KEY` (OpenRouter) для ИИ-ответов

### Что нового
- …

### Известные проблемы
- …
```

---

## Открытый исходный код vs «скрытый»

### Рекомендация для JArbis beta: **оставить исходники открытыми (Public repo)**

| Открытый source (Public) | «Скрытый» (Private repo + только exe) |
|--------------------------|----------------------------------------|
| Доверие: пользователь видит, что делает микрофон и `.env` | Подозрение: «что внутри exe?» |
| Issues + PR от сообщества | Только баги «вслепую» |
| Совпадает с позицией «open source assistant» в README | Противоречит таблице «Open source: Да» |
| Стандарт GitHub: **код в repo, exe в Releases** | Exe всё равно можно декompile — «секретности» мало |
| Проще привлекать тестеров-разработчиков | Проще только если планируете коммерцию / закрытый форк |

**Практичная схема (рекомендуем):**

```
Public GitHub repo  →  исходники, Issues, CI, README
GitHub Releases     →  только zip с JArbis.exe (~1.4 ГБ)
```

Исходники **не обязаны** совпадать 1:1 с каждым exe (тег на коммите сборки — достаточно).

### Когда имеет смысл Private repo

- Коммерческая лицензия позже, код не хотите светить до v1.0 stable.
- В репо случайно остались секреты/личные данные — **сначала почистить**, не прятать.
- Exe-only продукт без community — тогда Issues всё равно нужны публично (отдельный repo «JArbis-releases» только с Releases — редкий и неудобный вариант).

### Компромисс

- **Public** repo + **Pre-release** + disclaimer в README.
- Крупные модели/голоса **не в git** (как сейчас) — только скачивание при первом запуске.
- Если позже захотите закрыть код — можно сделать Private **после** beta, но потеряете доверие ранних пользователей.

**Итог:** для публичной beta голосового ассистента с микрофоном — **открытый source + exe в Releases** — оптимальный вариант.

---

## Версионирование beta

- `1.0.0-beta.1` → первая публичная beta
- `1.0.0-beta.2` → исправления по feedback
- `1.0.0` → stable (когда будете готовы снять pre-release)

Версия в коде: `config.py` → `VERSION`.

---

## Ссылки

- [README](../README.md)
- [CONTRIBUTING](../CONTRIBUTING.md)
- [GITHUB.md](GITHUB.md)

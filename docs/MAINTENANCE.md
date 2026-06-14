# JArbis — режим сопровождения (maintenance)

Проект в **public beta**. Новые большие фичи — только по feedback.  
Твоя задача сейчас: **не потерять проект**, быстро чинить баги, иногда выпускать `beta.N`.

**Текущий релиз:** [v1.0.0-beta.1](https://github.com/celxca2282-blip/JArbis/releases/tag/v1.0.0-beta.1)

---

## Режим работы

| Делать | Не делать (пока нет Issues) |
|--------|-----------------------------|
| Отвечать в Issues за 1–3 дня | Пункты 2–4 из роадмапа (мониторинг, vision…) |
| Фиксить повторяющиеся баги | Переписывать архитектуру «на будущее» |
| Patch-release `1.0.0-beta.2` после 2–3 фиксов | Ежедневные коммиты «просто так» |
| Раз в 1–2 недели — быстрая проверка | Ждать, что feedback придёт сам |

---

## Раз в 1–2 недели (~5 минут)

```powershell
cd C:\JArbis
python scripts/check_maintainer.py
```

Скрипт проверит: секреты не в git, версия, опционально — Issues на GitHub.

Затем вручную:

1. [Issues](https://github.com/celxca2282-blip/JArbis/issues) — есть ли новые баги?
2. [Actions](https://github.com/celxca2282-blip/JArbis/actions) — CI зелёный на `main`?
3. Если тишина — можно **ничего не делать**. Это нормально.

---

## Когда выпускать `beta.2`

Выпускай patch-beta, если выполнено **хотя бы одно**:

- Исправлен **критичный** баг (не запускается, краш, микрофон мёртв)
- Накопилось **2–3** осмысленных фикса по Issues
- Тестер явно просит обновление

**Не обязательно** выпускать exe ради одной строчки в README.

### Чеклист patch-release

```powershell
cd C:\JArbis

# 1. Версия
#    config.py → VERSION = "1.0.0-beta.2"

# 2. Тесты
python -m pytest tests/ -q

# 3. Сборка (долго, ~10–30 мин)
python scripts/build_exe.py
python scripts/make_release_zip.py
python scripts/verify_exe_bundle.py

# 4. Git
git add .
git commit -m "fix: … (beta.2)"
git push origin main

# 5. GitHub Releases
#    Tag: v1.0.0-beta.2
#    Pre-release: да
#    Asset: releases/JArbis-v1.0.0-beta.2-win64.zip
#    Обновить ссылку «Скачать» в README (или тег в docs/MAINTENANCE.md)
```

---

## Как отвечать на Issue

1. **«Спасибо, воспроизведу»** — в течение 48 ч, даже если фикс позже.
2. Попроси `jarvis.log`, версию, Windows — шаблон уже в форме.
3. После фикса: «Закрыто в beta.2, скачай …» + ссылка на Release.
4. Feature request → label `enhancement`, ответ «в backlog, не в текущем спринте» — честно.

---

## Если feedback не приходит

Это **ожидаемо** для solo beta без рекламы. Один пост может изменить картину:

- Reddit: r/windows, r/LocalLLaMA (если про LLM)
- Habr: «голосовой ассистент для Windows, open source beta»
- Telegram-чаты про Python / Windows

Шаблон поста:

```
JArbis — open source голосовой ассистент для Windows (beta, MIT).
Wake-word, Whisper, Piper HD, управление ПК, опционально OpenRouter.
Exe ~1.4 GB, без Python. Ищу тестеров и багрепорты:
https://github.com/celxca2282-blip/JArbis/releases/tag/v1.0.0-beta.1
```

---

## Отложенный роадмап (не трогать без запроса)

См. [ROADMAP.md](ROADMAP.md) — мониторинг «почему лагает», проактивные уведомления, vision.

---

## Ссылки

| Что | URL |
|-----|-----|
| Скачать beta | https://github.com/celxca2282-blip/JArbis/releases/tag/v1.0.0-beta.1 |
| Issues | https://github.com/celxca2282-blip/JArbis/issues |
| CI | https://github.com/celxca2282-blip/JArbis/actions |
| Beta-док | [BETA.md](BETA.md) |
| GitHub how-to | [GITHUB.md](GITHUB.md) |

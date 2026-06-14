# GitHub: публичная beta

**Исходники** — в публичном репозитории (MIT). **Готовый exe** — только в **Releases** (~1.4 ГБ, не в git).

Пользователям: скачивайте **`JArbis-v…-win64.zip`**, не «Source code» на странице Release.

Подробный чеклист beta: **[BETA.md](BETA.md)**

---

## Роли

| Кто | Что делает |
|-----|------------|
| **Maintainer** | Код, CI, сборка exe, Pre-release на GitHub, ответы в Issues |
| **Пользователь / тестер** | Скачивает zip, тестирует, Issues (баг / feedback) |

Python и git **не нужны** для использования exe — только браузер и аккаунт GitHub (для Issues).
---

## Шаг 1. Установить Git (один раз, на твоём ПК)

1. Скачай [Git for Windows](https://git-scm.com/download/win)
2. Установи с настройками по умолчанию
3. Перезапусти терминал / Cursor
4. Проверка: `git --version`

Опционально — [GitHub CLI](https://cli.github.com/) (`gh`) для создания репо из консоли.

---

## Шаг 2. Создать репозиторий на GitHub

### Через сайт

1. [github.com/new](https://github.com/new)
2. Имя, например: `JArbis`
3. **Public** — для публичной beta (рекомендуется)
4. Без README / .gitignore (они уже в проекте)
5. Создать репозиторий

### Первый push с твоего ПК

```powershell
cd C:\JArbis

git init
git add .
git status
# Убедись: нет .env, data/gui_settings.json, dist/

git commit -m "Initial commit: JArbis voice assistant"
git branch -M main
git remote add origin https://github.com/ТВОЙ_ЛОГИН/JArbis.git
git push -u origin main
```

При первом push GitHub попросит войти (браузер или Personal Access Token).

---

## Шаг 3. Пригласить тестера

1. Репозиторий → **Settings** → **Collaborators** (или **Manage access**)
2. **Add people** → логин тестера на GitHub
3. Роль **Read** достаточно (скачивать Releases + писать Issues)

Если репо **публичное** — приглашение не обязательно, достаточно ссылки.

---

## Шаг 4. Выкладывать сборку для тестера (Releases)

**Не коммить** `dist/` в git — слишком тяжело. Используй **Releases**.

### Сборка и zip

```powershell
cd C:\JArbis
python scripts/build_exe.py
python scripts/make_release_zip.py
```

Появится: `releases/JArbis-v{VERSION}-win64.zip` (VERSION из `config.py`)

### Загрузка на GitHub (beta)

1. **Releases** → **Draft a new release**
2. Tag: `v1.0.0-beta.1` (как в `config.VERSION`)
3. Title: `JArbis v1.0.0-beta.1 — Public Beta (Windows x64)`
4. Описание: что изменилось + ссылка на Issues
5. **Pre-release** — включить
6. Прикрепить zip из `releases/`
7. **Publish release**
### Что писать тестеру

```
Скачай beta:
https://github.com/celxca2282-blip/JArbis/releases/tag/v1.0.0-beta.1

Файл: JArbis-v1.0.0-beta.1-win64.zip (не Source code)
Внутри — УСТАНОВИТЬ.bat, ЗАПУСТИТЬ.bat, КАК_ТЕСТИРОВАТЬ.txt

Баги и идеи — Issues на GitHub.
```

> Пока релиз **Pre-release**, ссылка `/releases/latest` не ведёт на beta — используй прямой tag URL.

---

## Режим сопровождения (ты ушёл в другой проект)

1. Раз в 1–2 недели: `python scripts/check_maintainer.py --online`
2. Отвечай в Issues; фикси только то, что реально мешает
3. Patch-release `beta.2` — см. **[MAINTENANCE.md](MAINTENANCE.md)**
4. Новые фичи — только из **[ROADMAP.md](ROADMAP.md)** и только по запросу

---

## Шаг 5. Тестер: как скачать и запустить

1. Открыть **Releases** → последний релиз
2. Скачать **JArbis-v….-win64.zip**
3. Распаковать
4. **`УСТАНОВИТЬ.bat`** — создаст `.env`
5. При необходимости вписать ключ в `.env`
6. **`ЗАПУСТИТЬ.bat`**
7. Баги: **Issues** → шаблон бага

---

## Шаг 6. Обратная связь (Issues)

Тестер создаёт Issue с:

- что делал / что ожидал
- скрин (по желанию)
- `data/jarvis.log` (вложить файл)
- **без** `.env`

Ты отвечаешь в Issue, фиксишь в коде, пушишь, выкладываешь новый Release.

---

## Рабочий цикл (кратко)

```
Ты: правки → pytest → build_exe → make_release_zip → Release на GitHub
Тестер: скачал zip → тест → Issue
Ты: фикс → новый тег v1.0.x → снова Release
```

---

## Если тестер хочет запуск из исходников (Python)

**В 1 клик:** `install.bat` в корне репозитория.

**Вручную:**

```powershell
git clone https://github.com/ТВОЙ_ЛОГИН/JArbis.git
cd JArbis
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# Вписать OPENAI_API_KEY в .env
python scripts/download_voice.py
python main.py
```

---

## Безопасность

- **Никогда** не коммить `.env` и `data/gui_settings.json` (там может быть API-ключ)
- Перед каждым `git add` смотри `git status`
- Если ключ утёк — смени на [openrouter.ai](https://openrouter.ai/)

---

## Лимиты GitHub

- Файл в Release: до **2 ГБ** (наш zip ~2 ГБ — впритык, при росте — убрать лишнее из bundle или LFS)
- LFS для exe обычно не нужен — только Releases

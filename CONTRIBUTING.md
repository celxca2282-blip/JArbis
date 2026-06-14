# Участие в JArbis (public beta)

Спасибо, что пробуете **beta** и помогаете улучшить проект.

> Статус: **public beta** — баги ожидаемы. Любой feedback ценен.

## Быстрый feedback (без Python)

1. Скачай **Pre-release** из [GitHub Releases](https://github.com/celxca2282-blip/JArbis/releases) (`JArbis-v…-win64.zip`).
2. Прочитай `КАК_ТЕСТИРОВАТЬ.txt` в архиве.
3. **Баг** → [Issues → Сообщение о баге](https://github.com/celxca2282-blip/JArbis/issues/new?template=bug_report.md)
4. **Идея / отзыв** → [Issues → Идея или feedback](https://github.com/celxca2282-blip/JArbis/issues/new?template=feature_request.md)
5. **Не прикладывай `.env`** — там API-ключ.

Подробнее: [docs/BETA.md](docs/BETA.md) · [docs/GITHUB.md](docs/GITHUB.md)

## Для разработчиков

**В 1 клик (Windows):** после `git clone` запустите **`install.bat`**.

**Вручную:**

```powershell
git clone https://github.com/celxca2282-blip/JArbis.git
cd JArbis
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements-dev.txt
copy .env.example .env
python scripts/download_voice.py
python main.py
```

### Тесты

```powershell
python -m pytest tests/
```

### Сборка exe для Release

```powershell
pip install pyinstaller
python scripts/build_exe.py
python scripts/make_release_zip.py
```

Версия берётся из `config.VERSION`. На GitHub отметьте **Pre-release** для beta.

### Правила

- Комментарии в коде — на русском.
- Не коммитьте `.env`, `data/gui_settings.json`, логи, `dist/`, модели голосов.
- Перед PR: `pytest` зелёный.
- Минимальный diff.

## Версионирование

- Beta: `1.0.0-beta.1`, `1.0.0-beta.2`, …
- Stable (позже): `1.0.0`

Версия в `config.VERSION`. Тег git: `v` + VERSION.

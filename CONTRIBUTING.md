# Участие в разработке JArbis

Спасибо, что помогаете улучшать проект.

## Для тестеров (без Python)

1. Скачайте последний **Release** на GitHub (zip для Windows, не Source code).
2. Прочитайте `КАК_ТЕСТИРОВАТЬ.txt` в архиве.
3. Баги — **Issues** → шаблон «Сообщение о баге».
4. Не прикладывайте `.env` и не публикуйте API-ключи.

Подробнее: [docs/GITHUB.md](docs/GITHUB.md)

## Для разработчиков

**Требования:** Python **3.11** или **3.12** (не 3.14), Windows 10/11.

```powershell
git clone https://github.com/ВАШ_ЛОГИН/JArbis.git
cd JArbis
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements-dev.txt
copy .env.example .env
# Вписать OPENAI_API_KEY (OpenRouter) — опционально для LLM
python scripts/download_voice.py
python main.py
```

Опционально Silero TTS (тяжёлый torch):

```powershell
pip install -r requirements-optional-silero.txt
```

### Тесты

```powershell
python -m pytest tests/
```

Сетевые тесты (если появятся): `python -m pytest tests/ -m network`

### Сборка exe

```powershell
pip install pyinstaller
python scripts/build_exe.py
python scripts/make_release_zip.py --version X.Y.Z
```

### Правила

- Комментарии в коде — на русском.
- Не коммитьте `.env`, `data/gui_settings.json`, логи, `dist/`, модели голосов.
- Перед PR: `pytest` зелёный.
- Минимальный diff: не рефакторить несвязанный код.

## Версионирование

Версия в `config.VERSION`. Для релиза: тег `vX.Y.Z` + zip в GitHub Releases.

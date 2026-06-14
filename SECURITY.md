# Безопасность

## Сообщить об уязвимости

Для **public beta** используй [GitHub Issues](https://github.com/celxca2282-blip/JArbis/issues/new) с меткой security или опиши проблему в баг-репорте **без публикации эксплойта**.

Не прикладывай `.env`, API-ключи и личные логи с секретами.

## Секреты

- **Никогда** не коммить `.env` — ключ OpenRouter и другие токены.
- `data/gui_settings.json` может содержать чувствительные настройки — в `.gitignore`.
- Если ключ утёк — отзови на [openrouter.ai](https://openrouter.ai/) и создай новый.

## Exe и микрофон

JArbis использует микрофон для wake-word и команд. Исходный код открыт (MIT) — можно проверить, что отправляется наружу:

- STT/TTS — локально (Whisper, Piper) или через выбранные вами сервисы (Edge-TTS, OpenRouter).
- Без вашего `OPENAI_API_KEY` LLM-запросы не выполняются.

Скачивайте exe только из [официальных Releases](https://github.com/celxca2282-blip/JArbis/releases).

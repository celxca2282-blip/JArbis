# JArbis — роадмап (отложено)

**Статус:** maintenance mode. Новые фичи — только если пользователи просят в Issues.

---

## В production (beta.1)

- Wake-word, STT (Whisper), TTS (Piper HD / Edge / SAPI)
- GUI + системный трей
- Локальные команды Windows, открытие приложений, сценарии
- Звуковая матрица (громкость приложений, mute, смена устройства)
- LLM через OpenRouter (опционально)
- Exe-сборка + public beta на GitHub

---

## Backlog (не начинать без feedback)

| # | Фича | Зачем | Триггер для старта |
|---|------|-------|-------------------|
| 2 | **System monitor** (psutil) — «почему лагает» | CPU/RAM/диск по процессам | 3+ Issues или явный запрос |
| 3 | **Proactive notifications** | Напоминания, алерты | Запрос + понятный UX |
| 4 | **Vision** (скрин / камера) | Сложно, тяжело для beta | После stable 1.0 |

---

## Версии (план)

| Версия | Содержание |
|--------|------------|
| `1.0.0-beta.1` | Первая public beta ✅ |
| `1.0.0-beta.N` | Bugfix по Issues |
| `1.0.0` | Stable: снять Pre-release, `/releases/latest` работает |

Версия в коде: `config.VERSION`.

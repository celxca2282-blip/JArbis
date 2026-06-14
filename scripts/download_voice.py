#!/usr/bin/env python3
"""
Скачивает Piper HD голос (русский мужской) в data/voices/piper/.
Запуск: python scripts/download_voice.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import config


def main() -> None:
    config.ensure_data_dirs()
    print("Скачивание Piper HD — мужской русский голос")
    print("Папка:", config.VOICES_DIR / "piper")
    print("Модель ~60 МБ, без torch, нормальная скорость и тембр.")

    try:
        from jarvis.voice import piper_tts

        if not piper_tts.piper_available():
            print("Ошибка: pip install piper-tts onnxruntime")
            sys.exit(1)

        voices = [
            config.PIPER_VOICE or "ru_RU-ruslan-medium",
            "ru_RU-dmitri-medium",
            "ru_RU-denis-medium",
        ]
        ok_any = False
        for vid in voices:
            print(f"\n--- {piper_tts.voice_label(vid)} ---")
            if piper_tts.download_model(vid):
                ok_any = True

        if ok_any and piper_tts.load_model(voice_id=config.PIPER_VOICE):
            print("\nГотово! Piper HD загружен.")
            print("В GUI: Настройки - Голоса - «Джарвис HD — Руслан» - Прослушать - Сохранить")
        else:
            print("Не удалось загрузить модель. Проверьте интернет.")
            sys.exit(1)
    except Exception as e:
        print(f"Ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

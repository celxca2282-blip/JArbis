"""
Список критичных файлов/папок в dist/JArbis после PyInstaller.
Если чего-то нет — exe может падать без понятной ошибки.
"""

from __future__ import annotations

from pathlib import Path

# Пути относительно dist/JArbis/
REQUIRED_DIRS = (
    "_internal/jarvis/gui/assets",
    "_internal/piper/espeak-ng-data",
    "_internal/vosk",
    "_internal/faster_whisper/assets",
    "_internal/customtkinter/assets",
    "_internal/ctranslate2",
    "_internal/onnxruntime/capi",
    "_internal/certifi",
)

REQUIRED_FILES = (
    "JArbis.exe",
    "_internal/jarvis/gui/assets/icon.ico",
    "_internal/vosk/libvosk.dll",
    "_internal/faster_whisper/assets/silero_vad_v6.onnx",
    "_internal/piper/espeakbridge.pyd",
    "_internal/ctranslate2/ctranslate2.dll",
    "_internal/onnxruntime/capi/onnxruntime.dll",
    "_internal/certifi/cacert.pem",
)


def verify_dist(dist_dir: Path) -> list[str]:
    """Возвращает список отсутствующих путей (пустой список = всё ок)."""
    missing: list[str] = []
    for rel in REQUIRED_DIRS:
        path = dist_dir / rel
        if not path.is_dir():
            missing.append(rel)
    for rel in REQUIRED_FILES:
        path = dist_dir / rel
        if not path.is_file():
            missing.append(rel)
    return missing

# piper_tts.py
"""
Локальная озвучка Piper HD — натуральный мужской русский голос (ONNX ~60 МБ).
Без замедления и без искажения pitch — чистый синтез.
"""

import logging
import re
import urllib.request
from pathlib import Path
from typing import Callable

import numpy as np

import config

logger = logging.getLogger(__name__)

# Голоса Piper: id -> (подпись, путь на HuggingFace, имя файла без расширения)
PIPER_VOICES: dict[str, tuple[str, str, str]] = {
    "ru_RU-ruslan-medium": (
        "Руслан — мужской HD (рекомендуется)",
        "ru/ru_RU/ruslan/medium",
        "ru_RU-ruslan-medium",
    ),
    "ru_RU-dmitri-medium": (
        "Дмитрий — мужской, чёткий",
        "ru/ru_RU/dmitri/medium",
        "ru_RU-dmitri-medium",
    ),
    "ru_RU-denis-medium": (
        "Денис — мужской, спокойный",
        "ru/ru_RU/denis/medium",
        "ru_RU-denis-medium",
    ),
    "ru_RU-irina-medium": (
        "Ирина — женский",
        "ru/ru_RU/irina/medium",
        "ru_RU-irina-medium",
    ),
}

PIPER_VOICE_OPTIONS: list[tuple[str, str]] = [(vid, meta[0]) for vid, meta in PIPER_VOICES.items()]

HF_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main"

_voice = None
_loaded_voice_id: str | None = None
_speech_channel = None


def piper_available() -> bool:
    """Проверяет, установлен ли piper-tts."""
    try:
        from piper import PiperVoice  # noqa: F401

        return True
    except ImportError:
        return False


def model_ready() -> bool:
    """Модель уже в памяти."""
    return _voice is not None


def resolve_voice_id(voice_id: str | None = None) -> str:
    """Возвращает id голоса Piper из config."""
    vid = (voice_id or getattr(config, "PIPER_VOICE", "ru_RU-ruslan-medium") or "ru_RU-ruslan-medium").strip()
    if vid not in PIPER_VOICES:
        vid = "ru_RU-ruslan-medium"
    return vid


def voice_dir(voice_id: str | None = None) -> Path:
    """Папка с файлами конкретного голоса."""
    vid = resolve_voice_id(voice_id)
    return config.VOICES_DIR / "piper" / vid


def model_paths(voice_id: str | None = None) -> tuple[Path, Path]:
    """Пути к .onnx и .onnx.json."""
    vid = resolve_voice_id(voice_id)
    _label, _hf, fname = PIPER_VOICES[vid]
    folder = voice_dir(vid)
    return folder / f"{fname}.onnx", folder / f"{fname}.onnx.json"


def model_on_disk(voice_id: str | None = None) -> bool:
    """Файлы модели уже скачаны."""
    onnx_path, json_path = model_paths(voice_id)
    return onnx_path.is_file() and json_path.is_file() and onnx_path.stat().st_size > 1_000_000


def voice_label(voice_id: str | None = None) -> str:
    """Подпись для GUI."""
    vid = resolve_voice_id(voice_id)
    return PIPER_VOICES.get(vid, (vid, "", ""))[0]


# Скачивает onnx + json с HuggingFace
def download_model(voice_id: str | None = None, force: bool = False) -> bool:
    vid = resolve_voice_id(voice_id)
    if not force and model_on_disk(vid):
        return True

    if vid not in PIPER_VOICES:
        return False

    _label, hf_path, fname = PIPER_VOICES[vid]
    folder = voice_dir(vid)
    folder.mkdir(parents=True, exist_ok=True)
    onnx_path = folder / f"{fname}.onnx"
    json_path = folder / f"{fname}.onnx.json"

    try:
        for suffix, dest in ((".onnx", onnx_path), (".onnx.json", json_path)):
            url = f"{HF_BASE}/{hf_path}/{fname}{suffix}"
            logger.info("Скачивание Piper: %s", dest.name)
            urllib.request.urlretrieve(url, dest)
            if not dest.is_file() or dest.stat().st_size < 1024:
                raise RuntimeError(f"Пустой файл: {dest.name}")
        logger.info("Piper голос готов: %s", vid)
        return True
    except Exception as e:
        logger.error("Не удалось скачать Piper (%s): %s", vid, e)
        return False


# Загружает PiperVoice в память
def load_model(force: bool = False, voice_id: str | None = None) -> bool:
    global _voice, _loaded_voice_id
    vid = resolve_voice_id(voice_id)
    if _voice is not None and not force and _loaded_voice_id == vid:
        return True

    try:
        from piper import PiperVoice

        if not download_model(vid, force=force):
            return False

        onnx_path, json_path = model_paths(vid)
        _voice = PiperVoice.load(str(onnx_path), config_path=str(json_path))
        _loaded_voice_id = vid
        logger.info("Piper TTS готов (%s)", vid)
        return True
    except Exception as e:
        logger.error("Не удалось загрузить Piper: %s", e)
        _voice = None
        _loaded_voice_id = None
        return False


def unload_model() -> None:
    """Сбрасывает кэш после смены настроек."""
    global _voice, _loaded_voice_id
    _voice = None
    _loaded_voice_id = None


# Готовит текст для синтеза
def _prepare_text(text: str) -> str:
    prepared = text.strip()
    if not prepared:
        return prepared
    prepared = re.sub(r"[^\w\s\d.,!:?ёЁа-яА-Я-]", "", prepared, flags=re.UNICODE)
    if not re.search(r"[.!?…]$", prepared):
        prepared += "."
    return prepared


# Синтезирует аудио
def synthesize(text: str, voice_id: str | None = None) -> tuple[np.ndarray, int] | None:
    prepared = _prepare_text(text)
    if not prepared:
        return None
    if not load_model(voice_id=voice_id):
        return None

    try:
        chunks = list(_voice.synthesize(prepared))
        if not chunks:
            return None
        parts = []
        sample_rate = int(_voice.config.sample_rate)
        for chunk in chunks:
            raw = np.frombuffer(chunk.audio_int16_bytes, dtype=np.int16).astype(np.float32)
            parts.append(raw / 32768.0)
        audio = np.concatenate(parts) if len(parts) > 1 else parts[0]
        return audio.astype(np.float32), sample_rate
    except Exception as e:
        logger.error("Ошибка синтеза Piper: %s", e)
        return None


# Воспроизводит аудио через pygame
def _play_audio(
    audio: np.ndarray,
    sample_rate: int,
    cancel_check: Callable[[], bool] | None = None,
) -> None:
    global _speech_channel
    import pygame

    from jarvis.voice.tts_module import MIXER_SAMPLE_RATE, _init_mixer

    _init_mixer()
    audio = np.clip(audio, -1.0, 1.0)

    if sample_rate != MIXER_SAMPLE_RATE:
        new_len = max(1, int(len(audio) * MIXER_SAMPLE_RATE / sample_rate))
        audio = np.interp(
            np.linspace(0, len(audio) - 1, new_len),
            np.arange(len(audio)),
            audio,
        ).astype(np.float32)

    stereo = np.column_stack((audio, audio))
    pcm = (stereo * 32767).astype(np.int16).tobytes()
    sound = pygame.mixer.Sound(buffer=pcm)

    if _speech_channel is None:
        _speech_channel = pygame.mixer.Channel(2)

    if pygame.mixer.music.get_busy():
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass

    _speech_channel.play(sound)
    while _speech_channel.get_busy():
        if cancel_check and cancel_check():
            _speech_channel.stop()
            return
        pygame.time.wait(10)


def stop_playback() -> None:
    """Останавливает озвучку Piper."""
    global _speech_channel
    try:
        if _speech_channel and _speech_channel.get_busy():
            _speech_channel.stop()
    except Exception:
        pass


# Озвучивает текст
def speak(
    text: str,
    *,
    voice_id: str | None = None,
    cancel_check: Callable[[], bool] | None = None,
) -> bool:
    try:
        result = synthesize(text, voice_id=voice_id)
        if result is None:
            return False
        audio, sample_rate = result
        _play_audio(audio, sample_rate, cancel_check=cancel_check)
        return True
    except Exception as e:
        logger.error("Ошибка озвучки Piper: %s", e)
        return False

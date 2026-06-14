# silero_tts.py
"""
Локальная озвучка через Silero TTS (русский v3/v4/v5).
Профиль «Джарвис RU» — спокойный мужской голос без интернета.
"""

import logging
import re
from typing import Callable

import numpy as np

import config

logger = logging.getLogger(__name__)

# Доступные дикторы Silero (v3/v4/v5 ru)
SILERO_SPEAKERS: list[tuple[str, str]] = [
    ("eugene", "Евгений — мужской, спокойный"),
    ("aidar", "Айдар — мужской, энергичный"),
    ("baya", "Бая — женский, мягкий"),
    ("kseniya", "Ксения — женский, деловой"),
    ("xenia", "Ксения v5 — женский, выразительный"),
    ("random", "Случайный диктор"),
]

# Модели Silero: id -> (файл, url, подпись)
SILERO_MODELS: dict[str, tuple[str, str, str]] = {
    "v4_ru": (
        "v4_ru.pt",
        "https://models.silero.ai/models/tts/ru/v4_ru.pt",
        "v4 — рекомендуется",
    ),
    "v5_ru": (
        "v5_ru.pt",
        "https://models.silero.ai/models/tts/ru/v5_ru.pt",
        "v5 — новее, выразительнее",
    ),
    "v3_1_ru": (
        "v3_1_ru.pt",
        "https://models.silero.ai/models/tts/ru/v3_1_ru.pt",
        "v3 — классика",
    ),
}

SILERO_MODEL_OPTIONS: list[tuple[str, str]] = [
    (mid, f"{mid.replace('_', ' ')} — {meta[2]}") for mid, meta in SILERO_MODELS.items()
]

SILERO_SAMPLE_RATE = 48000

_model = None
_torch = None
_speech_channel = None
_loaded_model_id: str | None = None


def torch_available() -> bool:
    """Проверяет, установлен ли PyTorch."""
    try:
        import torch  # noqa: F401

        return True
    except ImportError:
        return False


def model_ready() -> bool:
    """Модель уже загружена в память."""
    return _model is not None


def can_speak() -> bool:
    """Можно ли использовать Silero (torch установлен)."""
    return torch_available()


def resolve_model_id(model_id: str | None = None) -> str:
    """Возвращает id модели Silero из config или аргумента."""
    mid = (model_id or getattr(config, "SILERO_MODEL", "v4_ru") or "v4_ru").strip()
    if mid not in SILERO_MODELS:
        mid = "v4_ru"
    return mid


def model_label(model_id: str | None = None) -> str:
    """Подпись модели для GUI."""
    mid = resolve_model_id(model_id)
    for oid, label in SILERO_MODEL_OPTIONS:
        if oid == mid:
            return label
    return mid


# Подготавливает текст для Silero (кириллица + базовая пунктуация)
def _prepare_text(text: str) -> str:
    prepared = text.strip()
    if not prepared:
        return prepared
    prepared = re.sub(r"[^\w\s\d.,!:?ёЁа-яА-Я-]", "", prepared, flags=re.UNICODE)
    if not re.search(r"[.!?…]$", prepared):
        prepared += "."
    return prepared


# Загружает модель Silero напрямую с models.silero.ai (без torch.hub + GitHub API)
def load_model(force: bool = False, model_id: str | None = None) -> bool:
    global _model, _torch, _loaded_model_id
    mid = resolve_model_id(model_id)
    if _model is not None and not force and _loaded_model_id == mid:
        return True

    try:
        import torch
        from torch import package

        _torch = torch
        filename, url, _desc = SILERO_MODELS[mid]
        model_dir = config.VOICES_DIR / "silero" / "model"
        model_dir.mkdir(parents=True, exist_ok=True)
        model_path = model_dir / filename

        if force or not model_path.is_file():
            logger.info("Скачивание Silero TTS (%s) с models.silero.ai…", mid)
            torch.hub.download_url_to_file(url, str(model_path), progress=True)
        else:
            logger.info("Загрузка Silero TTS (%s) из кэша…", mid)

        imp = package.PackageImporter(str(model_path))
        model = imp.load_pickle("tts_models", "model")
        device = torch.device("cpu")
        model.to(device)
        _model = model
        _loaded_model_id = mid
        logger.info("Silero TTS готов (%s)", mid)
        return True
    except Exception as e:
        logger.error("Не удалось загрузить Silero: %s", e)
        _model = None
        _loaded_model_id = None
        return False


def unload_model() -> None:
    """Сбрасывает кэш модели (после смены настроек)."""
    global _model, _loaded_model_id
    _model = None
    _loaded_model_id = None


# Замедляет аудио для более «дворецкого» темпа
def _apply_speed(audio: np.ndarray, speed: float) -> np.ndarray:
    if speed <= 0 or abs(speed - 1.0) < 0.02:
        return audio.astype(np.float32)
    new_len = max(1, int(len(audio) / speed))
    indices = np.linspace(0, len(audio) - 1, new_len)
    return np.interp(indices, np.arange(len(audio)), audio).astype(np.float32)


# Синтезирует аудио в numpy-массив
def synthesize(
    text: str,
    speaker: str | None = None,
    speed: float | None = None,
    model_id: str | None = None,
) -> tuple[np.ndarray, int] | None:
    prepared = _prepare_text(text)
    if not prepared:
        return None
    if not load_model(model_id=model_id):
        return None

    spk = (speaker or config.SILERO_SPEAKER or "eugene").strip()
    spd = speed if speed is not None else float(config.SILERO_SPEED)

    try:
        audio = _model.apply_tts(text=prepared, speaker=spk, sample_rate=SILERO_SAMPLE_RATE)
        if hasattr(audio, "numpy"):
            audio_np = audio.numpy().astype(np.float32)
        else:
            audio_np = np.asarray(audio, dtype=np.float32)
        audio_np = _apply_speed(audio_np, spd)
        return audio_np, SILERO_SAMPLE_RATE
    except Exception as e:
        logger.error("Ошибка синтеза Silero: %s", e)
        return None


# Воспроизводит numpy-аудио через pygame
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
        )

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
    """Останавливает текущую озвучку Silero."""
    global _speech_channel
    try:
        if _speech_channel and _speech_channel.get_busy():
            _speech_channel.stop()
    except Exception:
        pass


# Озвучивает текст через Silero
def speak(
    text: str,
    *,
    speaker: str | None = None,
    speed: float | None = None,
    model_id: str | None = None,
    cancel_check: Callable[[], bool] | None = None,
) -> bool:
    try:
        result = synthesize(text, speaker=speaker, speed=speed, model_id=model_id)
        if result is None:
            return False
        audio, sample_rate = result
        _play_audio(audio, sample_rate, cancel_check=cancel_check)
        return True
    except Exception as e:
        logger.error("Ошибка озвучки Silero: %s", e)
        return False

# wake_word_module.py
"""
Модуль голосовой активации с поддержкой нескольких движков (vosk, openwakeword).
Движок и кодовое слово настраиваются через переменные окружения.
"""

import json
import logging
import re
import threading
from typing import Any, Optional

import numpy as np
import pyaudio

import config

logger = logging.getLogger(__name__)

# Параметры аудиопотока
SAMPLE_RATE = 16000
CHANNELS = 1

# openWakeWord
OWW_CHUNK_SIZE = 1280
OWW_DETECTION_THRESHOLD = 0.5

# Vosk
VOSK_CHUNK_SIZE = 4000

# Прерывание ожидания wake-word (для теста микрофона из GUI)
_wake_stop_event = threading.Event()


def request_wake_stop() -> None:
    """Просит прервать текущее ожидание кодового слова."""
    _wake_stop_event.set()


def clear_wake_stop() -> None:
    """Сбрасывает флаг прерывания wake-word."""
    _wake_stop_event.clear()


def is_wake_stop_requested() -> bool:
    return _wake_stop_event.is_set()

# Значения по умолчанию для каждого движка
_DEFAULT_WAKE_WORD_NAMES = {
    "vosk": "джарвис",
    "openwakeword": "jarvis",
}

# Варианты произношения wake-word «Джарвис» (ошибки STT/Vosk)
_JARVIS_WAKE_ALIASES = (
    "джарвис",
    "jarvis",
    "jarwis",
    "jarves",
    "charvis",
    "джарvis",
    "джарвис",
)

# Кэш модели openWakeWord (загружается лениво — не тянет scipy при движке vosk)
_wakeword_model: Optional[Any] = None
_vosk_model = None


# Возвращает выбранный движок голосовой активации
def get_wake_word_engine() -> str:
    return config.WAKE_WORD_ENGINE


# Возвращает кодовое слово для текущего движка
def get_wake_word_name() -> str:
    engine = get_wake_word_engine()
    custom_name = config.WAKE_WORD_NAME
    if custom_name:
        return custom_name
    return _DEFAULT_WAKE_WORD_NAMES.get(engine, "джарвис")


# Возвращает отображаемое имя wake-word с заглавной буквы
def get_wake_word_display_name() -> str:
    name = get_wake_word_name()
    if not name:
        return name
    return name[:1].upper() + name[1:]


# Возвращает сообщение для режима ожидания (для логов и интерфейса)
def get_wait_mode_message() -> str:
    return f'[Режим ожидания: скажите "{get_wake_word_display_name()}"]'


# Нормализует текст для сравнения кодового слова
def _normalize_text(text: str) -> str:
    normalized = text.lower().strip()
    normalized = normalized.replace("ё", "е")
    normalized = re.sub(r"[^\w\s]", "", normalized)
    return normalized


# Возвращает набор допустимых форм wake-word для сравнения
def _get_wake_word_aliases(wake_word_name: str) -> tuple[str, ...]:
    normalized = _normalize_text(wake_word_name)
    if normalized in {"джарвис", "jarvis"}:
        return _JARVIS_WAKE_ALIASES
    return (normalized,)


# Проверяет, совпадает ли слово с wake-word или его типичной ошибкой STT
def _word_is_wake_word(word: str, aliases: tuple[str, ...]) -> bool:
    normalized_word = _normalize_text(word)
    if normalized_word in aliases:
        return True

    if any(alias in {"джарвис", "jarvis"} for alias in aliases):
        return normalized_word.startswith("джарв") or normalized_word.startswith("jarv")

    return False


# Проверяет, содержит ли распознанный текст кодовое слово (строго для Vosk)
def _contains_wake_word(text: str, wake_word_name: str) -> bool:
    if not text:
        return False

    normalized_text = _normalize_text(text)
    aliases = _get_wake_word_aliases(wake_word_name)

    if not normalized_text:
        return False

    words = normalized_text.split()
    word_count = len(words)

    # Единственное слово — только wake-word
    if word_count == 1:
        return _word_is_wake_word(words[0], aliases)

    # Wake-word должен быть первым словом
    if _word_is_wake_word(words[0], aliases):
        return True

    # Длинная фраза без wake-word в начале — не активируем
    if word_count > 6:
        return False

    return False


# Публичная обёртка для тестов и отладки wake-word
def contains_wake_word(text: str, wake_word_name: str | None = None) -> bool:
    wake_name = wake_word_name or get_wake_word_name()
    return _contains_wake_word(text, wake_name)


# Скачивает официальные модели openWakeWord, если их ещё нет на диске
def _ensure_openwakeword_models() -> None:
    try:
        import openwakeword

        logger.info("Проверка и загрузка официальных голосовых моделей openWakeWord...")
        openwakeword.utils.download_models()
        logger.info("Все необходимые компоненты wake word успешно загружены")
    except Exception as e:
        logger.error("Не удалось скачать модели openWakeWord: %s", e)
        raise


# Загружает и возвращает модель openWakeWord
def _get_openwakeword_model(wake_word_name: str) -> Any:
    global _wakeword_model
    if _wakeword_model is None:
        try:
            from openwakeword.model import Model

            _ensure_openwakeword_models()
            logger.info("Инициализация модели openWakeWord (ONNX, слово: %s)...", wake_word_name)
            _wakeword_model = Model(
                wakeword_models=[wake_word_name],
                inference_framework="onnx",
            )
            logger.info("Модель openWakeWord готова")
        except Exception as e:
            logger.error("Не удалось загрузить модель openWakeWord: %s", e)
            raise
    return _wakeword_model


# Загружает русскую модель Vosk
def _get_vosk_model():
    global _vosk_model
    if _vosk_model is None:
        try:
            import vosk

            logger.info("Загрузка русской модели Vosk...")
            _vosk_model = vosk.Model(lang="ru")
            logger.info("Модель Vosk готова")
        except Exception as e:
            logger.error("Не удалось загрузить модель Vosk: %s", e)
            raise
    return _vosk_model


# Открывает аудиопоток PyAudio с учётом индекса микрофона
def _open_audio_stream(
    audio: pyaudio.PyAudio,
    chunk_size: int,
    microphone_index: Optional[int] = None,
):
    stream_kwargs = {
        "format": pyaudio.paInt16,
        "channels": CHANNELS,
        "rate": SAMPLE_RATE,
        "input": True,
        "frames_per_buffer": chunk_size,
    }
    if microphone_index is not None:
        stream_kwargs["input_device_index"] = microphone_index

    return audio.open(**stream_kwargs)


# Закрывает аудиопоток PyAudio
def _close_audio_stream(stream, audio: pyaudio.PyAudio) -> None:
    if stream is not None:
        try:
            stream.stop_stream()
            stream.close()
            logger.info("Аудиопоток PyAudio закрыт")
        except Exception as e:
            logger.warning("Ошибка закрытия аудиопотока: %s", e)

    try:
        audio.terminate()
    except Exception as e:
        logger.warning("Ошибка завершения PyAudio: %s", e)


# Ожидает кодовое слово через openWakeWord (ONNX)
def _wait_openwakeword(microphone_index: Optional[int] = None) -> bool:
    wake_word_name = get_wake_word_name()
    wakeword_model = _get_openwakeword_model(wake_word_name)
    audio = pyaudio.PyAudio()
    stream = None

    try:
        logger.info(
            "openWakeWord: запуск PyAudio (%s Гц, чанк %s, микрофон: %s)",
            SAMPLE_RATE,
            OWW_CHUNK_SIZE,
            microphone_index if microphone_index is not None else "по умолчанию",
        )
        stream = _open_audio_stream(audio, OWW_CHUNK_SIZE, microphone_index)
        logger.info("openWakeWord: ожидание кодового слова «%s»", wake_word_name)

        while True:
            if _wake_stop_event.is_set():
                logger.info("openWakeWord: ожидание прервано (тест микрофона)")
                return False

            try:
                raw_chunk = stream.read(OWW_CHUNK_SIZE, exception_on_overflow=False)
                chunk = np.frombuffer(raw_chunk, dtype=np.int16)
                prediction = wakeword_model.predict(chunk)
                score = prediction.get(wake_word_name, 0)

                if score > OWW_DETECTION_THRESHOLD:
                    logger.info(
                        "openWakeWord: кодовое слово «%s» обнаружено (score: %.2f)",
                        wake_word_name,
                        score,
                    )
                    return True

            except Exception as e:
                logger.error("openWakeWord: ошибка чтения аудио: %s", e)
                return False

    except Exception as e:
        logger.error("openWakeWord: не удалось открыть микрофон: %s", e)
        return False

    finally:
        _close_audio_stream(stream, audio)


# Ожидает кодовое слово через Vosk (русская модель)
def _wait_vosk(microphone_index: Optional[int] = None) -> bool:
    try:
        import vosk
    except ImportError as e:
        logger.error("Модуль vosk не установлен: %s", e)
        return False

    wake_word_name = get_wake_word_name()
    model = _get_vosk_model()
    recognizer = vosk.KaldiRecognizer(model, SAMPLE_RATE)
    recognizer.SetWords(True)

    audio = pyaudio.PyAudio()
    stream = None

    try:
        logger.info(
            "Vosk: запуск PyAudio (%s Гц, чанк %s, микрофон: %s)",
            SAMPLE_RATE,
            VOSK_CHUNK_SIZE,
            microphone_index if microphone_index is not None else "по умолчанию",
        )
        stream = _open_audio_stream(audio, VOSK_CHUNK_SIZE, microphone_index)
        logger.info("Vosk: ожидание кодового слова «%s»", wake_word_name)

        while True:
            if _wake_stop_event.is_set():
                logger.info("Vosk: ожидание прервано (тест микрофона)")
                return False

            try:
                raw_chunk = stream.read(VOSK_CHUNK_SIZE, exception_on_overflow=False)

                if recognizer.AcceptWaveform(raw_chunk):
                    result = json.loads(recognizer.Result())
                    text = result.get("text", "")
                else:
                    result = json.loads(recognizer.PartialResult())
                    text = result.get("partial", "")

                if _contains_wake_word(text, wake_word_name):
                    logger.info("Vosk: кодовое слово «%s» обнаружено в тексте: %s", wake_word_name, text)
                    return True

            except Exception as e:
                logger.error("Vosk: ошибка чтения или распознавания аудио: %s", e)
                return False

    except Exception as e:
        logger.error("Vosk: не удалось открыть микрофон: %s", e)
        return False

    finally:
        _close_audio_stream(stream, audio)


# Возвращает индекс микрофона из настроек (тот же, что для STT)
def _resolve_microphone_index(microphone_index: Optional[int] = None) -> Optional[int]:
    if microphone_index is not None:
        return microphone_index
    try:
        from jarvis.voice import stt_module

        return stt_module._get_input_device()
    except Exception:
        return None


# Точка входа: ждёт кодовое слово выбранным движком
def wait_for_jarvis(microphone_index: Optional[int] = None) -> bool:
    engine = get_wake_word_engine()
    wake_word_name = get_wake_word_name()
    mic_index = _resolve_microphone_index(microphone_index)

    logger.info("Активирован движок голосовой активации: %s (слово: «%s»)", engine, wake_word_name)

    if engine == "vosk":
        return _wait_vosk(mic_index)

    if engine == "openwakeword":
        return _wait_openwakeword(mic_index)

    logger.error("Неизвестный движок WAKE_WORD_ENGINE: %s", engine)
    return False

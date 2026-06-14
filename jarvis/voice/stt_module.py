import os
import sys

if sys.platform == "win32":
    try:
        import nvidia.cublas
        import nvidia.cudnn

        cublas_file = getattr(nvidia.cublas, "__file__", None)
        cudnn_file = getattr(nvidia.cudnn, "__file__", None)

        possible_bin_paths: list[str] = []
        if cublas_file:
            cublas_base = os.path.dirname(cublas_file)
            possible_bin_paths.extend([
                os.path.join(cublas_base, "bin"),
                os.path.abspath(os.path.join(cublas_base, "..", "bin")),
            ])
        if cudnn_file:
            cudnn_base = os.path.dirname(cudnn_file)
            possible_bin_paths.extend([
                os.path.join(cudnn_base, "bin"),
                os.path.abspath(os.path.join(cudnn_base, "..", "bin")),
            ])

        for path in possible_bin_paths:
            if path and os.path.exists(path):
                os.add_dll_directory(path)
    except Exception as e:
        print(f"[DEBUG] Не удалось принудительно привязать CUDA DLL: {e}")

# stt_module.py
"""
Модуль распознавания речи (Speech-to-Text) с использованием faster-whisper.
Слушает микрофон, определяет конец фразы через VAD и возвращает текст.
"""

import logging
import re
from typing import Callable, Optional

import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

import config

logger = logging.getLogger(__name__)

SAMPLE_RATE = 16000
CHANNELS = 1
FRAME_DURATION_SEC = 0.03

# Обратная совместимость для main и тестов
LOW_CONFIDENCE_THRESHOLD = config.STT_LOW_CONFIDENCE_THRESHOLD


# Проверяет, достаточна ли уверенность Whisper (с допуском у порога)
def is_confidence_acceptable(avg_logprob: float | None) -> bool:
    if avg_logprob is None:
        return True
    effective_threshold = config.STT_LOW_CONFIDENCE_THRESHOLD - config.STT_LOW_CONFIDENCE_MARGIN
    return avg_logprob >= effective_threshold

_model: Optional[WhisperModel] = None
_using_cpu = False
_loaded_model_name: str | None = None


# Возвращает compute_type для Whisper с учётом config
def _resolve_compute_type(device: str) -> str:
    if config.STT_COMPUTE_TYPE != "auto":
        return config.STT_COMPUTE_TYPE
    return "int8" if device == "cpu" else "float16"


# Проверяет доступность CUDA до загрузки GPU-модели
def _cuda_dll_available() -> bool:
    if config.STT_FORCE_CPU:
        return False
    try:
        import nvidia.cublas  # noqa: F401

        return True
    except Exception:
        return False


# Формирует initial_prompt Whisper с wake-word и топом приложений
def get_stt_initial_prompt() -> str:
    try:
        from jarvis.voice.wake_word_module import get_wake_word_display_name

        wake_word = get_wake_word_display_name()
    except Exception:
        wake_word = "Джарвис"

    parts = [
        f"Голосовые команды Windows на русском. Кодовое слово: {wake_word}.",
        "Голосовые команды: открой, запусти, крой, пусти, грой.",
    ]

    try:
        from jarvis.commands import app_scanner

        app_names = app_scanner.get_top_app_names_for_prompt(config.STT_PROMPT_APP_LIMIT)
        if app_names:
            parts.append("Программы: " + ", ".join(app_names) + ".")
    except Exception as e:
        logger.debug("Не удалось добавить приложения в STT prompt: %s", e)

    return " ".join(parts)


# Возвращает индекс микрофона из конфига или None (устройство по умолчанию)
def _get_input_device() -> Optional[int]:
    raw_value = config.STT_INPUT_DEVICE
    if not raw_value:
        return None
    try:
        return int(raw_value)
    except ValueError:
        logger.warning("Некорректный STT_INPUT_DEVICE: %s", raw_value)
        return None


# Список микрофонов для GUI (value, label)
def list_input_devices() -> list[tuple[str, str]]:
    devices: list[tuple[str, str]] = [("", "По умолчанию")]
    try:
        for index, info in enumerate(sd.query_devices()):
            if int(info.get("max_input_channels", 0)) <= 0:
                continue
            name = str(info.get("name", f"Устройство {index}"))
            devices.append((str(index), f"[{index}] {name}"))
    except Exception as e:
        logger.warning("list_input_devices: %s", e)
    return devices


# Нормализует RMS-уровень микрофона в диапазон 0..1
def _frame_level(frame: np.ndarray) -> float:
    try:
        if frame.size == 0:
            return 0.0
        energy = float(np.sqrt(np.mean(frame.astype(np.float32) ** 2)))
        return max(0.0, min(1.0, energy / max(config.STT_ENERGY_THRESHOLD * 4.0, 1e-6)))
    except Exception:
        return 0.0


# Логирует выбранное устройство ввода и тестовый уровень сигнала
def _log_input_device() -> None:
    try:
        device_index = _get_input_device()
        if device_index is None:
            default_device = sd.query_devices(kind="input")
            logger.info("[STT] Микрофон по умолчанию: %s", default_device.get("name", "неизвестно"))
            sample_rate = int(default_device.get("default_samplerate", SAMPLE_RATE))
        else:
            device_info = sd.query_devices(device_index)
            logger.info("[STT] Микрофон [%s]: %s", device_index, device_info.get("name", "неизвестно"))
            sample_rate = int(device_info.get("default_samplerate", SAMPLE_RATE))

        logger.info("[STT] Sample rate микрофона: %s Hz", sample_rate)

        frames = int(sample_rate * 0.5)
        stream_kwargs = {"samplerate": sample_rate, "channels": CHANNELS, "dtype": "float32"}
        if device_index is not None:
            stream_kwargs["device"] = device_index

        with sd.InputStream(**stream_kwargs) as stream:
            audio_chunk, _ = stream.read(frames)
            frame = np.asarray(audio_chunk, dtype=np.float32).flatten()
            peak = float(np.max(np.abs(frame))) if frame.size else 0.0
            logger.info("[STT] Тест микрофона 0.5 сек: peak energy=%.4f", peak)
            if peak < config.STT_ENERGY_THRESHOLD:
                logger.warning("[STT] Сигнал слишком тихий — проверьте уровень микрофона")
    except Exception as e:
        logger.warning("Не удалось получить информацию о микрофоне: %s", e)


# Быстрая проверка микрофона без повторов и без загрузки модели заново
def get_mic_info() -> dict:
    """Возвращает имя устройства, sample rate и уровень сигнала."""
    info = {"name": "неизвестно", "sample_rate": SAMPLE_RATE, "peak": 0.0, "level_ok": False}
    try:
        device_index = _get_input_device()
        if device_index is None:
            default_device = sd.query_devices(kind="input")
            info["name"] = str(default_device.get("name", "неизвестно"))
            sample_rate = int(default_device.get("default_samplerate", SAMPLE_RATE))
        else:
            device_info = sd.query_devices(device_index)
            info["name"] = str(device_info.get("name", "неизвестно"))
            sample_rate = int(device_info.get("default_samplerate", SAMPLE_RATE))

        info["sample_rate"] = sample_rate
        frames = int(sample_rate * 0.5)
        stream_kwargs = {"samplerate": sample_rate, "channels": CHANNELS, "dtype": "float32"}
        if device_index is not None:
            stream_kwargs["device"] = device_index

        with sd.InputStream(**stream_kwargs) as stream:
            audio_chunk, _ = stream.read(frames)
            frame = np.asarray(audio_chunk, dtype=np.float32).flatten()
            peak = float(np.max(np.abs(frame))) if frame.size else 0.0
            info["peak"] = peak
            info["level_ok"] = peak >= config.STT_ENERGY_THRESHOLD
    except Exception as e:
        logger.warning("get_mic_info: %s", e)
    return info


# Короткая запись для теста микрофона (одна попытка, без retry)
def listen_mic_test(
    max_duration_sec: float = 4.0,
    on_level: Optional[Callable[[float], None]] = None,
) -> tuple[Optional[str], Optional[float]]:
    try:
        if _model is None:
            init_stt()
        return _listen_once(max_duration_sec=max_duration_sec, on_level=on_level)
    except Exception as e:
        logger.error("listen_mic_test: %s", e)
        return None, None


# Инициализирует модель Whisper с откатом CUDA -> CPU
def init_stt() -> None:
    global _model, _using_cpu, _loaded_model_name
    if _model is not None:
        return

    _log_input_device()
    logger.info("Загрузка модели Whisper '%s'...", config.STT_MODEL_NAME)

    if config.STT_FORCE_CPU or not _cuda_dll_available():
        if not config.STT_FORCE_CPU:
            logger.info("[STT] CUDA недоступна — сразу загружаю CPU-модель")
        _model = WhisperModel(
            config.STT_MODEL_NAME,
            device="cpu",
            compute_type=_resolve_compute_type("cpu"),
        )
        _using_cpu = True
        _loaded_model_name = config.STT_MODEL_NAME
        logger.info("[STT] Режим: CPU, модель: %s", config.STT_MODEL_NAME)
        logger.info("[SUCCESS] Модель Whisper успешно загружена")
        return

    try:
        _model = WhisperModel(
            config.STT_MODEL_NAME,
            device="cuda",
            compute_type=_resolve_compute_type("cuda"),
        )
        _using_cpu = False
        logger.info("[STT] Режим: GPU, модель: %s", config.STT_MODEL_NAME)

        try:
            _cuda_self_test(_model)
        except Exception as cuda_test_error:
            logger.warning(
                "CUDA не прошёл тестовую транскрибацию (%s). Переключаюсь на CPU.",
                cuda_test_error,
            )
            _model = WhisperModel(
                config.STT_MODEL_NAME,
                device="cpu",
                compute_type=_resolve_compute_type("cpu"),
            )
            _using_cpu = True
            logger.info("[STT] Режим: CPU, модель: %s", config.STT_MODEL_NAME)
    except Exception:
        logger.warning("Ошибка запуска на GPU. Автоматический откат на CPU (int8).")
        _model = WhisperModel(
            config.STT_MODEL_NAME,
            device="cpu",
            compute_type=_resolve_compute_type("cpu"),
        )
        _using_cpu = True
        logger.info("[STT] Режим: CPU, модель: %s", config.STT_MODEL_NAME)

    logger.info("[SUCCESS] Модель Whisper успешно загружена")
    _loaded_model_name = config.STT_MODEL_NAME


# Перезагружает Whisper, если сменилась модель (fast/quality toggle)
def reload_stt_model_if_needed() -> None:
    global _model, _loaded_model_name
    try:
        if _loaded_model_name == config.STT_MODEL_NAME and _model is not None:
            return
        _model = None
        _loaded_model_name = None
        init_stt()
    except Exception as e:
        logger.error("reload_stt_model_if_needed: %s", e)


# Возвращает уже загруженную модель Whisper
def _get_model() -> WhisperModel:
    if _model is None:
        init_stt()
    return _model


# Переключает модель на CPU после ошибки CUDA во время распознавания
def _fallback_to_cpu_model() -> WhisperModel:
    global _model, _using_cpu, _loaded_model_name
    logger.warning("Ошибка CUDA при распознавании. Переключаю модель на CPU...")
    _model = WhisperModel(
        config.STT_MODEL_NAME,
        device="cpu",
        compute_type=_resolve_compute_type("cpu"),
    )
    _using_cpu = True
    _loaded_model_name = config.STT_MODEL_NAME
    logger.info("[STT] Режим: CPU, модель: %s", config.STT_MODEL_NAME)
    return _model


# Выполняет распознавание аудио выбранной моделью
def _run_transcribe(model: WhisperModel, audio: np.ndarray, *, vad_filter: bool | None = None):
    use_vad = config.STT_USE_VAD_FILTER if vad_filter is None else vad_filter
    try:
        segments, info = model.transcribe(
            audio,
            language="ru",
            beam_size=config.STT_BEAM_SIZE,
            initial_prompt=get_stt_initial_prompt(),
            condition_on_previous_text=False,
            compression_ratio_threshold=2.4,
            log_prob_threshold=-1.0,
            no_speech_threshold=0.6,
            vad_filter=use_vad,
        )
        return list(segments), info
    except Exception as e:
        # В exe VAD-модель может отсутствовать — повторяем без фильтра тишины
        if use_vad:
            logger.warning("VAD недоступен, повтор STT без vad_filter: %s", e)
            return _run_transcribe(model, audio, vad_filter=False)
        raise


# Проверяет, что CUDA реально выполняет транскрибацию (не пустой VAD)
def _cuda_self_test(model: WhisperModel) -> None:
    test_audio = (np.random.randn(SAMPLE_RATE * 2).astype(np.float32) * 0.08)
    segments, _ = _run_transcribe(model, test_audio, vad_filter=False)
    if not segments:
        raise RuntimeError("CUDA-тест: пустой результат транскрибации")


# Проверяет, есть ли рабочий микрофон
def _check_microphone() -> bool:
    try:
        device_index = _get_input_device()
        if device_index is None:
            sd.query_devices(kind="input")
        else:
            sd.query_devices(device_index)
        return True
    except Exception as e:
        logger.error("Микрофон недоступен (возможно отключён): %s", e)
        return False


# Определяет, есть ли речь во фрагменте аудио (простой VAD по громкости)
def _is_speech(audio_frame: np.ndarray, threshold: float) -> bool:
    energy = float(np.sqrt(np.mean(audio_frame ** 2)))
    return energy > threshold


# Записывает аудио с микрофона до конца фразы (VAD)
def _record_with_vad(
    max_duration_sec: Optional[float] = None,
    on_level: Optional[Callable[[float], None]] = None,
) -> Optional[np.ndarray]:
    if not _check_microphone():
        return None

    max_duration = max_duration_sec or config.STT_MAX_RECORD_DURATION_SEC
    frame_length = int(SAMPLE_RATE * FRAME_DURATION_SEC)
    silence_frames_limit = int(config.STT_SILENCE_DURATION_SEC / FRAME_DURATION_SEC)
    max_frames = int(max_duration / FRAME_DURATION_SEC)
    wait_frames_limit = int(config.STT_WAIT_SPEECH_TIMEOUT_SEC / FRAME_DURATION_SEC)
    input_device = _get_input_device()

    recorded_frames: list[np.ndarray] = []
    speech_started = False
    silence_frames = 0
    waited_frames = 0

    logger.info("Запись речи с микрофона (STT)...")

    stream_kwargs = {
        "samplerate": SAMPLE_RATE,
        "channels": CHANNELS,
        "dtype": "float32",
    }
    if input_device is not None:
        stream_kwargs["device"] = input_device

    try:
        with sd.InputStream(**stream_kwargs) as stream:
            for _ in range(max_frames + wait_frames_limit):
                audio_chunk, overflowed = stream.read(frame_length)
                if overflowed:
                    logger.warning("Переполнение буфера микрофона")

                frame = np.asarray(audio_chunk, dtype=np.float32).flatten()
                if on_level:
                    try:
                        on_level(_frame_level(frame))
                    except Exception:
                        pass
                has_speech = _is_speech(frame, config.STT_ENERGY_THRESHOLD)

                if not speech_started:
                    if has_speech:
                        speech_started = True
                        recorded_frames.append(frame)
                    else:
                        waited_frames += 1
                        if waited_frames >= wait_frames_limit:
                            logger.info("Таймаут: речь не началась")
                            return None
                    continue

                recorded_frames.append(frame)

                if has_speech:
                    silence_frames = 0
                else:
                    silence_frames += 1
                    if silence_frames >= silence_frames_limit:
                        break

    except sd.PortAudioError as e:
        logger.error("Ошибка PortAudio (микрофон отключён?): %s", e)
        return None
    except Exception as e:
        logger.error("Ошибка записи с микрофона: %s", e)
        return None

    if not recorded_frames:
        if on_level:
            try:
                on_level(0.0)
            except Exception:
                pass
        return None

    if on_level:
        try:
            on_level(0.0)
        except Exception:
            pass

    return np.concatenate(recorded_frames)


# Распознаёт аудио и возвращает текст с оценкой уверенности
def _transcribe_audio(audio: np.ndarray) -> tuple[Optional[str], Optional[float]]:
    try:
        audio = np.asarray(audio, dtype=np.float32).flatten()

        if audio.size < SAMPLE_RATE * 0.3:
            logger.info("Слишком короткая запись для распознавания")
            return None, None

        model = _get_model()
        if _using_cpu:
            segments, _ = _run_transcribe(model, audio)
        else:
            try:
                segments, _ = _run_transcribe(model, audio)
            except Exception:
                logger.warning("Ошибка CUDA при транскрибации. Экстренный переход на CPU.")
                model = _fallback_to_cpu_model()
                segments, _ = _run_transcribe(model, audio)

        text = " ".join(segment.text.strip() for segment in segments).strip()
        text = re.sub(r"\s+", " ", text).strip()

        logprobs = [segment.avg_logprob for segment in segments if segment.avg_logprob is not None]
        avg_logprob = sum(logprobs) / len(logprobs) if logprobs else None

        if not text:
            return None, avg_logprob

        if avg_logprob is not None:
            logger.info("STT avg_logprob: %.3f", avg_logprob)

        return text, avg_logprob

    except Exception as e:
        logger.error("Ошибка распознавания речи: %s", e)
        return None, None


# Одна попытка записи и распознавания
def _listen_once(
    max_duration_sec: Optional[float] = None,
    on_level: Optional[Callable[[float], None]] = None,
    on_recording_done: Optional[Callable[[], None]] = None,
) -> tuple[Optional[str], Optional[float]]:
    audio = _record_with_vad(max_duration_sec=max_duration_sec, on_level=on_level)
    if on_recording_done:
        try:
            on_recording_done()
        except Exception:
            pass
    if audio is None:
        return None, None
    return _transcribe_audio(audio)


# Слушает микрофон и возвращает текст с оценкой уверенности Whisper
def listen_with_confidence(
    on_level: Optional[Callable[[float], None]] = None,
    on_recording_done: Optional[Callable[[], None]] = None,
) -> tuple[Optional[str], Optional[float]]:
    try:
        if _model is None:
            init_stt()

        listen_kwargs = {
            "on_level": on_level,
            "on_recording_done": on_recording_done,
        }
        text, avg_logprob = _listen_once(**listen_kwargs)
        if text is None:
            if config.STT_RETRY_ON_LOW_CONFIDENCE:
                logger.info("Повторная запись STT (тишина или пустой результат)...")
                retry_text, retry_logprob = _listen_once(max_duration_sec=4.0, **listen_kwargs)
                if retry_text:
                    return retry_text, retry_logprob
            return None, avg_logprob

        if not is_confidence_acceptable(avg_logprob):
            logger.warning(
                "STT низкая уверенность: %.3f (порог %.3f, допуск %.3f)",
                avg_logprob,
                config.STT_LOW_CONFIDENCE_THRESHOLD,
                config.STT_LOW_CONFIDENCE_MARGIN,
            )
            if config.STT_RETRY_ON_LOW_CONFIDENCE:
                logger.info("Повторная запись STT (одна попытка)...")
                retry_text, retry_logprob = _listen_once(max_duration_sec=3.0, **listen_kwargs)
                if retry_text and is_confidence_acceptable(retry_logprob):
                    return retry_text, retry_logprob
                if retry_text and (retry_logprob or -999.0) > (avg_logprob or -999.0):
                    return retry_text, retry_logprob
            return None, avg_logprob

        return text, avg_logprob

    except Exception as e:
        logger.error("Неожиданная ошибка в listen_with_confidence(): %s", e)
        return None, None


# Слушает микрофон, распознаёт речь и возвращает только текст
def listen() -> Optional[str]:
    text, _ = listen_with_confidence()
    return text

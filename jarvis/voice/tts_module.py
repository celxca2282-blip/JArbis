# tts_module.py
"""
Модуль синтеза речи (Text-to-Speech) с использованием edge-tts.
Генерирует аудио голосом ru-RU-DmitryNeural и воспроизводит его.
"""

import asyncio
import logging
import os
import re
import threading
import uuid
from pathlib import Path

import edge_tts
import numpy as np
import pygame

import config

logger = logging.getLogger(__name__)

# Мужской естественный русский голос (см. README для альтернатив)
VOICE = config.TTS_VOICE

# Скорость и высота речи из config
SPEECH_RATE = config.TTS_RATE
SPEECH_PITCH = config.TTS_PITCH

# Пауза перед началом фразы (мс)
START_PAUSE_MS = config.TTS_START_PAUSE_MS

# Папка временных mp3-файлов озвучки
TEMP_AUDIO_DIR = config.TEMP_DIR
TEMP_AUDIO_PATTERN = "temp_audio_*.mp3"

# Единые параметры pygame.mixer для всех звуков модуля
MIXER_SAMPLE_RATE = 44100
MIXER_CHANNELS = 2
MIXER_BUFFER = 512

# Параметры звукового сигнала активации
ACTIVATION_SAMPLE_RATE = MIXER_SAMPLE_RATE
ACTIVATION_TONE_DURATION = 0.08
ACTIVATION_PAUSE_DURATION = 0.02
ACTIVATION_FADE_RATIO = 0.15

# Отдельный канал для коротких служебных звуков, чтобы не трогать music-канал речи
_activation_channel: pygame.mixer.Channel | None = None

# Флаг прерывания текущей озвучки (кнопка «Стоп» в GUI)
_speech_cancel = threading.Event()

# Ленивый движок Windows SAPI для быстрого режима
_sapi_engine = None

# Кэш списка голосов edge-tts (ShortName -> подпись)
_edge_voices_cache: list[tuple[str, str]] | None = None

# Фраза для превью в настройках GUI
PREVIEW_PHRASE = "Сэр, системы в норме. Так будет звучать мой голос."
PREVIEW_PHRASE_EN = "Sir, all systems are operational. This is how I will sound."

# Профили движка озвучки для GUI
TTS_PROFILES: list[tuple[str, str]] = [
    ("piper", "◆ Piper HD — мужской, офлайн"),
    ("edge", "● Edge-TTS — онлайн"),
    ("sapi", "○ Windows SAPI — запасной"),
]

# Готовые образы — без дублей, каждый голос уникален
VOICE_PRESETS: list[tuple[str, str, dict]] = [
    (
        "jarvis_hd",
        "◆ Джарвис HD — Руслан",
        {
            "TTS_ENGINE": "piper",
            "PIPER_VOICE": "ru_RU-ruslan-medium",
            "TTS_VOICE": "ru-RU-DmitryNeural",
            "TTS_RATE": "+0%",
            "TTS_PITCH": "+0Hz",
            "EDGE_TTS_LOCALE": "ru",
        },
    ),
    (
        "jarvis_dmitri",
        "◆ Дмитрий — мужской",
        {
            "TTS_ENGINE": "piper",
            "PIPER_VOICE": "ru_RU-dmitri-medium",
            "TTS_VOICE": "ru-RU-DmitryNeural",
            "TTS_RATE": "+0%",
            "TTS_PITCH": "+0Hz",
            "EDGE_TTS_LOCALE": "ru",
        },
    ),
    (
        "jarvis_denis",
        "◆ Денис — спокойный",
        {
            "TTS_ENGINE": "piper",
            "PIPER_VOICE": "ru_RU-denis-medium",
            "TTS_VOICE": "ru-RU-DmitryNeural",
            "TTS_RATE": "+0%",
            "TTS_PITCH": "+0Hz",
            "EDGE_TTS_LOCALE": "ru",
        },
    ),
    (
        "irina_female",
        "◆ Ирина — женский",
        {
            "TTS_ENGINE": "piper",
            "PIPER_VOICE": "ru_RU-irina-medium",
            "TTS_VOICE": "ru-RU-SvetlanaNeural",
            "TTS_RATE": "+0%",
            "TTS_PITCH": "+0Hz",
            "EDGE_TTS_LOCALE": "ru",
        },
    ),
    (
        "edge_dmitry",
        "● Дмитрий Neural — онлайн",
        {
            "TTS_ENGINE": "edge",
            "PIPER_VOICE": "ru_RU-ruslan-medium",
            "TTS_VOICE": "ru-RU-DmitryNeural",
            "TTS_RATE": "+0%",
            "TTS_PITCH": "+0Hz",
            "EDGE_TTS_LOCALE": "ru",
        },
    ),
    (
        "edge_guy_en",
        "● Guy EN — JARVIS style",
        {
            "TTS_ENGINE": "edge",
            "PIPER_VOICE": "ru_RU-ruslan-medium",
            "TTS_VOICE": "en-US-GuyNeural",
            "TTS_RATE": "+0%",
            "TTS_PITCH": "+0Hz",
            "EDGE_TTS_LOCALE": "en",
        },
    ),
    (
        "sapi_robot",
        "○ SAPI — робот",
        {
            "TTS_ENGINE": "sapi",
            "PIPER_VOICE": "ru_RU-ruslan-medium",
            "TTS_VOICE": "ru-RU-DmitryNeural",
            "TTS_RATE": "+0%",
            "TTS_PITCH": "+0Hz",
            "EDGE_TTS_LOCALE": "ru",
        },
    ),
]

# Резервные голоса edge-tts, если сеть недоступна
FALLBACK_RU_EDGE_VOICES: list[tuple[str, str]] = [
    ("ru-RU-DmitryNeural", "Дмитрий — мужской, уверенный"),
    ("ru-RU-SvetlanaNeural", "Светлана — женский, нейтральный"),
    ("ru-RU-DariyaNeural", "Дария — женский, тёплый"),
]

FALLBACK_EN_EDGE_VOICES: list[tuple[str, str]] = [
    ("en-US-GuyNeural", "Guy — мужской, глубокий"),
    ("en-US-RyanNeural", "Ryan — мужской, нейтральный"),
    ("en-US-ChristopherNeural", "Christopher — мужской, спокойный"),
    ("en-US-AriaNeural", "Aria — женский"),
    ("en-US-JennyNeural", "Jenny — женский, дружелюбный"),
    ("en-GB-RyanNeural", "Ryan — британский мужской"),
    ("en-GB-SoniaNeural", "Sonia — британский женский"),
]


# Перечитывает голос и параметры из config после сохранения настроек
def reload_tts_settings() -> None:
    global VOICE, SPEECH_RATE, SPEECH_PITCH, _sapi_engine
    VOICE = config.TTS_VOICE
    SPEECH_RATE = config.TTS_RATE
    SPEECH_PITCH = config.TTS_PITCH
    _sapi_engine = None
    try:
        from jarvis.voice import piper_tts, silero_tts

        piper_tts.unload_model()
        silero_tts.unload_model()
    except Exception:
        pass


# Выбирает движок озвучки с учётом fast mode
def resolve_tts_engine() -> str:
    engine = (getattr(config, "TTS_ENGINE", "piper") or "piper").strip().lower()
    if engine not in ("piper", "silero", "edge", "sapi"):
        engine = "piper"
    # В быстром режиме edge не используем — локальный Piper HD
    if config.FAST_MODE and engine == "edge":
        engine = "piper"
    return engine


# Достаёт поле из объекта edge-tts или словаря
def _voice_field(voice, name: str, default: str = "") -> str:
    if isinstance(voice, dict):
        return str(voice.get(name, default))
    return str(getattr(voice, name, default))


# Возвращает настройки готового образа по id
def get_voice_preset(preset_id: str) -> dict | None:
    pid = (preset_id or "").strip()
    for sid, _label, settings in VOICE_PRESETS:
        if sid == pid:
            return dict(settings)
    return None


# Применяет образ к словарю настроек GUI (для сохранения)
def apply_voice_preset(preset_id: str, base: dict | None = None) -> dict:
    payload = dict(base or {})
    preset = get_voice_preset(preset_id)
    if preset:
        payload.update(preset)
    return payload


# Проверяет, английский ли голос edge-tts
def is_english_edge_voice(short_name: str) -> bool:
    low = (short_name or "").lower()
    return low.startswith("en-")


# Возвращает фразу превью под выбранный голос
def preview_phrase_for_voice(edge_voice: str | None = None, engine: str | None = None) -> str:
    eng = (engine or resolve_tts_engine()).strip().lower()
    voice = edge_voice or config.TTS_VOICE
    if eng == "edge" and is_english_edge_voice(voice):
        return PREVIEW_PHRASE_EN
    return PREVIEW_PHRASE


# Возвращает голоса edge-tts: (ShortName, подпись), фильтр ru/en/all
def list_edge_voices(locale: str | None = None, refresh: bool = False) -> list[tuple[str, str]]:
    loc = (locale or getattr(config, "EDGE_TTS_LOCALE", "ru") or "ru").strip().lower()
    if loc not in ("ru", "en", "all"):
        loc = "ru"

    try:
        all_voices = _fetch_all_edge_voices(refresh=refresh)
        filtered: list[tuple[str, str]] = []
        for short, label in all_voices:
            if loc == "all":
                filtered.append((short, label))
            elif loc == "ru" and short.lower().startswith("ru-"):
                filtered.append((short, label))
            elif loc == "en" and short.lower().startswith("en-"):
                filtered.append((short, label))
        if filtered:
            return filtered
    except Exception as e:
        logger.warning("list_edge_voices: %s", e)

    if loc == "en":
        return list(FALLBACK_EN_EDGE_VOICES)
    if loc == "all":
        return list(FALLBACK_RU_EDGE_VOICES) + list(FALLBACK_EN_EDGE_VOICES)
    return list(FALLBACK_RU_EDGE_VOICES)


# Загружает полный список голосов edge-tts в кэш
def _fetch_all_edge_voices(refresh: bool = False) -> list[tuple[str, str]]:
    global _edge_voices_cache
    if _edge_voices_cache is not None and not refresh:
        return list(_edge_voices_cache)

    try:
        all_voices = asyncio.run(edge_tts.list_voices())
        result: list[tuple[str, str]] = []
        for voice in sorted(all_voices, key=lambda v: _voice_field(v, "ShortName")):
            short = _voice_field(voice, "ShortName")
            locale_name = _voice_field(voice, "Locale", "")
            if not (locale_name.lower().startswith("ru") or locale_name.lower().startswith("en")):
                continue
            friendly = _voice_field(voice, "FriendlyName", short)
            gender = _voice_field(voice, "Gender", "")
            label = friendly
            if gender:
                label = f"{friendly} ({gender})"
            result.append((short, label))
        if result:
            _edge_voices_cache = result
            return list(result)
    except Exception as e:
        logger.warning("Не удалось загрузить голоса edge-tts: %s", e)

    _edge_voices_cache = list(FALLBACK_RU_EDGE_VOICES) + list(FALLBACK_EN_EDGE_VOICES)
    return list(_edge_voices_cache)


# Возвращает русские голоса edge-tts: (ShortName, подпись для combobox)
def list_russian_edge_voices(refresh: bool = False) -> list[tuple[str, str]]:
    return list_edge_voices(locale="ru", refresh=refresh)


# Возвращает голоса Windows SAPI: (id, подпись)
def list_sapi_voices() -> list[tuple[str, str]]:
    try:
        import pyttsx3

        engine = pyttsx3.init()
        voices = engine.getProperty("voices") or []
        result: list[tuple[str, str]] = []
        for voice in voices:
            voice_id = getattr(voice, "id", "") or ""
            name = getattr(voice, "name", voice_id) or voice_id
            label = name
            low = f"{voice_id} {name}".lower()
            if "ru" in low or "russian" in low or "рус" in low:
                label = f"★ {name}"
            result.append((voice_id, label))
        try:
            engine.stop()
        except Exception:
            pass
        if not result:
            return [("", "Системный голос по умолчанию")]
        result.sort(key=lambda item: (0 if item[1].startswith("★") else 1, item[1].lower()))
        return result
    except Exception as e:
        logger.warning("Не удалось получить голоса SAPI: %s", e)
        return [("", "Системный голос по умолчанию")]


# Подпись голоса edge-tts по ShortName
def edge_voice_label(short_name: str) -> str:
    for sid, label in _fetch_all_edge_voices():
        if sid == short_name:
            return label
    for sid, label in FALLBACK_RU_EDGE_VOICES + FALLBACK_EN_EDGE_VOICES:
        if sid == short_name:
            return label
    return short_name


# Применяет выбранный SAPI-голос к движку pyttsx3
def _apply_sapi_voice(engine, voice_id: str | None = None) -> None:
    target = (voice_id if voice_id is not None else config.TTS_SAPI_VOICE).strip()
    voices = engine.getProperty("voices") or []
    if target:
        for voice in voices:
            vid = getattr(voice, "id", "") or ""
            if vid == target:
                engine.setProperty("voice", vid)
                return
    for voice in voices:
        vid = getattr(voice, "id", "") or ""
        name = getattr(voice, "name", "") or ""
        low = f"{vid} {name}".lower()
        if "ru" in low or "russian" in low or "рус" in low:
            engine.setProperty("voice", vid)
            return


# Инициализирует pygame.mixer один раз для речи и служебных сигналов
def _init_mixer() -> None:
    global _activation_channel

    if not pygame.mixer.get_init():
        logger.info("Инициализация pygame.mixer")
        pygame.mixer.init(
            frequency=MIXER_SAMPLE_RATE,
            size=-16,
            channels=MIXER_CHANNELS,
            buffer=MIXER_BUFFER,
        )
        pygame.mixer.set_num_channels(8)

    if _activation_channel is None:
        _activation_channel = pygame.mixer.Channel(1)


# Сбрасывает флаг прерывания перед новой фразой
def _reset_speech_cancel() -> None:
    _speech_cancel.clear()


# Немедленно обрывает озвучку и служебные сигналы
def stop_speech() -> None:
    try:
        _speech_cancel.set()
        if pygame.mixer.get_init():
            pygame.mixer.music.stop()
            try:
                pygame.mixer.music.unload()
            except Exception:
                pass
            if _activation_channel and _activation_channel.get_busy():
                _activation_channel.stop()
        if _sapi_engine is not None:
            try:
                _sapi_engine.stop()
            except Exception:
                pass
        try:
            from jarvis.voice import piper_tts, silero_tts

            piper_tts.stop_playback()
            silero_tts.stop_playback()
        except Exception:
            pass
        logger.info("Озвучка прервана")
    except Exception as e:
        logger.warning("stop_speech: %s", e)


# Возвращает кэшированный pyttsx3-движок (Windows SAPI)
def _get_sapi_engine():
    global _sapi_engine
    if _sapi_engine is None:
        import pyttsx3

        _sapi_engine = pyttsx3.init()
        _apply_sapi_voice(_sapi_engine)
        try:
            _sapi_engine.setProperty("rate", 185)
        except Exception:
            pass
    return _sapi_engine


# Озвучка через локальный SAPI — быстро, без интернета
def _speak_sapi(text: str, voice_id: str | None = None) -> None:
    try:
        if _speech_cancel.is_set():
            return
        engine = _get_sapi_engine()
        if voice_id:
            _apply_sapi_voice(engine, voice_id)
        engine.stop()
        engine.say(text)
        engine.runAndWait()
    except Exception as e:
        logger.error("Ошибка SAPI TTS: %s", e)


# Генерирует короткий синусоидальный импульс с плавным нарастанием и затуханием
def _generate_tone(frequency: float, duration_sec: float, sample_rate: int) -> np.ndarray:
    sample_count = int(sample_rate * duration_sec)
    time_axis = np.linspace(0, duration_sec, sample_count, endpoint=False)
    tone = np.sin(2 * np.pi * frequency * time_axis).astype(np.float32)

    fade_samples = max(1, int(sample_count * ACTIVATION_FADE_RATIO))
    fade_in = np.linspace(0.0, 1.0, fade_samples, dtype=np.float32)
    fade_out = np.linspace(1.0, 0.0, fade_samples, dtype=np.float32)
    tone[:fade_samples] *= fade_in
    tone[-fade_samples:] *= fade_out

    return tone


# Собирает двойной высокочастотный сигнал активации в 16-битный PCM
def _build_activation_pcm() -> bytes:
    first_beep = _generate_tone(1000, ACTIVATION_TONE_DURATION, ACTIVATION_SAMPLE_RATE)
    pause = np.zeros(int(ACTIVATION_SAMPLE_RATE * ACTIVATION_PAUSE_DURATION), dtype=np.float32)
    second_beep = _generate_tone(1300, ACTIVATION_TONE_DURATION, ACTIVATION_SAMPLE_RATE)

    signal = np.concatenate([first_beep, pause, second_beep])
    signal = np.clip(signal * 0.45, -1.0, 1.0)
    # mixer работает в stereo, поэтому дублируем моно-сигнал на два канала
    stereo_signal = np.column_stack((signal, signal))
    pcm = (stereo_signal * 32767).astype(np.int16)
    return pcm.tobytes()


# Воспроизводит короткий двойной звуковой сигнал активации
def play_activation_sound() -> None:
    try:
        logger.info("Воспроизведение сигнала активации")
        _init_mixer()
        sound = pygame.mixer.Sound(buffer=_build_activation_pcm())
        _activation_channel.play(sound)

        # Ждём окончания сигнала, чтобы не пересечься с записью STT
        while _activation_channel.get_busy():
            if _speech_cancel.is_set():
                _activation_channel.stop()
                return
            pygame.time.wait(10)

        logger.info("Сигнал активации воспроизведён")
    except pygame.error as e:
        logger.error("Ошибка воспроизведения сигнала активации: %s", e)
    except Exception as e:
        logger.error("Не удалось сгенерировать сигнал активации: %s", e)


# Подготавливает текст перед озвучкой: добавляет пунктуацию в конце при необходимости
def _prepare_text(text: str) -> str:
    prepared = text.strip()
    if not prepared:
        return prepared

    # Если в конце нет знака препинания — добавляем точку для правильной интонации
    if not re.search(r"[.!?…:;»\"')\]]$", prepared):
        prepared += "."

    return prepared


# Асинхронно сохраняет озвучку текста во временный mp3-файл
async def _generate_audio(
    text: str,
    file_path: Path,
    voice: str | None = None,
    rate: str | None = None,
    pitch: str | None = None,
) -> None:
    # Убираем эмодзи, оставляем кириллицу и пунктуацию
    text = re.sub(r"[^\w\s\d.,!:?ёЁа-яА-Я-]", "", text, flags=re.UNICODE)
    prepared_text = _prepare_text(text)
    if not prepared_text:
        logger.info("После очистки текст пуст — озвучка пропущена")
        return

    use_voice = voice or VOICE
    use_rate = rate if rate is not None else SPEECH_RATE
    use_pitch = pitch if pitch is not None else SPEECH_PITCH

    logger.info("Генерация голоса через edge-tts (голос: %s)", use_voice)
    communicate = edge_tts.Communicate(prepared_text, use_voice, rate=use_rate, pitch=use_pitch)
    await communicate.save(str(file_path))
    if not file_path.is_file() or file_path.stat().st_size < 128:
        raise RuntimeError("edge-tts не вернул аудиофайл")
    logger.info("Аудиофайл сгенерирован: %s", file_path)


# Создаёт уникальный путь для временного аудиофайла
def _create_temp_audio_path() -> Path:
    return TEMP_AUDIO_DIR / f"temp_audio_{uuid.uuid4()}.mp3"


# Удаляет старые временные файлы озвучки, если они не заняты системой
def cleanup_temp_audio() -> None:
    for file_path in TEMP_AUDIO_DIR.glob(TEMP_AUDIO_PATTERN):
        try:
            file_path.unlink()
        except OSError:
            # Windows может держать mp3 открытым после pygame; это не критично
            continue


# Воспроизводит mp3-файл и ждёт окончания
def _play_audio(file_path: Path) -> None:
    try:
        _init_mixer()
        if _activation_channel.get_busy():
            _activation_channel.stop()

        pygame.mixer.music.load(str(file_path))

        # Даём звуковой карте мгновение «проснуться» перед стартом речи
        pygame.time.delay(START_PAUSE_MS)

        pygame.mixer.music.play()
        logger.info("Воспроизведение начато")

        # Ждём окончания или прерывания через stop_speech()
        while pygame.mixer.music.get_busy():
            if _speech_cancel.is_set():
                pygame.mixer.music.stop()
                logger.info("Воспроизведение прервано")
                break
            pygame.time.Clock().tick(10)

        if not _speech_cancel.is_set():
            logger.info("Воспроизведение завершено")
    except pygame.error as e:
        logger.error("Ошибка аудиоустройства (возможно, занято): %s", e)
        raise
    finally:
        try:
            pygame.mixer.music.stop()
            pygame.mixer.music.unload()
        except Exception as e:
            logger.warning("Ошибка при остановке воспроизведения речи: %s", e)


# Озвучивает текст через edge-tts с опциональными переопределениями (превью в GUI)
def _speak_edge_via_node(
    text: str,
    *,
    voice: str | None = None,
    rate: str | None = None,
    pitch: str | None = None,
) -> bool:
    """Node.js sidecar (порт 17848) — быстрее и изолирован от Python GIL."""
    try:
        from jarvis.core.sidecar_manager import SidecarManager

        mp3 = SidecarManager.instance().speak_edge(
            text,
            voice or config.TTS_VOICE,
            rate or config.TTS_RATE,
            pitch or config.TTS_PITCH,
        )
        if mp3 and Path(mp3).is_file() and Path(mp3).stat().st_size >= 128:
            _play_audio(Path(mp3))
            return True
    except Exception as e:
        logger.debug("Node Edge-TTS: %s", e)
    return False


def speak_edge(
    text: str,
    *,
    voice: str | None = None,
    rate: str | None = None,
    pitch: str | None = None,
    muted: bool = False,
) -> None:
    if muted:
        return

    prepared = text.strip()
    if not prepared:
        return

    _reset_speech_cancel()
    temp_audio_path = _create_temp_audio_path()

    try:
        if _speak_edge_via_node(prepared, voice=voice, rate=rate, pitch=pitch):
            if _speech_cancel.is_set():
                return
            return

        asyncio.run(_generate_audio(prepared, temp_audio_path, voice=voice, rate=rate, pitch=pitch))

        if _speech_cancel.is_set():
            return
        if not temp_audio_path.exists() or temp_audio_path.stat().st_size < 128:
            _speak_sapi(prepared)
            return
        _play_audio(temp_audio_path)
    except Exception as e:
        logger.error("Ошибка озвучки edge-tts: %s", e)
        if not _speech_cancel.is_set():
            _speak_sapi(prepared)
    finally:
        try:
            pygame.mixer.music.unload()
        except Exception:
            pass
        for _ in range(5):
            try:
                if temp_audio_path.exists():
                    os.remove(temp_audio_path)
                break
            except OSError:
                pygame.time.wait(100)
        cleanup_temp_audio()


# Короткое превью выбранного голоса (настройки GUI)
def preview_voice(
    *,
    engine: str | None = None,
    edge_voice: str | None = None,
    sapi_voice: str | None = None,
    piper_voice: str | None = None,
    silero_speaker: str | None = None,
    silero_model: str | None = None,
    rate: str | None = None,
    pitch: str | None = None,
    use_sapi: bool | None = None,
) -> None:
    try:
        _reset_speech_cancel()
        eng = (engine or resolve_tts_engine()).strip().lower()
        if use_sapi is True:
            eng = "sapi"
        elif use_sapi is False and eng == "sapi":
            eng = "piper"

        phrase = preview_phrase_for_voice(edge_voice=edge_voice, engine=eng)

        if eng == "piper":
            if not speak_piper(phrase, voice_id=piper_voice or config.PIPER_VOICE):
                logger.warning("Piper preview failed — fallback edge")
                speak_edge(
                    phrase,
                    voice=edge_voice or config.TTS_VOICE,
                    rate=rate or config.TTS_RATE,
                    pitch=pitch or config.TTS_PITCH,
                )
        elif eng == "silero":
            from jarvis.voice import silero_tts

            if not silero_tts.speak(
                phrase,
                speaker=silero_speaker or config.SILERO_SPEAKER,
                model_id=silero_model or config.SILERO_MODEL,
                speed=1.0,
                cancel_check=_speech_cancel.is_set,
            ):
                logger.warning("Silero preview failed — fallback piper")
                speak_piper(phrase)
        elif eng == "sapi":
            _speak_sapi(phrase, voice_id=sapi_voice or config.TTS_SAPI_VOICE or None)
        else:
            speak_edge(
                phrase,
                voice=edge_voice or config.TTS_VOICE,
                rate=rate or config.TTS_RATE,
                pitch=pitch or config.TTS_PITCH,
            )
    except Exception as e:
        logger.error("Ошибка превью голоса: %s", e)


# Озвучивает через Piper HD
def speak_piper(text: str, *, voice_id: str | None = None) -> bool:
    from jarvis.voice import piper_tts

    _reset_speech_cancel()
    return piper_tts.speak(
        text,
        voice_id=voice_id or config.PIPER_VOICE,
        cancel_check=_speech_cancel.is_set,
    )


# Озвучивает через Silero с fallback
def speak_silero(text: str, *, speaker: str | None = None, model_id: str | None = None) -> bool:
    from jarvis.voice import silero_tts

    if not silero_tts.can_speak():
        logger.warning("Silero недоступен: установите requirements-optional-silero.txt")
        return False

    _reset_speech_cancel()
    return silero_tts.speak(
        text,
        speaker=speaker or config.SILERO_SPEAKER,
        model_id=model_id or config.SILERO_MODEL,
        cancel_check=_speech_cancel.is_set,
    )


# Озвучивает текст: генерирует mp3 и сразу воспроизводит
def speak(text: str, muted: bool = False) -> None:
    if muted:
        logger.info("TTS отключён (mute): %s", text[:80])
        return

    prepared = text.strip()
    if not prepared:
        logger.info("Пустой текст для озвучки — пропуск")
        return

    engine = resolve_tts_engine()
    logger.info("TTS engine=%s: %s", engine, prepared[:80])

    if engine == "piper":
        if speak_piper(prepared):
            return
        logger.warning("Piper недоступен — fallback edge")
        speak_edge(prepared, muted=muted)
        return

    if engine == "silero":
        if speak_silero(prepared):
            return
        logger.warning("Silero недоступен — fallback piper")
        if speak_piper(prepared):
            return
        speak_edge(prepared, muted=muted)
        return

    if engine == "sapi":
        _speak_sapi(prepared, voice_id=config.TTS_SAPI_VOICE or None)
        return

    speak_edge(prepared, muted=muted)

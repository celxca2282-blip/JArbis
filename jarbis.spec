# -*- mode: python ; coding: utf-8 -*-
"""
Спецификация PyInstaller для JArbis (Windows GUI).
Сборка: python scripts/build_exe.py
Проверка: python scripts/verify_exe_bundle.py
"""

from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_all,
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
)

ROOT = Path(SPECPATH)
ASSETS = ROOT / "jarvis" / "gui" / "assets"

block_cipher = None

datas = [
    (str(ASSETS), "jarvis/gui/assets"),
    (str(ROOT / ".env.example"), "."),
]
binaries = []
hiddenimports = [
    "customtkinter",
    "darkdetect",
    "PIL",
    "PIL._imagingtk",
    "PIL._tkinter_finder",
    "pystray",
    "pystray._win32",
    "jarvis",
    "faster_whisper",
    "edge_tts",
    "piper",
    "onnxruntime",
    "vosk",
    "vosk.vosk_cffi",
    "openwakeword",
    "scipy",
    "scipy.special",
    "scipy.linalg",
    "pyttsx3",
    "pyttsx3.drivers",
    "pyttsx3.drivers.sapi5",
    "comtypes",
    "pycaw",
    "keyboard",
    "sounddevice",
    "pyaudio",
    "pygame",
    "certifi",
]

# Все модули проекта
hiddenimports += collect_submodules("jarvis")

# Piper TTS: espeak-ng-data + native bridge
datas += collect_data_files(
    "piper",
    includes=[
        "espeak-ng-data/**/*",
        "tashkeel/**/*",
        "*.pyi",
        "py.typed",
    ],
)
binaries += collect_dynamic_libs("piper")

# Vosk wake-word: libvosk.dll и зависимости
_vosk_datas, _vosk_binaries, _vosk_hidden = collect_all("vosk")
datas += _vosk_datas
binaries += _vosk_binaries
hiddenimports += _vosk_hidden

# faster-whisper: VAD-модель silero_vad_v6.onnx
datas += collect_data_files("faster_whisper", includes=["assets/**/*"])

# Whisper backend: ctranslate2 DLL
binaries += collect_dynamic_libs("ctranslate2")

# ONNX runtime: Piper / openwakeword
_ort_datas, _ort_binaries, _ort_hidden = collect_all("onnxruntime")
datas += _ort_datas
binaries += _ort_binaries
hiddenimports += _ort_hidden

# CustomTkinter: темы и assets
_ctk_datas, _ctk_binaries, _ctk_hidden = collect_all("customtkinter")
datas += _ctk_datas
binaries += _ctk_binaries
hiddenimports += _ctk_hidden

# HTTPS: cacert.pem для requests / huggingface / openrouter
datas += collect_data_files("certifi")

# openWakeWord (опциональный движок wake-word)
_oww_datas, _oww_binaries, _oww_hidden = collect_all("openwakeword")
datas += _oww_datas
binaries += _oww_binaries
hiddenimports += _oww_hidden

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(ROOT / "scripts" / "pyi_rth_jarbis.py")],
    excludes=["torch", "torchaudio", "matplotlib", "pandas", "notebook", "pytest"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="JArbis",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ASSETS / "icon.ico") if (ASSETS / "icon.ico").is_file() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="JArbis",
)

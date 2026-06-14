# pyi_rth_jarbis.py
"""Runtime hook PyInstaller: рабочая папка и DLL-пути для frozen exe."""

import os
import sys
from pathlib import Path

# Папка с exe (не _internal) — для data/, .env, логов
if getattr(sys, "frozen", False):
    exe_dir = Path(sys.executable).resolve().parent
    os.chdir(exe_dir)
    os.environ.setdefault("JARBIS_HOME", str(exe_dir))
    # В exe CUDA часто ломает faster-whisper; CPU стабильнее (переопределяется через .env)
    os.environ.setdefault("STT_FORCE_CPU", "1")
    # small быстрее medium на CPU; явный STT_MODEL_NAME в .env имеет приоритет
    os.environ.setdefault("STT_MODEL_NAME", "small")

    # Папки с нативными DLL — vosk, whisper, onnx, piper
    internal = Path(getattr(sys, "_MEIPASS", exe_dir / "_internal"))
    dll_dirs = (
        internal / "vosk",
        internal / "ctranslate2",
        internal / "onnxruntime" / "capi",
        internal / "piper",
    )
    extra_path: list[str] = []
    for dll_dir in dll_dirs:
        if not dll_dir.is_dir():
            continue
        path_str = str(dll_dir)
        extra_path.append(path_str)
        if hasattr(os, "add_dll_directory"):
            try:
                os.add_dll_directory(path_str)
            except Exception:
                pass
    if extra_path:
        os.environ["PATH"] = os.pathsep.join(extra_path + [os.environ.get("PATH", "")])

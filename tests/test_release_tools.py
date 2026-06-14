# tests/test_release_tools.py
"""Тесты скриптов сборки и verify bundle."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from exe_bundle_manifest import verify_dist


def test_exe_bundle_manifest_detects_missing(tmp_path: Path) -> None:
    dist = tmp_path / "JArbis"
    dist.mkdir()
    (dist / "JArbis.exe").write_bytes(b"")
    missing = verify_dist(dist)
    assert "_internal/vosk/libvosk.dll" in missing
    assert "JArbis.exe" not in missing

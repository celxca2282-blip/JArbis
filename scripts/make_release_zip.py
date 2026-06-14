#!/usr/bin/env python3
"""
Собирает zip для GitHub Releases из dist/JArbis/.
Запуск после build_exe.py:
  python scripts/make_release_zip.py
  python scripts/make_release_zip.py --version 1.0.1
"""

from __future__ import annotations

import argparse
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = ROOT / "dist" / "JArbis"
RELEASES_DIR = ROOT / "releases"
DEFAULT_VERSION = "1.0.0"


def _zip_dir(source: Path, archive: Path) -> None:
    """Упаковывает папку в zip с корнем JArbis/."""
    archive.parent.mkdir(parents=True, exist_ok=True)
    if archive.is_file():
        archive.unlink()

    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for path in sorted(source.rglob("*")):
            if path.is_dir():
                continue
            arcname = Path("JArbis") / path.relative_to(source)
            zf.write(path, arcname.as_posix())


def main() -> None:
    parser = argparse.ArgumentParser(description="Zip dist/JArbis для GitHub Release")
    parser.add_argument("--version", default=DEFAULT_VERSION, help="Версия релиза, например 1.0.1")
    parser.add_argument("--skip-prepare", action="store_true", help="Не вызывать prepare_tester_dist")
    args = parser.parse_args()

    if not DIST_DIR.is_dir() or not (DIST_DIR / "JArbis.exe").is_file():
        print("Сначала соберите exe: python scripts/build_exe.py")
        sys.exit(1)

    if not args.skip_prepare:
        sys.path.insert(0, str(ROOT / "scripts"))
        from prepare_tester_dist import prepare_tester_dist

        prepare_tester_dist(DIST_DIR)

    version = args.version.strip().lstrip("v")
    archive = RELEASES_DIR / f"JArbis-v{version}-win64.zip"

    print(f"Упаковка: {DIST_DIR}")
    _zip_dir(DIST_DIR, archive)

    size_mb = archive.stat().st_size / (1024 * 1024)
    print(f"\nГотово: {archive}")
    print(f"Размер: {size_mb:.1f} МБ")
    if size_mb > 1900:
        print("Внимание: близко к лимиту GitHub 2 ГБ на файл — проверь размер bundle.")

    print("\nДальше на GitHub:")
    print("  Releases → Draft new release → tag v" + version)
    print(f"  Прикрепить: {archive.name}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Проверяет, что в dist/JArbis/ есть все критичные ресурсы для голоса и GUI.
Запуск: python scripts/verify_exe_bundle.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from exe_bundle_manifest import verify_dist  # noqa: E402


def main() -> None:
    dist_dir = ROOT / "dist" / "JArbis"
    if not dist_dir.is_dir():
        print(f"Ошибка: нет папки {dist_dir}")
        sys.exit(1)

    missing = verify_dist(dist_dir)
    if missing:
        print("Сборка exe неполная. Отсутствует:")
        for item in missing:
            print(f"  - {item}")
        sys.exit(1)

    print(f"OK: все критичные файлы на месте ({dist_dir})")


if __name__ == "__main__":
    main()

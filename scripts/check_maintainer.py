#!/usr/bin/env python3
"""
Быстрая проверка для режима сопровождения beta.
Запуск: python scripts/check_maintainer.py
        python scripts/check_maintainer.py --online   # + GitHub Issues
        python scripts/check_maintainer.py --pytest   # + полный pytest
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GITHUB_REPO = "celxca2282-blip/JArbis"


def _run(cmd: list[str]) -> tuple[int, str]:
    """Запускает команду и возвращает код и stdout+stderr."""
    try:
        proc = subprocess.run(
            cmd,
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        return proc.returncode, out.strip()
    except OSError as exc:
        return 1, str(exc)


def _check_secrets_not_tracked() -> list[str]:
    """Проверяет, что .env и gui_settings не попали в git."""
    problems: list[str] = []
    code, out = _run(["git", "ls-files", ".env", "data/gui_settings.json"])
    if code != 0:
        return problems
    for line in out.splitlines():
        line = line.strip()
        if line:
            problems.append(f"В git отслеживается секретный файл: {line}")
    return problems


def _check_git_clean() -> tuple[bool, str]:
    code, out = _run(["git", "status", "--porcelain"])
    if code != 0:
        return False, "git status недоступен"
    if out:
        return False, f"Есть незакоммиченные изменения:\n{out}"
    return True, "working tree clean"


def _fetch_github(path: str) -> dict | list | None:
    url = f"https://api.github.com/repos/{GITHUB_REPO}/{path}"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            return json.load(resp)
    except Exception as exc:
        print(f"  [!] GitHub API: {exc}")
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Проверка JArbis в режиме maintenance")
    parser.add_argument("--online", action="store_true", help="Проверить Issues и релиз на GitHub")
    parser.add_argument("--pytest", action="store_true", help="Запустить pytest")
    args = parser.parse_args()

    sys.path.insert(0, str(ROOT))
    import config

    print("=== JArbis maintainer check ===\n")
    ok = True

    print(f"VERSION: {config.VERSION}")

    clean, msg = _check_git_clean()
    print(f"Git: {'OK' if clean else 'WARN'} — {msg.split(chr(10))[0]}")
    if not clean:
        ok = False

    secrets = _check_secrets_not_tracked()
    if secrets:
        ok = False
        for s in secrets:
            print(f"SECURITY: {s}")
    else:
        print("Secrets: OK — .env не в git")

    env_path = ROOT / ".env"
    if env_path.is_file():
        print(f".env локально: есть ({env_path}) — не коммить")

    if args.pytest:
        print("\nPytest...")
        code, out = _run([sys.executable, "-m", "pytest", "tests/", "-q"])
        tail = "\n".join(out.splitlines()[-3:])
        print(tail)
        if code != 0:
            ok = False
            print("Pytest: FAIL")
        else:
            print("Pytest: OK")

    if args.online:
        print("\nGitHub...")
        issues = _fetch_github("issues?state=open&per_page=5")
        if isinstance(issues, list):
            print(f"Open Issues: {len(issues)}")
            for item in issues[:5]:
                print(f"  - #{item.get('number')}: {item.get('title')}")
        releases = _fetch_github("releases?per_page=1")
        if isinstance(releases, list) and releases:
            rel = releases[0]
            tag = rel.get("tag_name", "?")
            pre = rel.get("prerelease", False)
            assets = [a.get("name") for a in rel.get("assets", [])]
            print(f"Latest release: {tag} (pre-release={pre})")
            if assets:
                print(f"  assets: {', '.join(assets)}")
            expected = f"v{config.VERSION.lstrip('v')}"
            if tag != expected:
                print(f"  [!] Тег на GitHub ({tag}) != config.VERSION ({expected})")
                ok = False

    print("\n---")
    if ok:
        print("Итог: OK — можно спокойно ждать feedback.")
        print("Дальше: docs/MAINTENANCE.md")
    else:
        print("Итог: есть замечания — см. выше.")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()

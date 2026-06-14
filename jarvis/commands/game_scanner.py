# game_scanner.py
"""
Опциональный поиск игр (Steam, Epic, папки Games).
Результат — превью для импорта в user_apps, не в общий apps_index.
"""

import json
import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Папки для эвристического поиска
COMMON_GAME_DIRS = (
    Path(r"C:\Games"),
    Path(r"D:\Games"),
    Path(r"E:\Games"),
    Path(r"C:\Program Files (x86)\Steam\steamapps\common"),
    Path(r"D:\SteamLibrary\steamapps\common"),
)

SKIP_EXE_NAMES = frozenset(
    {"uninstall.exe", "setup.exe", "launcher.exe", "redist.exe", "crashhandler.exe"}
)


@dataclass
class GameCandidate:
    """Найденная игра для превью-импорта."""

    display_name: str
    exe_path: str
    source: str  # steam | epic | folder_scan


# Парсит пути библиотек из libraryfolders.vdf (упрощённо, без полного VDF-парсера)
def _parse_steam_library_paths(vdf_path: Path) -> list[Path]:
    paths: list[Path] = []
    try:
        if not vdf_path.is_file():
            return paths
        text = vdf_path.read_text(encoding="utf-8", errors="replace")
        steam_root = vdf_path.parent.parent
        paths.append(steam_root / "common")

        for match in re.finditer(r'"path"\s+"([^"]+)"', text):
            raw = match.group(1).replace("\\\\", "\\")
            lib = Path(raw)
            common = lib / "steamapps" / "common"
            if common.is_dir():
                paths.append(common)
    except Exception as e:
        logger.warning("Ошибка чтения Steam VDF: %s", e)
    return paths


# Ищет главный .exe в папке игры Steam
def _find_main_exe(game_dir: Path) -> Path | None:
    try:
        exes = [p for p in game_dir.glob("*.exe") if p.name.lower() not in SKIP_EXE_NAMES]
        if not exes:
            for sub in game_dir.iterdir():
                if sub.is_dir():
                    exes.extend(
                        p for p in sub.glob("*.exe") if p.name.lower() not in SKIP_EXE_NAMES
                    )
        if not exes:
            return None
        # Предпочитаем exe с именем папки или самый короткий путь
        named = [e for e in exes if game_dir.name.lower() in e.stem.lower()]
        return (named or exes)[0]
    except Exception:
        return None


# Сканирует библиотеки Steam
def _scan_steam() -> list[GameCandidate]:
    found: list[GameCandidate] = []
    steam_vdf = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Steam" / "steamapps" / "libraryfolders.vdf"
    for common_dir in _parse_steam_library_paths(steam_vdf):
        if not common_dir.is_dir():
            continue
        try:
            for game_dir in common_dir.iterdir():
                if not game_dir.is_dir():
                    continue
                exe = _find_main_exe(game_dir)
                if exe:
                    found.append(
                        GameCandidate(
                            display_name=game_dir.name,
                            exe_path=str(exe.resolve()),
                            source="steam",
                        )
                    )
        except Exception as e:
            logger.warning("Ошибка сканирования %s: %s", common_dir, e)
    return found


# Сканирует манифесты Epic Games Launcher
def _scan_epic() -> list[GameCandidate]:
    found: list[GameCandidate] = []
    manifests_dir = Path(os.environ.get("ProgramData", r"C:\ProgramData")) / "Epic" / "EpicGamesLauncher" / "Data" / "Manifests"
    if not manifests_dir.is_dir():
        return found

    try:
        for manifest_file in manifests_dir.glob("*.item"):
            try:
                data = json.loads(manifest_file.read_text(encoding="utf-8", errors="replace"))
            except Exception:
                continue

            install_dir = data.get("InstallLocation") or data.get("ManifestLocation", "")
            launch_exe = data.get("LaunchExecutable", "")
            display = data.get("DisplayName") or data.get("AppName") or manifest_file.stem

            if not install_dir or not launch_exe:
                continue

            exe_path = Path(install_dir) / launch_exe
            if exe_path.is_file():
                found.append(
                    GameCandidate(
                        display_name=str(display),
                        exe_path=str(exe_path.resolve()),
                        source="epic",
                    )
                )
    except Exception as e:
        logger.warning("Ошибка сканирования Epic: %s", e)
    return found


# Сканирует типичные папки Games
def _scan_game_folders() -> list[GameCandidate]:
    found: list[GameCandidate] = []
    for base in COMMON_GAME_DIRS:
        if not base.is_dir():
            continue
        try:
            for item in base.iterdir():
                if not item.is_dir():
                    continue
                exe = _find_main_exe(item)
                if exe:
                    found.append(
                        GameCandidate(
                            display_name=item.name,
                            exe_path=str(exe.resolve()),
                            source="folder_scan",
                        )
                    )
        except Exception as e:
            logger.warning("Ошибка сканирования %s: %s", base, e)
    return found


# Убирает дубликаты по пути exe
def _dedupe(candidates: list[GameCandidate]) -> list[GameCandidate]:
    seen: set[str] = set()
    result: list[GameCandidate] = []
    for item in candidates:
        key = item.exe_path.lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return sorted(result, key=lambda c: c.display_name.lower())


# Полный скан игр для превью в GUI
def scan_games() -> list[GameCandidate]:
    try:
        all_found: list[GameCandidate] = []
        all_found.extend(_scan_steam())
        all_found.extend(_scan_epic())
        all_found.extend(_scan_game_folders())
        result = _dedupe(all_found)
        logger.info("Скан игр: найдено %s кандидатов", len(result))
        return result
    except Exception as e:
        logger.error("Ошибка scan_games: %s", e)
        return []

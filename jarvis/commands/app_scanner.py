# app_scanner.py
"""
Сканирование меню «Пуск» и UWP-приложений для голосового запуска программ.
"""

import json
import logging
import os
import re
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

import config

logger = logging.getLogger(__name__)

# Версия формата индекса — при изменении логики сканирования увеличить
INDEX_VERSION = 4

# Маркеры в запросе — не разбивать на однословные subtokens
DISAMBIGUATION_MARKERS = (
    "музык", "music", "store", "магазин", "spotify", "discord",
    "xbox", "warp", "cloudflare", "yandex", "яндекс", "microsoft",
)

# Запрещённые имена — не попадают в индекс и не открываются по голосу
BLACKLIST_NAMES = frozenset(
    {"cmd", "powershell", "pwsh", "regedit", "mmc", "taskkill"}
)

# Пропускаемые фрагменты в названиях ярлыков
SKIP_NAME_PARTS = (
    "uninstall",
    "удалить",
    "удаление",
    "documentation",
    "readme",
)

# Мусор STT — удаляется из запроса перед поиском
QUERY_STOP_WORDS = frozenset(
    {
        "запрет",
        "видео",
        "ему",
        "и",
        "тв",
        "youtube",
        "the",
        "a",
        "an",
        "на",
        "мне",
        "для",
        "проект",
    }
)

# Русские/искажённые названия → имя в индексе (одно- и многословные)
QUERY_ALIASES: dict[str, str] = {
    "дискорд": "discord",
    "стим": "steam",
    "телеграм": "telegram",
    "телеграмм": "telegram",
    "телега": "telegram",
    "хром": "chrome",
    "файрфокс": "firefox",
    "спотифай": "spotify",
    "spotify": "spotify",
    "влс": "vlc",
    "курсор": "cursor",
    "ванда": "riot client",
    "vanguard": "riot client",
    "вандр": "riot client",
    "riot": "riot client",
    "кино и тв": "movies tv",
    "кино тв": "movies tv",
    "microsoft store": "microsoft store",
    "магазин microsoft": "microsoft store",
    "магазин": "microsoft store",
    "xbox": "xbox",
    "obs": "obs studio",
    "абс": "obs studio",
    "abs studio": "obs studio",
    "abs": "obs studio",
    "плеер": "mumu player",
    "mumu": "mumu player",
    "муму": "mumu player",
    "му мну": "mumu player",
    "му-му": "mumu player",
    "cupcut": "capcut",
    "cap cut": "capcut",
    "capcut": "capcut",
    "яндекс музыка": "yandex music",
    "яндекс музыку": "yandex music",
    "yandex music": "yandex music",
    "варp": "cloudflare one client",
    "warp": "cloudflare one client",
    "wnd": "cloudflare one client",
    "cloudflare": "cloudflare one client",
    "wemod": "wemod",
    "wunder": "wemod",
    "vmods": "wemod",
    "v-моды": "wemod",
    "v моды": "wemod",
    "v-mod": "wemod",
    "v mod": "wemod",
    "ванны": "riot client",
    "ван-др": "riot client",
    "valorant": "valorant",
    "валорант": "valorant",
    "ea": "ea",
    "electronic arts": "ea",
    "hiddify": "hiddify",
    "hs proxy": "hiddify",
    "rockstar": "rockstar games launcher",
    "варп": "cloudflare one client",
}

# Если в запросе есть ключевое слово — результат должен его содержать
DISAMBIGUATION_RULES: tuple[tuple[tuple[str, ...], tuple[str, ...]], ...] = (
    (("store", "магазин"), ("store", "магазин")),
    (("xbox",), ("xbox",)),
    (("spotify", "спотифай"), ("spotify",)),
    (("discord", "дискорд"), ("discord",)),
    (("vanguard", "ванда", "вандр"), ("vanguard", "riot",)),
    (("музык", "music"), ("music", "музык")),
)

# Маркеры запроса Vanguard — открываем Riot Client, если установлен
VANGUARD_QUERY_MARKERS = frozenset(
    {
        "vanguard",
        "ванда",
        "вандр",
        "ванны",
        "ван-др",
        "ванн",
        "ванд",
        "троевандр",
    }
)

# Известные UWP по AppID — fallback, если скан не нашёл или имя испорчено кодировкой
KNOWN_UWP_BY_APPID: dict[str, tuple[str, str]] = {
    "yandex music": (
        r"shell:AppsFolder\A025C540.Yandex.Music_vfvw9svesycw6!App",
        "Yandex Music",
    ),
}
# Маркеры запроса WARP и ложные совпадения
WARP_QUERY_MARKERS = ("wnd", "warp", "варp", "cloudflare")
WARP_FALSE_POSITIVE_NAMES = ("wand", "wemod")

# Протоколы Windows для известных приложений, если их нет в индексе
KNOWN_APP_PROTOCOLS: dict[str, tuple[str, str]] = {
    "microsoft store": ("ms-windows-store:", "Microsoft Store"),
    "store": ("ms-windows-store:", "Microsoft Store"),
    "магазин": ("ms-windows-store:", "Microsoft Store"),
    "xbox": ("xbox:", "Xbox"),
    "кино и тв": ("ms-windows-store://pdp/?ProductId=9WZDNCRFJ3TJ", "Кино и ТВ"),
    "кино тв": ("ms-windows-store://pdp/?ProductId=9WZDNCRFJ3TJ", "Кино и ТВ"),
    "movies tv": ("ms-windows-store://pdp/?ProductId=9WZDNCRFJ3TJ", "Кино и ТВ"),
    "films tv": ("ms-windows-store://pdp/?ProductId=9WZDNCRFJ3TJ", "Кино и ТВ"),
}


@dataclass
class AppEntry:
    """Запись об установленном приложении."""

    display_name: str
    normalized_name: str
    launch_path: str
    source: str


# Нормализует имя для сравнения при поиске
def normalize_app_name(name: str) -> str:
    normalized = name.lower().replace("ё", "е")
    normalized = re.sub(r"[^\w\s]", " ", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


# Проверяет, нужно ли исключить приложение из индекса
def _is_blacklisted(display_name: str, normalized_name: str) -> bool:
    if not normalized_name:
        return True

    if normalized_name in BLACKLIST_NAMES:
        return True

    for part in normalized_name.split():
        if part in BLACKLIST_NAMES:
            return True

    lowered = display_name.lower()
    for skip_part in SKIP_NAME_PARTS:
        if skip_part in lowered or skip_part in normalized_name:
            return True

    return False


# Проверяет, нужно ли пропустить ярлык по имени файла
def _should_skip_shortcut(filename: str) -> bool:
    stem = filename[:-4] if filename.lower().endswith(".lnk") else filename
    if not stem.strip():
        return True

    lowered = stem.lower()
    for skip_part in SKIP_NAME_PARTS:
        if skip_part in lowered:
            return True

    if lowered.startswith("uninstall"):
        return True

    return False


# Возвращает папки меню «Пуск» для сканирования
def _get_start_menu_dirs() -> list[Path]:
    dirs: list[Path] = []

    try:
        program_data = os.environ.get("ProgramData", r"C:\ProgramData")
        dirs.append(Path(program_data) / r"Microsoft\Windows\Start Menu\Programs")

        app_data = os.environ.get("APPDATA", "")
        if app_data:
            dirs.append(Path(app_data) / r"Microsoft\Windows\Start Menu\Programs")
    except Exception as e:
        logger.error("Ошибка получения путей меню «Пуск»: %s", e)

    return dirs


# Сканирует ярлыки .lnk в меню «Пуск»
def _scan_start_menu_deduped() -> list[AppEntry]:
    seen: dict[str, AppEntry] = {}

    for start_dir in _get_start_menu_dirs():
        if not start_dir.is_dir():
            continue

        try:
            for lnk_path in start_dir.rglob("*.lnk"):
                if _should_skip_shortcut(lnk_path.name):
                    continue

                display_name = lnk_path.stem.strip()
                normalized_name = normalize_app_name(display_name)
                if _is_blacklisted(display_name, normalized_name):
                    continue

                entry = AppEntry(
                    display_name=display_name,
                    normalized_name=normalized_name,
                    launch_path=str(lnk_path.resolve()),
                    source="start_menu",
                )

                existing = seen.get(normalized_name)
                if existing is None or len(entry.launch_path) < len(existing.launch_path):
                    seen[normalized_name] = entry

        except Exception as e:
            logger.error("Ошибка сканирования %s: %s", start_dir, e)

    return list(seen.values())


# Сканирует UWP через PowerShell bridge (win_bridge.ps1)
def _scan_uwp_via_bridge() -> list[AppEntry] | None:
    try:
        from jarvis.core.sidecar_manager import SidecarManager

        data = SidecarManager.instance().powershell_call("list_start_apps")
        if not data.get("ok"):
            return None

        entries: list[AppEntry] = []
        for item in data.get("apps") or []:
            if not isinstance(item, dict):
                continue
            display_name = str(item.get("name", "")).strip()
            app_id = str(item.get("appId", "")).strip()
            if not display_name or not app_id:
                continue
            normalized_name = normalize_app_name(display_name)
            if _is_blacklisted(display_name, normalized_name):
                continue
            entries.append(
                AppEntry(
                    display_name=display_name,
                    normalized_name=normalized_name,
                    launch_path=f"shell:AppsFolder\\{app_id}",
                    source="uwp",
                )
            )
        logger.info("UWP через win_bridge: %s записей", len(entries))
        return entries
    except Exception as e:
        logger.debug("UWP bridge: %s", e)
        return None


# Сканирует UWP-приложения через PowerShell Get-StartApps (UTF-8)
def _scan_uwp_apps() -> list[AppEntry]:
    if not config.APP_SCAN_UWP:
        return []

    bridged = _scan_uwp_via_bridge()
    if bridged is not None:
        return bridged

    try:
        command = (
            "[Console]::OutputEncoding = [System.Text.Encoding]::UTF8; "
            "$OutputEncoding = [System.Text.Encoding]::UTF8; "
            "chcp 65001 | Out-Null; "
            "Get-StartApps | Where-Object { $_.Name -ne '' } | "
            "Select-Object Name, AppID | ConvertTo-Json -Compress -Depth 3"
        )
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", command],
            capture_output=True,
            text=True,
            timeout=30,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode != 0:
            logger.warning("PowerShell Get-StartApps завершился с кодом %s", result.returncode)
            return []

        raw_output = result.stdout.strip()
        if not raw_output:
            return []

        parsed = json.loads(raw_output)
        if isinstance(parsed, dict):
            parsed = [parsed]

        entries: list[AppEntry] = []
        for item in parsed:
            if not isinstance(item, dict):
                continue

            display_name = str(item.get("Name", "")).strip()
            app_id = str(item.get("AppID", "")).strip()
            if not display_name or not app_id:
                continue

            normalized_name = normalize_app_name(display_name)
            if _is_blacklisted(display_name, normalized_name):
                continue

            launch_path = f"shell:AppsFolder\\{app_id}"
            entries.append(
                AppEntry(
                    display_name=display_name,
                    normalized_name=normalized_name,
                    launch_path=launch_path,
                    source="uwp",
                )
            )

        logger.info("UWP-сканирование: %s записей", len(entries))
        return entries
    except Exception as e:
        logger.warning("Не удалось просканировать UWP-приложения: %s", e)
        return []


# Добавляет известные UWP из KNOWN_UWP_BY_APPID, если их нет или имя битое
def _inject_known_uwp_entries(entries: list[AppEntry]) -> list[AppEntry]:
    by_name: dict[str, AppEntry] = {entry.normalized_name: entry for entry in entries}

    for alias_key, (launch_path, display_name) in KNOWN_UWP_BY_APPID.items():
        normalized_key = normalize_app_name(alias_key)
        existing = by_name.get(normalized_key)

        needs_inject = existing is None or (
            existing.launch_path != launch_path
            or existing.display_name.strip().lower() != display_name.lower()
            or "�" in existing.display_name
            or "?" in existing.display_name
        )

        if needs_inject:
            by_name[normalized_key] = AppEntry(
                display_name=display_name,
                normalized_name=normalized_key,
                launch_path=launch_path,
                source="uwp",
            )
            logger.info("Добавлен fallback UWP: %s", display_name)

    return list(by_name.values())


# Объединяет записи из разных источников с дедупликацией
def _merge_entries(*sources: list[AppEntry]) -> list[AppEntry]:
    seen: dict[str, AppEntry] = {}

    for entries in sources:
        for entry in entries:
            existing = seen.get(entry.normalized_name)
            if existing is None or len(entry.launch_path) < len(existing.launch_path):
                seen[entry.normalized_name] = entry

    return list(seen.values())


# Сканирует приложения без использования кэша (для тестов)
def build_index() -> list[AppEntry]:
    try:
        lnk_entries = _scan_start_menu_deduped()
        uwp_entries = _scan_uwp_apps()
        entries = _merge_entries(lnk_entries, uwp_entries)
        entries = _inject_known_uwp_entries(entries)
        logger.info("Индекс приложений построен: %s записей", len(entries))
        return entries
    except Exception as e:
        logger.error("Ошибка построения индекса приложений: %s", e)
        return []


# Преобразует AppEntry в словарь для JSON
def _entry_to_dict(entry: AppEntry) -> dict[str, str]:
    return asdict(entry)


# Преобразует словарь из JSON в AppEntry
def _entry_from_dict(data: dict) -> AppEntry:
    return AppEntry(
        display_name=data["display_name"],
        normalized_name=data["normalized_name"],
        launch_path=data["launch_path"],
        source=data.get("source", "start_menu"),
    )


# Сохраняет индекс приложений на диск
def _save_index(entries: list[AppEntry]) -> None:
    try:
        config.ensure_data_dirs()
        payload = {
            "index_version": INDEX_VERSION,
            "scanned_at": datetime.now(timezone.utc).isoformat(),
            "apps": [_entry_to_dict(entry) for entry in entries],
        }
        with config.APP_INDEX_PATH.open("w", encoding="utf-8") as index_file:
            json.dump(payload, index_file, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error("Ошибка сохранения индекса приложений: %s", e)


# Загружает индекс из кэша, если он свежий
def _load_cached_index() -> Optional[list[AppEntry]]:
    try:
        if not config.APP_INDEX_PATH.is_file():
            return None

        with config.APP_INDEX_PATH.open("r", encoding="utf-8") as index_file:
            payload = json.load(index_file)

        if payload.get("index_version") != INDEX_VERSION:
            logger.info("Кэш индекса устарел (version %s != %s)", payload.get("index_version"), INDEX_VERSION)
            return None

        scanned_at_raw = payload.get("scanned_at")
        if not scanned_at_raw:
            return None

        scanned_at = datetime.fromisoformat(scanned_at_raw)
        if scanned_at.tzinfo is None:
            scanned_at = scanned_at.replace(tzinfo=timezone.utc)

        age_hours = (datetime.now(timezone.utc) - scanned_at).total_seconds() / 3600.0
        if age_hours > config.APP_INDEX_MAX_AGE_HOURS:
            logger.info("Кэш индекса приложений устарел (%.1f ч)", age_hours)
            return None

        apps_data = payload.get("apps", [])
        return [_entry_from_dict(item) for item in apps_data if isinstance(item, dict)]
    except Exception as e:
        logger.warning("Не удалось загрузить кэш индекса приложений: %s", e)
        return None


# Загружает индекс из кэша или пересканирует систему
def load_or_build_index(force_rescan: bool = False) -> list[AppEntry]:
    try:
        if not force_rescan:
            cached = _load_cached_index()
            if cached is not None:
                if config.APP_SCAN_UWP and sum(1 for e in cached if e.source == "uwp") == 0:
                    logger.info("В кэше нет UWP-записей — пересканирование")
                else:
                    logger.info("Загружен кэш индекса приложений (%s записей)", len(cached))
                    return _inject_known_uwp_entries(cached)

        entries = build_index()
        _save_index(entries)
        return entries
    except Exception as e:
        logger.error("Ошибка load_or_build_index: %s", e)
        return []


# Удаляет файл кэша индекса приложений
def delete_app_index() -> tuple[bool, str]:
    try:
        config.ensure_data_dirs()
        if not config.APP_INDEX_PATH.is_file():
            return False, "Файл индекса не найден"
        config.APP_INDEX_PATH.unlink()
        logger.info("Индекс приложений удалён: %s", config.APP_INDEX_PATH)
        return True, "Индекс приложений удалён"
    except Exception as e:
        logger.error("Ошибка delete_app_index: %s", e)
        return False, "Не удалось удалить индекс"


# Возвращает число записей в кэше без пересканирования
def get_cached_index_count() -> int:
    try:
        cached = _load_cached_index()
        if cached is not None:
            return len(cached)
        if not config.APP_INDEX_PATH.is_file():
            return 0
        with config.APP_INDEX_PATH.open("r", encoding="utf-8") as index_file:
            payload = json.load(index_file)
        apps_data = payload.get("apps", [])
        return len(apps_data) if isinstance(apps_data, list) else 0
    except Exception:
        return 0


# Возвращает имена приложений для initial_prompt Whisper
def get_top_app_names_for_prompt(limit: int) -> list[str]:
    try:
        entries = load_or_build_index()
        priority_keys = (
            "steam", "spotify", "discord", "chrome", "capcut", "ea", "warp",
            "cloudflare", "telegram", "cursor", "xbox", "valorant", "riot",
            "wemod", "yandex", "rockstar", "obs", "hiddify",
        )
        priority: list[str] = []
        rest: list[str] = []
        seen: set[str] = set()

        for entry in entries:
            name = entry.display_name.strip()
            if not name or name in seen:
                continue
            seen.add(name)
            if any(key in entry.normalized_name for key in priority_keys):
                priority.append(name)
            else:
                rest.append(name)

        return (priority + rest)[:limit]
    except Exception as e:
        logger.warning("Не удалось собрать имена для STT prompt: %s", e)
        return []


# Убирает глаголы открытия и мусор STT из запроса
def normalize_app_query(query: str) -> str:
    normalized = query.lower().replace("ё", "е")
    normalized = re.sub(
        r"\b(открой|открою|откроем|открыть|запусти|запуск|запустить|крой|крою|"
        r"пусти|грой|гроем|вруби|включи|включай|включить|строи|строй|"
        r"jarvis|джарвис|программу|программа|приложение|app)\b",
        " ",
        normalized,
    )
    normalized = re.sub(r"[^\w\s]", " ", normalized)
    words = [word for word in normalized.split() if word and word not in QUERY_STOP_WORDS]
    return re.sub(r"\s+", " ", " ".join(words)).strip()


# Извлекает значимые токены имени приложения из запроса
def extract_app_tokens(query: str, original_query: str | None = None) -> list[str]:
    normalized = normalize_app_query(query)
    original = normalize_app_query(original_query or query)
    if not normalized:
        return []

    words = [word for word in normalized.split() if word not in QUERY_STOP_WORDS and len(word) >= 2]
    if not words:
        return []

    candidates: list[str] = []
    full_query = " ".join(words)
    if full_query:
        candidates.append(full_query)

    original_words = [w for w in original.split() if w not in QUERY_STOP_WORDS and len(w) >= 2]
    original_full = " ".join(original_words)
    if original_full and original_full not in candidates:
        candidates.insert(0, original_full)

    has_marker = any(marker in original for marker in DISAMBIGUATION_MARKERS)
    multi_word = len(original_words) >= 2

    if not (multi_word and has_marker):
        for count in (3, 2, 1):
            if len(words) >= count:
                token = " ".join(words[-count:])
                if token not in candidates:
                    candidates.append(token)

        longest_word = max(words, key=len)
        if longest_word not in candidates:
            candidates.append(longest_word)

    return candidates


# Возвращает варианты запроса с учётом алиасов (включая фразы)
def resolve_query_variants(query: str) -> list[str]:
    variants: list[str] = []
    normalized = normalize_app_query(query)

    for candidate in (query.strip(), normalized):
        if candidate and candidate not in variants:
            variants.append(candidate)

    for alias_key, alias_value in sorted(QUERY_ALIASES.items(), key=lambda item: -len(item[0])):
        for candidate in list(variants):
            if candidate == alias_key or alias_key in candidate:
                if alias_value not in variants:
                    variants.append(alias_value)

    return variants


# Проверяет, есть ли в тексте известный алиас приложения
def matches_known_app_alias(text: str) -> bool:
    normalized = normalize_app_name(text)
    if not normalized:
        return False

    for alias_key in QUERY_ALIASES:
        if alias_key in normalized or normalized == alias_key:
            return True

    standalone_names = {
        "spotify", "steam", "discord", "capcut", "cupcut", "cursor",
        "telegram", "chrome", "firefox", "obs", "xbox", "wemod", "warp",
        "valorant", "hiddify", "ea", "rockstar", "yandex",
    }
    return any(word in standalone_names for word in normalized.split())


# Проверяет правила различения похожих приложений
def _passes_disambiguation(
    query: str,
    entry: AppEntry,
    original_query: str | None = None,
) -> bool:
    query_norm = normalize_app_name(original_query or query)
    name = entry.normalized_name

    if any(marker in query_norm for marker in WARP_QUERY_MARKERS):
        if any(false_name in name for false_name in WARP_FALSE_POSITIVE_NAMES):
            return False

    if any(token in query_norm for token in ("music", "музык")):
        if any(false_name in name for false_name in WARP_FALSE_POSITIVE_NAMES):
            return False
        if "browser" in name and "music" not in name and "музык" not in name:
            return False

    # v-mod / v mod — WeMod, не Python Module Docs
    if re.search(r"\bv[\s-]?mod", query_norm) or "wemod" in query_norm:
        if "python" in name and ("module" in name or "docs" in name):
            return False

    for required_in_query, required_in_name in DISAMBIGUATION_RULES:
        if any(token in query_norm for token in required_in_query):
            if query_norm == name:
                return True
            if not any(token in name for token in required_in_name):
                return False

    return True


# Считает оценку совпадения запроса с записью приложения
def _score_match(query: str, entry: AppEntry) -> float:
    name = entry.normalized_name
    if not query or not name:
        return 0.0

    if query == name:
        return 1.0

    query_words = [word for word in query.split() if word not in QUERY_STOP_WORDS]
    name_words = name.split()

    if len(query_words) >= 2:
        matched = 0
        for word in query_words:
            if word in name_words:
                matched += 1
                continue
            if any(word in name_word or name_word in word for name_word in name_words):
                matched += 1

        overlap = matched / len(query_words)
        ratio = SequenceMatcher(None, query, name).ratio()

        if overlap < 1.0:
            if overlap < 0.5:
                return ratio * 0.4
            return overlap * 0.75 + ratio * 0.15

        return 0.88 + min(0.12, overlap * 0.12)

    if query in name or name in query:
        shorter = min(len(query), len(name))
        longer = max(len(query), len(name))
        return 0.85 + 0.1 * (shorter / longer)

    return SequenceMatcher(None, query, name).ratio()


# Возвращает порог score в зависимости от числа слов в запросе
def _min_score_for_query(query: str, min_score: Optional[float]) -> float:
    if min_score is not None:
        return min_score

    word_count = len([word for word in query.split() if word not in QUERY_STOP_WORDS])
    if word_count >= 2:
        return config.APP_FUZZY_MIN_SCORE_MULTIWORD
    return config.APP_FUZZY_MIN_SCORE


# Ищет приложение в индексе по голосовому запросу
def find_app(
    query: str,
    index: list[AppEntry],
    min_score: Optional[float] = None,
    original_query: str | None = None,
) -> tuple[Optional[AppEntry], bool]:
    original = original_query or query
    candidate_queries: list[str] = []

    for token in extract_app_tokens(query, original_query=original):
        for variant in resolve_query_variants(token):
            if variant and variant not in candidate_queries:
                candidate_queries.append(variant)

    if not candidate_queries:
        return None, False

    best_entry: Optional[AppEntry] = None
    best_score = 0.0
    second_score = 0.0
    best_threshold = config.APP_FUZZY_MIN_SCORE

    for candidate_query in candidate_queries:
        threshold = _min_score_for_query(candidate_query, min_score)

        for entry in index:
            if _is_blacklisted(entry.display_name, entry.normalized_name):
                continue
            if not _passes_disambiguation(candidate_query, entry, original_query=original):
                continue

            score = _score_match(candidate_query, entry)
            if score > best_score:
                second_score = best_score
                best_score = score
                best_entry = entry
                best_threshold = threshold
            elif score > second_score:
                second_score = score

    if best_entry is None or best_score < best_threshold:
        return None, False

    if best_score >= 1.0:
        return best_entry, False

    if second_score >= best_threshold and (best_score - second_score) < 0.1:
        logger.warning(
            "Неоднозначный поиск приложения «%s»: %.2f vs %.2f",
            query,
            best_score,
            second_score,
        )
        return None, True

    return best_entry, False


# Запускает приложение по известному протоколу Windows
def try_launch_known_protocol(query: str) -> Optional[str]:
    try:
        normalized = normalize_app_query(query)
        candidates = resolve_query_variants(normalized or query)

        for candidate in candidates:
            for key, (protocol, display_name) in sorted(
                KNOWN_APP_PROTOCOLS.items(),
                key=lambda item: -len(item[0]),
            ):
                if candidate == key or key in candidate:
                    os.startfile(protocol)
                    logger.info("Запуск по протоколу: %s (%s)", display_name, protocol)
                    return f"Открываю {display_name}, сэр."
    except Exception as e:
        logger.error("Ошибка запуска по протоколу для «%s»: %s", query, e)

    return None


# Проверяет, относится ли запрос к Vanguard / Riot Client
def is_vanguard_query(query: str, original_query: str | None = None) -> bool:
    original = original_query or query
    texts = [query, original]

    for text in texts:
        if not text:
            continue
        norm = normalize_app_name(text)
        if any(marker in norm for marker in VANGUARD_QUERY_MARKERS):
            return True
        for variant in resolve_query_variants(text):
            if variant in ("riot client", "vanguard"):
                return True
            if any(marker in variant for marker in VANGUARD_QUERY_MARKERS):
                return True

    return False


# Открывает Riot Client по запросу Vanguard или сообщает об отсутствии
def try_resolve_vanguard(
    query: str,
    index: list[AppEntry],
    original_query: str | None = None,
) -> Optional[str]:
    if not is_vanguard_query(query, original_query):
        return None

    try:
        entry, ambiguous = find_app("riot client", index, original_query=original_query)
        if ambiguous:
            return "Уточните, какое приложение открыть, сэр."
        if entry:
            return launch_app(entry)
        logger.warning("Vanguard-запрос, но Riot Client не найден в индексе")
        return "Riot Client не установлен, сэр."
    except Exception as e:
        logger.error("Ошибка try_resolve_vanguard: %s", e)
        return "Riot Client не установлен, сэр."


# Запускает известное UWP по AppID (fallback для Yandex Music и др.)
def try_launch_known_uwp(query: str) -> Optional[str]:
    try:
        normalized = normalize_app_query(query)
        candidates = resolve_query_variants(normalized or query)

        for candidate in candidates:
            for key, (launch_path, display_name) in sorted(
                KNOWN_UWP_BY_APPID.items(),
                key=lambda item: -len(item[0]),
            ):
                if candidate == key or key in candidate:
                    os.startfile(launch_path)
                    logger.info("Запуск UWP по AppID: %s (%s)", display_name, launch_path)
                    return f"Открываю {display_name}, сэр."
    except Exception as e:
        logger.error("Ошибка запуска UWP по AppID для «%s»: %s", query, e)

    return None


# Запускает приложение через ярлык, UWP или shell-путь
def launch_app(entry: AppEntry) -> str:
    try:
        os.startfile(entry.launch_path)
        logger.info("Запущено приложение: %s (%s)", entry.display_name, entry.launch_path)
        return f"Открываю {entry.display_name}, сэр."
    except Exception as e:
        logger.error("Ошибка запуска %s: %s", entry.display_name, e)
        return f"Не удалось открыть {entry.display_name}, сэр."

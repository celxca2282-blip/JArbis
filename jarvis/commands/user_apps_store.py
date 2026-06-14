# user_apps_store.py
"""
Пользовательские ярлыки: программа (.exe), ссылка (url), папка.
Голосовые триггеры — как в Luxify, но с ручным контролем.
"""

import json
import logging
import os
import re
import subprocess
import uuid
import webbrowser
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import config

logger = logging.getLogger(__name__)

STORE_VERSION = 2

ACTION_EXE = "exe"
ACTION_URL = "url"
ACTION_FOLDER = "folder"
VALID_ACTIONS = frozenset({ACTION_EXE, ACTION_URL, ACTION_FOLDER})


@dataclass
class UserApp:
    """Пользовательский ярлык с голосовыми триггерами."""

    id: str
    display_name: str
    action_type: str = ACTION_EXE
    exe_path: str = ""
    working_dir: str = ""
    args: str = ""
    url: str = ""
    folder_path: str = ""
    voice_triggers: list[str] = field(default_factory=list)
    enabled: bool = True
    source: str = "manual"  # manual | game_scan
    created_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "UserApp":
        action_type = str(data.get("action_type", "")).strip().lower()
        if action_type not in VALID_ACTIONS:
            if data.get("url"):
                action_type = ACTION_URL
            elif data.get("folder_path"):
                action_type = ACTION_FOLDER
            else:
                action_type = ACTION_EXE

        return cls(
            id=str(data.get("id", "")),
            display_name=str(data.get("display_name", "")),
            action_type=action_type,
            exe_path=str(data.get("exe_path", "")),
            working_dir=str(data.get("working_dir", "")),
            args=str(data.get("args", "")),
            url=str(data.get("url", "")),
            folder_path=str(data.get("folder_path", "")),
            voice_triggers=list(data.get("voice_triggers", [])),
            enabled=bool(data.get("enabled", True)),
            source=str(data.get("source", "manual")),
            created_at=str(data.get("created_at", "")),
        )

    def target_label(self) -> str:
        """Текст цели для карточки в GUI."""
        if self.action_type == ACTION_URL:
            return self.url
        if self.action_type == ACTION_FOLDER:
            return self.folder_path
        return self.exe_path

    def type_label(self) -> str:
        return {"exe": "Программа", "url": "Ссылка", "folder": "Папка"}.get(self.action_type, "Ярлык")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_trigger(text: str) -> str:
    normalized = text.lower().replace("ё", "е")
    normalized = re.sub(r"[^\w\s]", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def validate_exe_path(exe_path: str) -> tuple[bool, str]:
    try:
        if not exe_path or not exe_path.strip():
            return False, "Укажите путь к .exe"
        path = Path(exe_path.strip())
        if not path.is_absolute():
            return False, "Путь должен быть абсолютным"
        if path.suffix.lower() != ".exe":
            return False, "Файл должен иметь расширение .exe"
        if not path.is_file():
            return False, "Файл не найден"
        return True, ""
    except Exception as e:
        logger.error("Ошибка валидации exe: %s", e)
        return False, "Некорректный путь"


def validate_url(url: str) -> tuple[bool, str]:
    try:
        raw = url.strip()
        if not raw:
            return False, "Укажите ссылку"
        if not raw.startswith(("http://", "https://")):
            raw = "https://" + raw
        parsed = urlparse(raw)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            return False, "Некорректный URL"
        return True, ""
    except Exception as e:
        logger.error("Ошибка валидации url: %s", e)
        return False, "Некорректная ссылка"


def validate_folder_path(folder_path: str) -> tuple[bool, str]:
    try:
        if not folder_path or not folder_path.strip():
            return False, "Укажите папку"
        path = Path(folder_path.strip())
        if not path.is_absolute():
            return False, "Путь должен быть абсолютным"
        if not path.is_dir():
            return False, "Папка не найдена"
        return True, ""
    except Exception as e:
        logger.error("Ошибка валидации папки: %s", e)
        return False, "Некорректный путь"


def _validate_shortcut_fields(
    action_type: str,
    exe_path: str = "",
    url: str = "",
    folder_path: str = "",
) -> tuple[bool, str]:
    if action_type == ACTION_EXE:
        return validate_exe_path(exe_path)
    if action_type == ACTION_URL:
        return validate_url(url)
    if action_type == ACTION_FOLDER:
        return validate_folder_path(folder_path)
    return False, "Неизвестный тип ярлыка"


def load_user_apps() -> list[UserApp]:
    try:
        config.ensure_data_dirs()
        if not config.USER_APPS_PATH.is_file():
            return []

        with config.USER_APPS_PATH.open("r", encoding="utf-8") as file:
            payload = json.load(file)

        apps_raw = payload.get("apps", [])
        return [UserApp.from_dict(item) for item in apps_raw if isinstance(item, dict)]
    except Exception as e:
        logger.error("Ошибка загрузки user_apps: %s", e)
        return []


def save_user_apps(apps: list[UserApp]) -> bool:
    try:
        config.ensure_data_dirs()
        payload = {"version": STORE_VERSION, "apps": [app.to_dict() for app in apps]}
        with config.USER_APPS_PATH.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error("Ошибка сохранения user_apps: %s", e)
        return False


def _build_triggers(voice_triggers: list[str]) -> tuple[list[str], str]:
    triggers = [_normalize_trigger(t) for t in voice_triggers if str(t).strip()]
    if not triggers:
        return [], "Добавьте хотя бы один голосовой триггер"
    return triggers, ""


def add_shortcut(
    display_name: str,
    action_type: str,
    voice_triggers: list[str],
    exe_path: str = "",
    url: str = "",
    folder_path: str = "",
    working_dir: str = "",
    args: str = "",
    enabled: bool = True,
    source: str = "manual",
) -> tuple[Optional[UserApp], str]:
    action_type = action_type.strip().lower()
    if action_type not in VALID_ACTIONS:
        return None, "Неверный тип ярлыка"

    valid, error = _validate_shortcut_fields(action_type, exe_path, url, folder_path)
    if not valid:
        return None, error

    if not display_name.strip():
        return None, "Укажите название"

    triggers, err = _build_triggers(voice_triggers)
    if err:
        return None, err

    if action_type == ACTION_URL and not url.strip().startswith(("http://", "https://")):
        url = "https://" + url.strip()

    app = UserApp(
        id=str(uuid.uuid4()),
        display_name=display_name.strip(),
        action_type=action_type,
        exe_path=str(Path(exe_path.strip()).resolve()) if exe_path else "",
        working_dir=working_dir.strip() or (str(Path(exe_path).parent) if exe_path else ""),
        args=args.strip(),
        url=url.strip(),
        folder_path=str(Path(folder_path.strip()).resolve()) if folder_path else "",
        voice_triggers=triggers,
        enabled=enabled,
        source=source,
        created_at=_now_iso(),
    )

    apps = load_user_apps()
    apps.append(app)
    if save_user_apps(apps):
        return app, ""
    return None, "Не удалось сохранить"


def add_app(
    display_name: str,
    exe_path: str,
    voice_triggers: list[str],
    working_dir: str = "",
    args: str = "",
    enabled: bool = True,
) -> tuple[Optional[UserApp], str]:
    """Совместимость: добавление .exe."""
    return add_shortcut(
        display_name,
        ACTION_EXE,
        voice_triggers,
        exe_path=exe_path,
        working_dir=working_dir,
        args=args,
        enabled=enabled,
    )


def update_app(app_id: str, **fields) -> tuple[Optional[UserApp], str]:
    apps = load_user_apps()
    for index, app in enumerate(apps):
        if app.id != app_id:
            continue

        if "action_type" in fields:
            app.action_type = str(fields["action_type"]).strip().lower()

        if "display_name" in fields and fields["display_name"].strip():
            app.display_name = fields["display_name"].strip()

        if "exe_path" in fields:
            app.exe_path = fields["exe_path"].strip()
        if "url" in fields:
            app.url = fields["url"].strip()
        if "folder_path" in fields:
            app.folder_path = fields["folder_path"].strip()
        if "working_dir" in fields:
            app.working_dir = fields["working_dir"].strip()
        if "args" in fields:
            app.args = fields["args"].strip()
        if "enabled" in fields:
            app.enabled = bool(fields["enabled"])
        if "source" in fields:
            app.source = str(fields["source"])

        if "voice_triggers" in fields:
            triggers, err = _build_triggers(fields["voice_triggers"])
            if err:
                return None, err
            app.voice_triggers = triggers

        valid, error = _validate_shortcut_fields(
            app.action_type, app.exe_path, app.url, app.folder_path
        )
        if not valid:
            return None, error

        if app.action_type == ACTION_EXE and app.exe_path:
            app.exe_path = str(Path(app.exe_path).resolve())
            if not app.working_dir:
                app.working_dir = str(Path(app.exe_path).parent)
        if app.action_type == ACTION_FOLDER and app.folder_path:
            app.folder_path = str(Path(app.folder_path).resolve())
        if app.action_type == ACTION_URL and app.url and not app.url.startswith(("http://", "https://")):
            app.url = "https://" + app.url

        apps[index] = app
        if save_user_apps(apps):
            return app, ""
        return None, "Не удалось сохранить"

    return None, "Ярлык не найден"


def delete_app(app_id: str) -> bool:
    apps = load_user_apps()
    new_apps = [app for app in apps if app.id != app_id]
    if len(new_apps) == len(apps):
        return False
    return save_user_apps(new_apps)


def count_scanned_apps() -> int:
    """Сколько ярлыков добавлено через скан игр."""
    return sum(1 for app in load_user_apps() if app.source == "game_scan")


def delete_scanned_apps() -> tuple[int, str]:
    """Удаляет все ярлыки с source=game_scan; ручные не трогает."""
    try:
        apps = load_user_apps()
        remaining = [app for app in apps if app.source != "game_scan"]
        removed = len(apps) - len(remaining)
        if removed == 0:
            return 0, "Нет ярлыков из скана игр"
        if save_user_apps(remaining):
            return removed, f"Удалено ярлыков из скана: {removed}"
        return 0, "Не удалось сохранить"
    except Exception as e:
        logger.error("Ошибка delete_scanned_apps: %s", e)
        return 0, "Ошибка удаления"


def count_manual_apps() -> int:
    """Сколько ярлыков добавлено вручную (не через скан игр)."""
    return sum(1 for app in load_user_apps() if app.source == "manual")


def delete_manual_apps() -> tuple[int, str]:
    """Удаляет все ручные ярлыки; импорт из скана игр не трогает."""
    try:
        apps = load_user_apps()
        remaining = [app for app in apps if app.source != "manual"]
        removed = len(apps) - len(remaining)
        if removed == 0:
            return 0, "Нет ручных ярлыков"
        if save_user_apps(remaining):
            return removed, f"Удалено ручных ярлыков: {removed}"
        return 0, "Не удалось сохранить"
    except Exception as e:
        logger.error("Ошибка delete_manual_apps: %s", e)
        return 0, "Ошибка удаления"


def get_app_by_id(app_id: str) -> Optional[UserApp]:
    for app in load_user_apps():
        if app.id == app_id:
            return app
    return None


def import_game_candidates(candidates: list, voice_prefix: str = "открой") -> tuple[int, str]:
    """Импортирует выбранные игры из game_scanner в user_apps."""
    from jarvis.commands.game_scanner import GameCandidate

    imported = 0
    existing_paths = {a.exe_path.lower() for a in load_user_apps() if a.exe_path}

    for item in candidates:
        if isinstance(item, GameCandidate):
            cand = item
        else:
            continue

        if cand.exe_path.lower() in existing_paths:
            continue

        trigger = _normalize_trigger(f"{voice_prefix} {cand.display_name}")
        _, err = add_shortcut(
            cand.display_name,
            ACTION_EXE,
            [trigger, _normalize_trigger(cand.display_name)],
            exe_path=cand.exe_path,
            source="game_scan",
        )
        if not err:
            imported += 1
            existing_paths.add(cand.exe_path.lower())

    return imported, f"Импортировано игр: {imported}"


def _trigger_score(text: str, trigger: str) -> float:
    if not text or not trigger:
        return 0.0
    if text == trigger:
        return 1.0
    if trigger in text or text in trigger:
        return 0.92
    return SequenceMatcher(None, text, trigger).ratio()


def find_by_voice(text: str, min_score: float = 0.82) -> Optional[UserApp]:
    try:
        normalized = _normalize_trigger(text)
        if not normalized:
            return None

        best_app: Optional[UserApp] = None
        best_score = 0.0

        for app in load_user_apps():
            if not app.enabled:
                continue
            for trigger in app.voice_triggers:
                score = _trigger_score(normalized, _normalize_trigger(trigger))
                if score > best_score:
                    best_score = score
                    best_app = app

        if best_app and best_score >= min_score:
            return best_app
        return None
    except Exception as e:
        logger.error("Ошибка find_by_voice: %s", e)
        return None


def launch_user_app(app: UserApp) -> str:
    try:
        if app.action_type == ACTION_URL:
            valid, error = validate_url(app.url)
            if not valid:
                return f"Не удалось открыть {app.display_name}: {error}"
            url = app.url if app.url.startswith(("http://", "https://")) else f"https://{app.url}"
            webbrowser.open(url)
            logger.info("Открыта ссылка: %s", app.display_name)
            return f"Открываю {app.display_name}, сэр."

        if app.action_type == ACTION_FOLDER:
            valid, error = validate_folder_path(app.folder_path)
            if not valid:
                return f"Не удалось открыть {app.display_name}: {error}"
            os.startfile(app.folder_path)
            logger.info("Открыта папка: %s", app.display_name)
            return f"Открываю папку {app.display_name}, сэр."

        valid, error = validate_exe_path(app.exe_path)
        if not valid:
            return f"Не удалось открыть {app.display_name}: {error}"

        cwd = app.working_dir or str(Path(app.exe_path).parent)
        args_list = app.args.split() if app.args.strip() else []
        subprocess.Popen([app.exe_path, *args_list], cwd=cwd, shell=False)
        logger.info("Запущена программа: %s", app.display_name)
        return f"Открываю {app.display_name}, сэр."
    except Exception as e:
        logger.error("Ошибка запуска ярлыка %s: %s", app.display_name, e)
        return f"Не удалось открыть {app.display_name}, сэр."

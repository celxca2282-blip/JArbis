# command_registry.py
"""
Единый реестр команд ассистента: whitelist, локальные триггеры, подсказки для LLM.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class SimpleCommandSpec:
    """Системная команда без URI (браузер, медиа, погода и т.д.)."""

    command_id: str
    description: str
    llm_hint: str
    local_phrases: tuple[str, ...] = ()
    fuzzy_keywords: tuple[str, ...] = ()
    needs_confirmation: bool = False
    is_control: bool = True


# Каталог точечных целей Windows
SYSTEM_TARGETS: dict[str, dict[str, str]] = {
    "settings": {
        "uri": "ms-settings:",
        "description": "настройки Windows",
        "response": "Открываю настройки Windows, сэр.",
    },
    "settings_wifi": {
        "uri": "ms-settings:wifi",
        "description": "настройки Wi‑Fi",
        "response": "Открываю настройки Wi‑Fi, сэр.",
    },
    "settings_bluetooth": {
        "uri": "ms-settings:bluetooth",
        "description": "настройки Bluetooth",
        "response": "Открываю настройки Bluetooth, сэр.",
    },
    "settings_display": {
        "uri": "ms-settings:display",
        "description": "настройки экрана",
        "response": "Открываю настройки экрана, сэр.",
    },
    "settings_sound": {
        "uri": "ms-settings:sound",
        "description": "настройки звука",
        "response": "Открываю настройки звука, сэр.",
    },
    "settings_privacy": {
        "uri": "ms-settings:privacy",
        "description": "настройки конфиденциальности",
        "response": "Открываю настройки конфиденциальности, сэр.",
    },
    "settings_apps": {
        "uri": "ms-settings:appsfeatures",
        "description": "настройки приложений",
        "response": "Открываю настройки приложений, сэр.",
    },
    "settings_personalization": {
        "uri": "ms-settings:personalization",
        "description": "настройки персонализации",
        "response": "Открываю настройки персонализации, сэр.",
    },
    "settings_update": {
        "uri": "ms-settings:windowsupdate",
        "description": "центр обновления Windows",
        "response": "Открываю центр обновления Windows, сэр.",
    },
    "settings_network": {
        "uri": "ms-settings:network",
        "description": "настройки сети",
        "response": "Открываю настройки сети, сэр.",
    },
    "settings_power": {
        "uri": "ms-settings:powersleep",
        "description": "настройки питания и сна",
        "response": "Открываю настройки питания и сна, сэр.",
    },
    "settings_storage": {
        "uri": "ms-settings:storage",
        "description": "настройки хранилища",
        "response": "Открываю настройки хранилища, сэр.",
    },
    "settings_datetime": {
        "uri": "ms-settings:dateandtime",
        "description": "настройки даты и времени",
        "response": "Открываю настройки даты и времени, сэр.",
    },
    "settings_notifications": {
        "uri": "ms-settings:notifications",
        "description": "настройки уведомлений",
        "response": "Открываю настройки уведомлений, сэр.",
    },
    "settings_troubleshoot": {
        "uri": "ms-settings:troubleshoot",
        "description": "устранение неполадок",
        "response": "Открываю средство устранения неполадок, сэр.",
    },
    "calculator": {
        "uri": "calc",
        "description": "калькулятор",
        "response": "Открываю калькулятор, сэр.",
    },
    "notepad": {
        "uri": "notepad",
        "description": "блокнот",
        "response": "Открываю блокнот, сэр.",
    },
    "paint": {
        "uri": "mspaint",
        "description": "Paint",
        "response": "Открываю Paint, сэр.",
    },
    "explorer": {
        "uri": "explorer",
        "description": "проводник",
        "response": "Открываю проводник, сэр.",
    },
    "cmd": {
        "uri": "cmd",
        "description": "командную строку",
        "response": "Открываю командную строку, сэр.",
    },
    "task_manager": {
        "uri": "taskmgr",
        "description": "диспетчер задач",
        "response": "Открываю диспетчер задач, сэр.",
    },
}

OPEN_COMMAND_TARGETS: dict[str, str] = {
    "open_settings": "settings",
    "open_settings_wifi": "settings_wifi",
    "open_settings_bluetooth": "settings_bluetooth",
    "open_settings_display": "settings_display",
    "open_settings_sound": "settings_sound",
    "open_settings_privacy": "settings_privacy",
    "open_settings_apps": "settings_apps",
    "open_settings_personalization": "settings_personalization",
    "open_settings_update": "settings_update",
    "open_settings_network": "settings_network",
    "open_settings_power": "settings_power",
    "open_settings_storage": "settings_storage",
    "open_settings_datetime": "settings_datetime",
    "open_settings_notifications": "settings_notifications",
    "open_settings_troubleshoot": "settings_troubleshoot",
    "open_calculator": "calculator",
    "open_notepad": "notepad",
    "open_paint": "paint",
    "open_explorer": "explorer",
    "open_cmd": "cmd",
    "open_task_manager": "task_manager",
}

_OPEN_LOCAL_PHRASES: dict[str, tuple[str, ...]] = {
    "open_settings_bluetooth": (
        "настройки bluetooth", "настройки блютуз", "открой bluetooth", "открой блютуз",
    ),
    "open_settings_wifi": (
        "настройки вайфай", "настройки wi fi", "настройки wifi", "настройки вай фай", "открой вайфай",
    ),
    "open_settings_sound": ("настройки звука", "настройки звук", "открой настройки звука"),
    "open_settings_display": ("настройки дисплея", "настройки экрана", "настройки display"),
    "open_settings_privacy": (
        "настройки конфиденциальности", "настройки приватности", "настройки privacy",
    ),
    "open_settings_apps": ("настройки приложений", "настройки apps", "настройки appsfeatures"),
    "open_settings_personalization": (
        "настройки персонализации", "настройки оформления", "настройки personalization",
    ),
    "open_settings_update": ("настройки обновления", "настройки windows update", "центр обновления"),
    "open_settings_network": ("настройки сети", "настройки network", "настройки интернета"),
    "open_settings_power": ("настройки питания", "настройки сна", "настройки powersleep"),
    "open_settings_storage": ("настройки памяти", "настройки хранилища", "настройки storage"),
    "open_settings_datetime": ("настройки даты", "настройки времени", "настройки dateandtime"),
    "open_settings_notifications": ("настройки уведомлений", "открой уведомления", "открою уведомления"),
    "open_settings_troubleshoot": (
        "устранение неполадок", "средство устранения неполадок", "открой устранение неполадок",
    ),
    "open_settings": ("открой настройки", "открыть настройки", "настройки windows", "системные настройки"),
    "open_calculator": ("открой калькулятор", "запусти калькулятор"),
    "open_notepad": ("открой блокнот", "запусти блокнот"),
    "open_paint": ("открой paint", "открой паинт", "запусти paint", "запусти паинт"),
    "open_explorer": ("открой проводник", "запусти проводник"),
    "open_cmd": ("открой cmd", "открой консоль", "командная строка", "терминал"),
    "open_task_manager": ("диспетчер задач", "открой диспетчер задач", "task manager"),
}

FUZZY_RULES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("уведомлен",), "open_settings_notifications"),
    (("неполад", "устранен", "troubleshoot"), "open_settings_troubleshoot"),
    (("wifi", "вай", "wi fi"), "open_settings_wifi"),
    (("bluetooth", "блюту"), "open_settings_bluetooth"),
    (("звук",), "open_settings_sound"),
    (("экран", "дисплей", "display"), "open_settings_display"),
    (("приложен", "appsfeatures"), "open_settings_apps"),
    (("персонал", "оформлен", "personalization"), "open_settings_personalization"),
    (("обновлен", "windowsupdate"), "open_settings_update"),
    (("настройки сети", "settings network"), "open_settings_network"),
    (("питани", "powersleep", "настройки сна"), "open_settings_power"),
    (("хранилищ", "storage"), "open_settings_storage"),
    (("dateandtime", "настройки даты", "настройки времени"), "open_settings_datetime"),
    (("конфиденциаль", "приватност", "privacy"), "open_settings_privacy"),
)

_OPEN_LLM_HINTS: dict[str, str] = {
    "open_settings": "главные настройки",
    "open_settings_wifi": "Wi‑Fi",
    "open_settings_bluetooth": "Bluetooth",
    "open_settings_display": "экран",
    "open_settings_sound": "звук",
    "open_settings_privacy": "конфиденциальность",
    "open_settings_apps": "приложения",
    "open_settings_personalization": "персонализация",
    "open_settings_update": "обновления Windows",
    "open_settings_network": "сеть",
    "open_settings_power": "питание и сон",
    "open_settings_storage": "хранилище",
    "open_settings_datetime": "дата и время",
    "open_settings_notifications": "уведомления",
    "open_settings_troubleshoot": "устранение неполадок",
    "open_calculator": "калькулятор",
    "open_notepad": "блокнот",
    "open_paint": "Paint",
    "open_explorer": "проводник",
    "open_cmd": "командная строка",
    "open_task_manager": "диспетчер задач",
}

SIMPLE_COMMANDS: tuple[SimpleCommandSpec, ...] = (
    SimpleCommandSpec(
        "open_browser",
        "браузер",
        "[EXEC:open_browser] — браузер",
        ("открой браузер", "запусти браузер", "открывай браузер"),
    ),
    SimpleCommandSpec(
        "lock_pc",
        "блокировка ПК",
        "[EXEC:lock_pc] — блокировка компьютера",
        ("заблокируй комп", "заблокируй систему", "заблокируй компьютер"),
        needs_confirmation=True,
    ),
    SimpleCommandSpec(
        "get_weather",
        "погода",
        "[EXEC:get_weather] — погода",
        fuzzy_keywords=("погод", "температур", "на улице"),
    ),
    SimpleCommandSpec(
        "media_play_pause",
        "пауза/воспроизведение",
        "[EXEC:media_play_pause] — пауза/воспроизведение",
        ("пауза", "ваузы", "паузы", "затушка", "поставь на паузу", "продолжи", "продолжен", "лей", "плей"),
    ),
    SimpleCommandSpec(
        "media_next",
        "следующий трек",
        "[EXEC:media_next] — следующий трек",
        ("следующий трек", "переключи песню", "включи следующий"),
    ),
    SimpleCommandSpec(
        "volume_mute",
        "выключить звук",
        "[EXEC:volume_mute] — выключить звук",
        ("выключи звук", "муте", "выключи музыку"),
    ),
    SimpleCommandSpec(
        "start_work",
        "рабочий сценарий",
        "10. Если пользователь просит «начать работу» — [EXEC:start_work].",
    ),
    SimpleCommandSpec(
        "open_app",
        "открыть программу из индекса",
        "[OPEN_APP:название] — открыть установленную программу (Discord, Steam и т.д.).",
        is_control=True,
    ),
)

LOCAL_SKILL_PHRASES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("очисти мою память", "забудь меня", "сотри профиль", "удали данные обо мне"), "clear_memory"),
    (("который час", "сколько времени", "какое время", "сколько сейчас времени"), "get_time"),
)

WORKFLOWS: dict[str, dict[str, object]] = {
    "start_work": {
        "description": "Запуск рабочего пространства",
        "apps": ["ms-settings:", "xbox:"],
        "sites": ["https://www.youtube.com", "https://mail.google.com", "https://funpay.com"],
    }
}

NEEDS_LOCK_CONFIRMATION = "__NEEDS_LOCK_CONFIRMATION__"


def get_allowed_command_ids() -> list[str]:
    ids = [cmd.command_id for cmd in SIMPLE_COMMANDS]
    ids.extend(OPEN_COMMAND_TARGETS.keys())
    ids.append("volume")
    return ids


def get_control_action_ids() -> set[str]:
    control_ids = {cmd.command_id for cmd in SIMPLE_COMMANDS if cmd.is_control}
    control_ids.update(OPEN_COMMAND_TARGETS.keys())
    control_ids.add("open_app")
    return control_ids


def get_local_triggers() -> tuple[tuple[tuple[str, ...], str], ...]:
    triggers: list[tuple[tuple[str, ...], str]] = []

    for command in SIMPLE_COMMANDS:
        if command.local_phrases:
            triggers.append((command.local_phrases, command.command_id))

    for command_id, phrases in _OPEN_LOCAL_PHRASES.items():
        triggers.append((phrases, command_id))

    triggers.extend(LOCAL_SKILL_PHRASES)
    return tuple(triggers)


def get_fuzzy_rules() -> tuple[tuple[tuple[str, ...], str], ...]:
    return FUZZY_RULES


def get_simple_command(command_id: str) -> Optional[SimpleCommandSpec]:
    for command in SIMPLE_COMMANDS:
        if command.command_id == command_id:
            return command
    return None


def build_llm_commands_section() -> str:
    lines = [
        "9. Доступные команды:",
        "[EXEC:open_browser], [EXEC:lock_pc], [EXEC:get_weather], [EXEC:media_play_pause],",
        "[EXEC:media_next], [EXEC:volume_mute], [EXEC:volume_X], где X — число от 0 до 100.",
    ]

    for command in SIMPLE_COMMANDS:
        if command.command_id == "start_work":
            lines.append(command.llm_hint)

    lines.append("11. Точечное открытие Windows (используй один подходящий тег):")
    for command_id in OPEN_COMMAND_TARGETS:
        hint = _OPEN_LLM_HINTS.get(command_id, command_id)
        lines.append(f"[EXEC:{command_id}] — {hint};")

    lines.append('Пример: «открой настройки bluetooth» → [EXEC:open_settings_bluetooth].')
    lines.extend([
        "18. Если пользователь просит открыть программу (Discord, Steam, Telegram, Cursor и т.д.), "
        "которой нет в списке open_settings_* / open_calculator, "
        "используй тег [OPEN_APP:название] — только латиница/английское имя (discord, spotify, cursor), "
        "без пути и без кириллицы. Пример: «открой дискорд» → [OPEN_APP:discord].",
        "19. Всегда оборачивай теги в квадратные скобки: [OPEN_APP:имя], [EXEC:...]. "
        "Без скобок тег не сработает.",
        "20. Для «открой X» всегда пробуй [OPEN_APP:...], никогда не отказывай («не могу открыть»).",
        "21. «плеер» / «му-му-плеер» / «mumu» → [OPEN_APP:mumu player], не [EXEC:media_play_pause].",
        "22. «ванда» / «vanguard» → [OPEN_APP:vanguard] или [OPEN_APP:riot client].",
        "23. Не выдумывай wmplayer, vlc и т.д., если пользователь назвал другое имя.",
        "24. Не используй [SEARCH:...] для открытия программ. "
        "Если пользователь просит открыть/запустить/включить программу — ТОЛЬКО [OPEN_APP:...]. "
        "ЗАПРЕЩЕНО [SEARCH:...] для таких запросов, даже если не знаешь приложение.",
        "25. Не выдумывай пути к .exe. Только [OPEN_APP:имя].",
        "26. «яндекс музыка» → [OPEN_APP:yandex music], не браузер. "
        "«capcut» / «cupcut» → [OPEN_APP:capcut]. "
        "WeMod → [OPEN_APP:wemod], Vanguard → [OPEN_APP:riot client].",
        "# Зарезервировано: [OPEN_URL:адрес] — не использовать.",
        "12. Запрещено вызывать команды, которых нет в списке выше. "
        "Не выдумывай имена вроде open_notifications.",
        "13. Запрос «открой X» в Windows — [EXEC:...] или [OPEN_APP:имя] для программ, никогда [SEARCH:...].",
        "14. При искажённом STT — выбери ближайшую команду из whitelist.",
        "15. [SAVE_MEMORY:...] только при «меня зовут», «я люблю», «запомни что».",
        "16. При неясном STT — один [EXEC:...], не несколько.",
        "17. Обращайся «сэр». Не используй имя из памяти без явного представления.",
        "Удаление долговременной памяти выполняется только локально, без участия ИИ.",
    ])
    return "\n".join(lines)

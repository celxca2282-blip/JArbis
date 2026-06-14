# scenario_store.py
"""
Хранилище пользовательских сценариев (цепочки действий).
"""

import json
import logging
import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any, Optional

import config

logger = logging.getLogger(__name__)

STORE_VERSION = 1


@dataclass
class ScenarioStep:
    """Один шаг сценария."""

    type: str
    path: str = ""
    args: str = ""
    url: str = ""
    query: str = ""
    command_id: str = ""
    user_app_id: str = ""
    delay_sec: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {key: value for key, value in asdict(self).items() if value or key == "type"}

    @classmethod
    def from_dict(cls, data: dict) -> "ScenarioStep":
        return cls(
            type=str(data.get("type", "delay")),
            path=str(data.get("path", "")),
            args=str(data.get("args", "")),
            url=str(data.get("url", "")),
            query=str(data.get("query", "")),
            command_id=str(data.get("command_id", "")),
            user_app_id=str(data.get("user_app_id", "")),
            delay_sec=float(data.get("delay_sec", 0)),
        )


@dataclass
class Scenario:
    """Сценарий с голосовыми триггерами и шагами."""

    id: str
    name: str
    description: str = ""
    voice_triggers: list[str] = field(default_factory=list)
    enabled: bool = True
    steps: list[ScenarioStep] = field(default_factory=list)
    stop_on_error: bool = False
    created_at: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "voice_triggers": self.voice_triggers,
            "enabled": self.enabled,
            "steps": [step.to_dict() for step in self.steps],
            "stop_on_error": self.stop_on_error,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Scenario":
        steps_raw = data.get("steps", [])
        steps = [ScenarioStep.from_dict(item) for item in steps_raw if isinstance(item, dict)]
        return cls(
            id=str(data.get("id", "")),
            name=str(data.get("name", "")),
            description=str(data.get("description", "")),
            voice_triggers=list(data.get("voice_triggers", [])),
            enabled=bool(data.get("enabled", True)),
            steps=steps,
            stop_on_error=bool(data.get("stop_on_error", False)),
            created_at=str(data.get("created_at", "")),
        )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# Нормализует текст триггера
def _normalize_trigger(text: str) -> str:
    normalized = text.lower().replace("ё", "е")
    normalized = re.sub(r"[^\w\s]", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


# Встроенный preset «Начать работу» при первом запуске
def _default_start_work_scenario() -> Scenario:
    return Scenario(
        id="preset-start-work",
        name="Начать работу",
        description="Рабочее пространство: настройки, Xbox, сайты",
        voice_triggers=["начать работу", "рабочий режим", "start work"],
        enabled=True,
        steps=[
            ScenarioStep(type="command", command_id="open_settings", delay_sec=0),
            ScenarioStep(type="url", url="https://www.youtube.com", delay_sec=1),
            ScenarioStep(type="url", url="https://mail.google.com", delay_sec=1),
            ScenarioStep(type="url", url="https://funpay.com", delay_sec=0),
        ],
        stop_on_error=False,
        created_at=_now_iso(),
    )


# Создаёт файл сценариев с preset, если его нет
def ensure_scenarios_file() -> None:
    try:
        config.ensure_data_dirs()
        if config.SCENARIOS_PATH.is_file():
            return
        save_scenarios([_default_start_work_scenario()])
        logger.info("Создан scenarios.json с preset «Начать работу»")
    except Exception as e:
        logger.error("Ошибка ensure_scenarios_file: %s", e)


# Загружает сценарии из JSON
def load_scenarios() -> list[Scenario]:
    try:
        ensure_scenarios_file()
        with config.SCENARIOS_PATH.open("r", encoding="utf-8") as file:
            payload = json.load(file)
        scenarios_raw = payload.get("scenarios", [])
        return [Scenario.from_dict(item) for item in scenarios_raw if isinstance(item, dict)]
    except Exception as e:
        logger.error("Ошибка загрузки scenarios: %s", e)
        return []


# Сохраняет сценарии в JSON
def save_scenarios(scenarios: list[Scenario]) -> bool:
    try:
        config.ensure_data_dirs()
        payload = {
            "version": STORE_VERSION,
            "scenarios": [scenario.to_dict() for scenario in scenarios],
        }
        with config.SCENARIOS_PATH.open("w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        logger.error("Ошибка сохранения scenarios: %s", e)
        return False


# Добавляет сценарий
def add_scenario(
    name: str,
    voice_triggers: list[str],
    steps: list[ScenarioStep],
    description: str = "",
    enabled: bool = True,
    stop_on_error: bool = False,
) -> tuple[Optional[Scenario], str]:
    if not name.strip():
        return None, "Укажите название сценария"

    triggers = [_normalize_trigger(t) for t in voice_triggers if t.strip()]
    if not triggers:
        return None, "Добавьте голосовые триггеры"

    if not steps:
        return None, "Добавьте хотя бы один шаг"

    scenario = Scenario(
        id=str(uuid.uuid4()),
        name=name.strip(),
        description=description.strip(),
        voice_triggers=triggers,
        enabled=enabled,
        steps=steps,
        stop_on_error=stop_on_error,
        created_at=_now_iso(),
    )

    scenarios = load_scenarios()
    scenarios.append(scenario)
    if save_scenarios(scenarios):
        return scenario, ""
    return None, "Не удалось сохранить"


# Обновляет сценарий
def update_scenario(scenario_id: str, **fields) -> tuple[Optional[Scenario], str]:
    scenarios = load_scenarios()
    for index, scenario in enumerate(scenarios):
        if scenario.id != scenario_id:
            continue

        if "name" in fields and fields["name"].strip():
            scenario.name = fields["name"].strip()
        if "description" in fields:
            scenario.description = fields["description"].strip()
        if "enabled" in fields:
            scenario.enabled = bool(fields["enabled"])
        if "stop_on_error" in fields:
            scenario.stop_on_error = bool(fields["stop_on_error"])
        if "voice_triggers" in fields:
            triggers = [_normalize_trigger(t) for t in fields["voice_triggers"] if str(t).strip()]
            if not triggers:
                return None, "Добавьте голосовые триггеры"
            scenario.voice_triggers = triggers
        if "steps" in fields:
            scenario.steps = fields["steps"]

        scenarios[index] = scenario
        if save_scenarios(scenarios):
            return scenario, ""
        return None, "Не удалось сохранить"

    return None, "Сценарий не найден"


# Удаляет сценарий
def delete_scenario(scenario_id: str) -> bool:
    scenarios = load_scenarios()
    new_list = [s for s in scenarios if s.id != scenario_id]
    if len(new_list) == len(scenarios):
        return False
    return save_scenarios(new_list)


# Возвращает сценарий по id или legacy-имени workflow
def get_scenario_by_id(scenario_id: str) -> Optional[Scenario]:
    for scenario in load_scenarios():
        if scenario.id == scenario_id:
            return scenario
    return None


def find_by_id_or_legacy_name(name: str) -> Optional[Scenario]:
    normalized = _normalize_trigger(name)
    for scenario in load_scenarios():
        if scenario.id == name or _normalize_trigger(scenario.name) == normalized:
            return scenario
    if normalized == "start_work" or normalized == "начать работу":
        for scenario in load_scenarios():
            if scenario.id == "preset-start-work":
                return scenario
    return None


# Считает score совпадения триггера
def _trigger_score(text: str, trigger: str) -> float:
    if text == trigger:
        return 1.0
    if trigger in text or text in trigger:
        return 0.92
    return SequenceMatcher(None, text, trigger).ratio()


# Ищет сценарий по голосовой фразе
def find_by_voice(text: str, min_score: float = 0.82) -> Optional[Scenario]:
    try:
        normalized = _normalize_trigger(text)
        if not normalized:
            return None

        best: Optional[Scenario] = None
        best_score = 0.0

        for scenario in load_scenarios():
            if not scenario.enabled:
                continue
            for trigger in scenario.voice_triggers:
                score = _trigger_score(normalized, _normalize_trigger(trigger))
                if score > best_score:
                    best_score = score
                    best = scenario

        if best and best_score >= min_score:
            return best
        return None
    except Exception as e:
        logger.error("Ошибка find_by_voice scenario: %s", e)
        return None

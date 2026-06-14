# scenario_runner.py
"""
Выполнение пользовательских сценариев по шагам.
"""

import logging
import os
import subprocess
import time
import webbrowser
from pathlib import Path

import jarvis.commands.app_scanner as app_scanner
import jarvis.commands.commands_module as commands_module
import jarvis.commands.scenario_store as scenario_store
import jarvis.commands.user_apps_store as user_apps_store
from jarvis.core.event_bus import EventBus, EventType

logger = logging.getLogger(__name__)


# Выполняет один шаг сценария
def _run_step(step: scenario_store.ScenarioStep, scenario_name: str) -> tuple[bool, str]:
    try:
        if step.type == "delay":
            time.sleep(max(0.0, step.delay_sec))
            return True, f"Пауза {step.delay_sec} сек."

        if step.type == "exe":
            path = Path(step.path)
            if not path.is_file():
                return False, f"EXE не найден: {step.path}"
            args = step.args.split() if step.args.strip() else []
            subprocess.Popen([str(path), *args], cwd=str(path.parent), shell=False)
            return True, f"Запущен {path.name}"

        if step.type == "url":
            if not step.url.strip():
                return False, "Пустой URL"
            webbrowser.open(step.url.strip())
            return True, f"Открыт URL: {step.url}"

        if step.type == "app_index":
            index = app_scanner.load_or_build_index()
            result, ambiguous = commands_module._resolve_and_launch_app(step.query, index)
            if ambiguous:
                return False, "Неоднозначное приложение в индексе"
            if result:
                return True, result
            return False, f"Приложение «{step.query}» не найдено"

        if step.type == "command":
            if not step.command_id:
                return False, "Не указана системная команда"
            result = commands_module.execute_system_command(step.command_id)
            if result is False:
                return False, f"Команда {step.command_id} не выполнена"
            if isinstance(result, str):
                return True, result
            return True, f"Команда {step.command_id} выполнена"

        if step.type == "user_app":
            app = user_apps_store.get_app_by_id(step.user_app_id)
            if not app:
                return False, "Пользовательское приложение не найдено"
            message = user_apps_store.launch_user_app(app)
            ok = "не удалось" not in message.lower()
            return ok, message

        return False, f"Неизвестный тип шага: {step.type}"
    except Exception as e:
        logger.error("Ошибка шага сценария %s: %s", scenario_name, e)
        return False, str(e)
    finally:
        if step.delay_sec > 0 and step.type != "delay":
            time.sleep(step.delay_sec)


# Запускает сценарий по id
def run_scenario(scenario_id: str, event_bus: EventBus | None = None) -> str:
    bus = event_bus or EventBus.instance()
    scenario = scenario_store.get_scenario_by_id(scenario_id)
    if not scenario:
        legacy = scenario_store.find_by_id_or_legacy_name(scenario_id)
        scenario = legacy
    if not scenario:
        return f"Сценарий «{scenario_id}» не найден, сэр."

    if not scenario.enabled:
        return f"Сценарий «{scenario.name}» отключён, сэр."

    logger.info("Запуск сценария: %s (%s шагов)", scenario.name, len(scenario.steps))
    errors: list[str] = []

    for index, step in enumerate(scenario.steps, start=1):
        bus.publish(
            EventType.SCENARIO_STEP_STARTED,
            {
                "scenario_id": scenario.id,
                "scenario_name": scenario.name,
                "step_index": index,
                "step_total": len(scenario.steps),
                "step_type": step.type,
            },
        )

        ok, message = _run_step(step, scenario.name)
        logger.info("Сценарий «%s» шаг %s/%s: %s — %s", scenario.name, index, len(scenario.steps), ok, message)

        if not ok:
            errors.append(message)
            if scenario.stop_on_error:
                bus.publish(
                    EventType.SCENARIO_COMPLETED,
                    {"scenario_id": scenario.id, "success": False, "errors": errors},
                )
                return f"Сценарий «{scenario.name}» остановлен: {message}"

    bus.publish(
        EventType.SCENARIO_COMPLETED,
        {"scenario_id": scenario.id, "success": len(errors) == 0, "errors": errors},
    )

    if errors:
        return f"Сценарий «{scenario.name}» завершён с ошибками: {'; '.join(errors)}"
    return f"Сценарий «{scenario.name}» выполнен. Всё готово, сэр."

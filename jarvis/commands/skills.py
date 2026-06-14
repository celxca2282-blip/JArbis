# skills.py
"""
Модуль навыков голосового ассистента.
Содержит функции, которые выполняют отдельные задачи по запросу пользователя.
"""

from datetime import datetime


# Возвращает текущее системное время в виде строки на русском языке
def get_time() -> str:
    try:
        now = datetime.now()
        hours = now.hour
        minutes = now.minute
        return f"Сейчас {hours} часов {minutes} минут"
    except Exception as e:
        print(f"Ошибка при получении времени: {e}")
        return "Не удалось получить текущее время."

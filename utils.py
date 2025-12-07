"""
Вспомогательные функции
"""
import re
from datetime import datetime
from typing import Tuple
import logging

logger = logging.getLogger(__name__)

def format_number(num: int) -> str:
    """Форматирование чисел с разделителями"""
    return f"{num:,}".replace(",", " ")

def format_date(date_str: str) -> str:
    """Форматирование даты"""
    try:
        if isinstance(date_str, str):
            date = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        else:
            date = date_str
        
        return date.strftime("%d.%m.%Y %H:%M")
    except:
        return "Неизвестно"

def format_timedelta(td) -> str:
    """Форматирование временного интервала"""
    try:
        days = td.days
        hours = td.seconds // 3600
        minutes = (td.seconds % 3600) // 60
        
        parts = []
        if days > 0:
            parts.append(f"{days}д")
        if hours > 0:
            parts.append(f"{hours}ч")
        if minutes > 0:
            parts.append(f"{minutes}м")
        
        return " ".join(parts) if parts else "менее минуты"
    except:
        return ""

def validate_nickname(nickname: str) -> Tuple[bool, str]:
    """Валидация никнейма"""
    if len(nickname) < 3:
        return False, "❌ Никнейм должен содержать минимум 3 символа"
    
    if len(nickname) > 20:
        return False, "❌ Никнейм не должен превышать 20 символов"
    
    # Проверка на недопустимые символы
    if not re.match(r'^[a-zA-Zа-яА-Я0-9 _\-]+$', nickname):
        return False, "❌ Никнейм может содержать только буквы, цифры, пробелы, дефисы и подчеркивания"
    
    # Проверка на запрещенные слова
    forbidden = ["admin", "админ", "moderator", "модератор"]
    if any(word in nickname.lower() for word in forbidden):
        return False, "❌ Никнейм содержит запрещенные слова"
    
    return True, "✅ Никнейм прошел проверку"

def is_admin(user_id: int, admin_ids: list) -> bool:
    """Проверка, является ли пользователь администратором"""
    return user_id in admin_ids

def check_daily_limit(user, limit_key='daily_tasks_count', limit_value=10):
    """Проверка дневного лимита"""
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Если последняя задача была не сегодня, сбрасываем счетчик
    if user.get('last_task_date') != today:
        return True, limit_value
    
    current_count = user.get(limit_key, 0)
    remaining = limit_value - current_count
    
    if current_count >= limit_value:
        return False, 0
    
    return True, remaining

def get_task_limit_text(task_type, user_data):
    """Получить текст о лимитах для типа задания"""
    from config import TASK_TYPES
    
    task_info = TASK_TYPES.get(task_type, {})
    max_per_day = task_info.get('max_per_day')
    
    if not max_per_day:
        return "безлимит"
    
    if task_type == 'regular_tasks':
        current = user_data.get('daily_regular_tasks', 0)
    else:
        current = user_data.get('daily_tasks_count', 0)
    
    return f"{current}/{max_per_day}"
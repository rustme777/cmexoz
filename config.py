"""
Конфигурация бота
"""
import os
import json
import logging

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Получение переменных окружения
def get_env_variable(name, default=None, required=False):
    """Получить переменную окружения"""
    value = os.environ.get(name, default)
    
    if required and not value:
        logger.error(f"❌ Переменная окружения {name} не установлена!")
        raise ValueError(f"Переменная {name} обязательна")
    
    return value

# Основные настройки
BOT_TOKEN = get_env_variable("BOT_TOKEN", required=True)
ADMIN_IDS = json.loads(get_env_variable("ADMIN_IDS", "[]"))

# Настройки Railway
PORT = int(get_env_variable("PORT", "8080"))
RAILWAY_STATIC_URL = get_env_variable("RAILWAY_STATIC_URL", "")
WEBHOOK_MODE = get_env_variable("WEBHOOK_MODE", "false").lower() == "true"

# Определяем URL вебхука
if WEBHOOK_MODE and RAILWAY_STATIC_URL:
    WEBHOOK_URL = f"{RAILWAY_STATIC_URL}/{BOT_TOKEN}"
    logger.info(f"🌐 Используется Webhook: {WEBHOOK_URL}")
else:
    WEBHOOK_URL = None
    logger.info("🔄 Используется Polling режим")

# Настройки базы данных
DB_PATH = "bot_database.db"

# Лимиты
DAILY_TASK_LIMIT = 10
DAILY_REGULAR_TASK_LIMIT = 10

# Типы заданий
TASK_TYPES = {
    "contracts": {
        "name": "Контракты",
        "emoji": "📜",
        "points": 5,
        "description": "Выполнение контрактов в игре",
        "requires_screenshot": True,
        "max_per_submission": 16,
        "max_per_day": None  # безлимит
    },
    "regular_tasks": {
        "name": "Задания",
        "emoji": "✅",
        "points": 5,
        "description": "Выполнение обычных заданий",
        "requires_screenshot": True,
        "max_per_submission": 10,
        "max_per_day": 10  # лимит 10 в день
    },
    "woodcutting": {
        "name": "Вырубка леса",
        "emoji": "🌳",
        "points": 5,
        "description": "Вырубка деревьев",
        "requires_screenshot": True,
        "max_per_submission": 10,
        "max_per_day": None
    },
    "help_newbies": {
        "name": "Помощь новичкам",
        "emoji": "🆘",
        "points": 5,
        "description": "Помощь новичкам деньгами",
        "requires_screenshot": True,
        "max_per_submission": 5,
        "max_per_day": None
    }
}

# Значки
BADGES = {
    "star": {"emoji": "⭐", "name": "Звезда", "description": "Выдано администратором"},
    "crown": {"emoji": "👑", "name": "Король", "description": "Лидер сообщества"},
    "fire": {"emoji": "🔥", "name": "Огненный", "description": "Невероятная активность"},
    "diamond": {"emoji": "💎", "name": "Алмаз", "description": "Ценный участник"},
    "rocket": {"emoji": "🚀", "name": "Ракета", "description": "Быстрый рост"},
    "heart": {"emoji": "❤️", "name": "Доброе сердце", "description": "Помощь другим"},
    "trophy": {"emoji": "🏆", "name": "Чемпион", "description": "Победитель розыгрышей"}
}
"""
Модуль клавиатур
"""
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton
from config import TASK_TYPES

def create_user_keyboard():
    """Основная клавиатура пользователя"""
    keyboard = [
        [KeyboardButton("🎮 Отправить задание")],
        [KeyboardButton("📊 Мой профиль"), KeyboardButton("🏆 Топ игроков")],
        [KeyboardButton("📋 Мои задания"), KeyboardButton("🎰 Розыгрыши")],
        [KeyboardButton("❓ Помощь"), KeyboardButton("⚙️ Настройки")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def create_admin_keyboard():
    """Клавиатура администратора"""
    keyboard = [
        [KeyboardButton("📋 Проверить задания"), KeyboardButton("👥 Участники")],
        [KeyboardButton("🎰 Управление розыгрышами"), KeyboardButton("📊 Статистика")],
        [KeyboardButton("📢 Рассылка"), KeyboardButton("🔙 В меню")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def create_task_types_keyboard():
    """Клавиатура выбора типа задания"""
    keyboard = []
    
    for task_id, task_info in TASK_TYPES.items():
        keyboard.append([
            InlineKeyboardButton(
                f"{task_info['emoji']} {task_info['name']}",
                callback_data=f"task_select_{task_id}"
            )
        ])
    
    keyboard.append([
        InlineKeyboardButton("❓ Помощь", callback_data="task_help"),
        InlineKeyboardButton("❌ Отмена", callback_data="task_cancel")
    ])
    
    return InlineKeyboardMarkup(keyboard)

def create_main_menu_keyboard():
    """Главное меню inline-клавиатура"""
    keyboard = [
        [InlineKeyboardButton("🎮 Отправить задание", callback_data="new_task")],
        [InlineKeyboardButton("📊 Мой профиль", callback_data="profile")],
        [InlineKeyboardButton("🏆 Топ игроков", callback_data="top")],
        [InlineKeyboardButton("🎰 Активные розыгрыши", callback_data="drawings")],
        [InlineKeyboardButton("❓ Помощь", callback_data="help")]
    ]
    return InlineKeyboardMarkup(keyboard)

def create_back_to_menu_keyboard():
    """Кнопка возврата в меню"""
    keyboard = [[InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu")]]
    return InlineKeyboardMarkup(keyboard)

def create_confirmation_keyboard():
    """Клавиатура подтверждения"""
    keyboard = [
        [
            InlineKeyboardButton("✅ Да, отправляю", callback_data="confirm_screenshot"),
            InlineKeyboardButton("⏭️ Пропустить", callback_data="skip_screenshot")
        ],
        [InlineKeyboardButton("❌ Отмена", callback_data="task_cancel")]
    ]
    return InlineKeyboardMarkup(keyboard)

def create_drawings_list_keyboard(drawings):
    """Список розыгрышей"""
    keyboard = []
    
    for drawing in drawings[:5]:
        keyboard.append([
            InlineKeyboardButton(
                f"🎰 {drawing['name'][:20]}",
                callback_data=f"drawing_view_{drawing['drawing_id']}"
            )
        ])
    
    keyboard.append([InlineKeyboardButton("🔙 Назад", callback_data="back_to_menu")])
    return InlineKeyboardMarkup(keyboard)
# ========== СИСТЕМА ЗАДАНИЙ ==========

async def start_task_submission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало отправки задания"""
    user = update.effective_user
    user_data = db.get_user(user.id)
    
    # Проверка бана
    if user_data and user_data.get('is_banned'):
        await update.message.reply_text(
            f"🚫 <b>Вы заблокированы!</b>\n\nПричина: {user_data.get('ban_reason', 'не указана')}",
            parse_mode='HTML'
        )
        return ConversationHandler.END
    
    # Проверка дневного лимита заданий
    can_send, remaining = check_daily_limit(user_data or {}, 'daily_tasks_count', 10)
    
    if not can_send:
        await update.message.reply_text(
            "📊 <b>ДНЕВНОЙ ЛИМИТ ИСЧЕРПАН</b>\n\n"
            "Вы уже отправили 10 заданий сегодня.\n"
            "🔄 Лимит сбросится в 00:00 по МСК",
            parse_mode='HTML'
        )
        return ConversationHandler.END
    
    text = f"""
🎮 <b>ОТПРАВКА ЗАДАНИЯ</b>

Выберите тип задания из списка:

📊 <b>Лимиты на сегодня:</b>
• Осталось заданий: {remaining}/10
• Обычные задания: {user_data.get('daily_regular_tasks', 0) if user_data else 0}/10

🎯 <b>Выберите тип задания:</b>
    """
    
    await update.message.reply_text(
        text,
        parse_mode='HTML',
        reply_markup=create_task_types_keyboard()
    )
    
    return TASK_SELECT

async def select_task_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выбор типа задания"""
    query = update.callback_query
    await query.answer()
    
    task_type = query.data.replace("task_select_", "")
    task_info = TASK_TYPES.get(task_type)
    
    if not task_info:
        await query.edit_message_text("❌ Неизвестный тип задания!")
        return ConversationHandler.END
    
    # Сохраняем в контекст
    context.user_data['task_type'] = task_type
    context.user_data['task_info'] = task_info
    
    # Форматируем лимиты
    max_per_day = task_info.get('max_per_day')
    limit_text = f"{max_per_day}/день" if max_per_day else "безлимит"
    
    text = f"""
🎮 <b>ТИП ЗАДАНИЯ:</b> {task_info['emoji']} {task_info['name']}

📝 <b>Описание:</b> {task_info['description']}
💰 <b>Баллов за единицу:</b> {task_info['points']}
📊 <b>Максимум за отправку:</b> {task_info.get('max_per_submission', 'безлимит')}
📋 <b>Дневной лимит:</b> {limit_text}

✏️ <b>Сколько раз вы выполнили это задание?</b>
Введите число от 1 до {task_info.get('max_per_submission', 100)}:
    """
    
    await query.edit_message_text(text, parse_mode='HTML')
    return TASK_COUNT

async def process_task_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка количества"""
    try:
        count = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ Пожалуйста, введите число!")
        return TASK_COUNT
    
    task_info = context.user_data.get('task_info')
    max_count = task_info.get('max_per_submission', 100)
    
    if count < 1:
        await update.message.reply_text("❌ Количество должно быть не менее 1!")
        return TASK_COUNT
    
    if count > max_count:
        await update.message.reply_text(f"❌ Максимальное количество: {max_count}!")
        return TASK_COUNT
    
    # Для обычных заданий проверяем дневной лимит
    if context.user_data['task_type'] == 'regular_tasks':
        user = db.get_user(update.effective_user.id)
        daily_regular = user.get('daily_regular_tasks', 0)
        max_per_day = task_info.get('max_per_day', 10)
        
        if daily_regular + count > max_per_day:
            available = max_per_day - daily_regular
            await update.message.reply_text(
                f"❌ Превышен дневной лимит!\n"
                f"Выполнено сегодня: {daily_regular}/{max_per_day}\n"
                f"Доступно еще: {available}",
                parse_mode='HTML'
            )
            return TASK_COUNT
    
    context.user_data['task_count'] = count
    
    # Если требуется скриншот
    if task_info.get('requires_screenshot', True):
        text = """
📸 <b>СКРИНШОТ ЗАДАНИЯ</b>

Пожалуйста, отправьте скриншот, подтверждающий выполнение задания.

💡 <b>Требования к скриншоту:</b>
• Должен быть четким и читаемым
• Должен подтверждать выполнение задания
• Формат: JPG, PNG (до 10 МБ)

📎 <b>Отправьте скриншот или нажмите "Пропустить":</b>
        """
        
        await update.message.reply_text(
            text,
            parse_mode='HTML',
            reply_markup=create_confirmation_keyboard()
        )
        return TASK_SCREENSHOT
    else:
        # Если скриншот не требуется, переходим к комментарию
        context.user_data['task_screenshot'] = None
        return await ask_for_comment(update, context)

async def process_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка комментария и завершение отправки"""
    comment = update.message.text.strip()
    
    if comment.lower() == 'пропустить':
        comment = ''
    
    # Сохраняем задание в БД
    user_id = update.effective_user.id
    task_type = context.user_data['task_type']
    task_info = context.user_data['task_info']
    count = context.user_data['task_count']
    screenshot = context.user_data.get('task_screenshot')
    
    # Создаем задание
    task_data = {
        'user_id': user_id,
        'task_type': task_type,
        'points': task_info['points'],
        'count': count,
        'screenshot_path': screenshot,
        'comment': comment,
        'status': 'pending'
    }
    
    task_id = db.create_task(task_data)
    
    # Обновляем дневной счетчик для обычных заданий
    if task_type == 'regular_tasks':
        db.update_daily_counter(user_id, task_type, count)
    
    total_points = task_info['points'] * count
    
    text = f"""
✅ <b>ЗАДАНИЕ ОТПРАВЛЕНО НА ПРОВЕРКУ!</b>

🎮 <b>Тип задания:</b> {task_info['emoji']} {task_info['name']}
📊 <b>Количество:</b> {count} выполнений
💰 <b>Баллов:</b> {task_info['points']} × {count} = {format_number(total_points)}
🆔 <b>Номер задания:</b> #{task_id}

⏳ <b>Время проверки:</b> до 24 часов
📝 <b>Статус:</b> отправлено на модерацию

✨ <b>Следите за уведомлениями!</b>
Администратор проверит ваше задание и начислит баллы.
    """
    
    await update.message.reply_text(
        text,
        parse_mode='HTML',
        reply_markup=create_back_to_menu_keyboard()
    )
    
    # Очищаем контекст
    context.user_data.clear()
    
    return ConversationHandler.END

# ========== АДМИН КОМАНДЫ ==========

async def admin_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Панель администратора"""
    user = update.effective_user
    
    if not is_admin(user.id, ADMIN_IDS):
        await update.message.reply_text("⛔ У вас нет прав администратора!")
        return
    
    # Получаем статистику
    pending_tasks = len(db.get_pending_tasks())
    top_users = db.get_top_users(5)
    drawings = len(db.get_active_drawings())
    
    text = f"""
👑 <b>ПАНЕЛЬ АДМИНИСТРАТОРА</b>

Добро пожаловать, {user.first_name}!

📊 <b>Общая статистика:</b>
• Заданий на проверке: {pending_tasks}
• Активных розыгрышей: {drawings}
• Топ-5 участников: {len(top_users)}

👥 <b>Топ участников:</b>
"""
    
    for i, user_data in enumerate(top_users[:3], 1):
        nickname = user_data['nickname']
        points = user_data['total_points']
        text += f"{i}. {nickname} - {points} баллов\n"
    
    text += "\n🚀 <b>Используйте кнопки ниже для управления:</b>"
    
    await update.message.reply_text(
        text,
        parse_mode='HTML',
        reply_markup=create_admin_keyboard()
    )

async def check_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверка заданий"""
    user = update.effective_user
    
    if not is_admin(user.id, ADMIN_IDS):
        await update.message.reply_text("⛔ У вас нет прав администратора!")
        return
    
    pending_tasks = db.get_pending_tasks(limit=10)
    
    if not pending_tasks:
        text = """
✅ <b>ПРОВЕРКА ЗАДАНИЙ</b>

📭 На данный момент нет заданий на проверке.

🎯 <b>Что можно сделать:</b>
• Проверить статистику участников
• Создать новый розыгрыш
• Отправить рассылку участникам
"""
        keyboard = create_back_to_menu_keyboard()
    else:
        text = f"""
✅ <b>ПРОВЕРКА ЗАДАНИЙ</b>

📋 Заданий на проверке: {len(pending_tasks)}

<b>📝 Последние задания:</b>
"""
        
        for task in pending_tasks[:3]:
            task_info = TASK_TYPES.get(task['task_type'], {'name': task['task_type'], 'emoji': '📝'})
            nickname = task.get('nickname') or task.get('username') or f"User_{task['user_id']}"
            created_at = format_date(task['created_at'])
            
            text += f"\n<b>{task_info['emoji']} {task_info['name']}</b>"
            text += f"\n👤 {nickname}"
            text += f"\n🎯 Баллов: {task['points']} × {task.get('count', 1)} = {task['points'] * task.get('count', 1)}"
            text += f"\n📅 {created_at}"
            text += f"\n{'─' * 25}"
        
        if len(pending_tasks) > 3:
            text += f"\n\n<i>...и еще {len(pending_tasks) - 3} заданий</i>"
        
        # Кнопки для проверки
        keyboard = []
        for task in pending_tasks[:5]:
            task_info = TASK_TYPES.get(task['task_type'], {'name': task['task_type'][:10]})
            keyboard.append([
                InlineKeyboardButton(
                    f"👤 {task['task_id']} | {task_info['name'][:15]}",
                    callback_data=f"admin_review_task_{task['task_id']}"
                )
            ])
        
        keyboard.append([
            InlineKeyboardButton("🔄 Обновить", callback_data="admin_refresh_tasks"),
            InlineKeyboardButton("🔙 Назад", callback_data="admin_back_to_dashboard")
        ])
        keyboard = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        text,
        parse_mode='HTML',
        reply_markup=keyboard
    )

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /profile"""
    user = update.effective_user
    user_data = db.get_user(user.id)
    
    if not user_data:
        await update.message.reply_text("❌ Профиль не найден!")
        return
    
    # Получаем статистику
    tasks = db.get_user_tasks(user.id)
    completed = len([t for t in tasks if t['status'] == 'approved'])
    pending = len([t for t in tasks if t['status'] == 'pending'])
    
    text = f"""
👤 <b>ПРОФИЛЬ</b>

📝 <b>Никнейм:</b> {user_data['nickname']}
💰 <b>Баллы:</b> {format_number(user_data['total_points'])}
📅 <b>В системе:</b> с {format_date(user_data['join_date'])}

📊 <b>Статистика заданий:</b>
✅ Выполнено: {completed}
⏳ На проверке: {pending}

🎯 <b>Лимиты сегодня:</b>
📋 Всего заданий: {user_data.get('daily_tasks_count', 0)}/{10}
✅ Обычные задания: {user_data.get('daily_regular_tasks', 0)}/{10}

🚀 <b>Продолжайте в том же духе!</b>
    """
    
    await update.message.reply_text(text, parse_mode='HTML')
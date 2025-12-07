#!/usr/bin/env python3
"""
Telegram Task Bot PRO - Полная система с админ-панелью и розыгрышами
Версия: 5.0 (С системой розыгрышей)
"""

import logging
import os
import json
import asyncio
import aiohttp
import aiofiles
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Tuple, Any, Union
from functools import wraps
import hashlib
import pickle
import gzip
from dataclasses import dataclass, asdict
from enum import Enum
import random
import string
from pathlib import Path
import re
import time
from collections import defaultdict

import redis.asyncio as redis
from telegram import (
    Update, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardRemove,
    InputMediaPhoto,
    BotCommand,
    WebAppInfo
)
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ConversationHandler,
    filters,
    ContextTypes,
    JobQueue,
    CallbackContext,
    PicklePersistence
)
from telegram.constants import ParseMode, ChatAction
from telegram.error import TelegramError, NetworkError, RetryAfter

# ========== КОНФИГУРАЦИЯ ==========
# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = json.loads(os.getenv("ADMIN_IDS", "[]"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "")
WEBHOOK_PORT = int(os.getenv("PORT", "8080"))

# Директории
for dir_path in ["screenshots", "cache", "drawings", "avatars", "reports", "prizes"]:
    os.makedirs(dir_path, exist_ok=True)

# ========== СИСТЕМА БЕЙДЖЕЙ ==========
BADGES = {
    # Основные достижения
    "star": {"emoji": "⭐", "name": "Звезда", "description": "Выдано администратором за выдающиеся заслуги"},
    "crown": {"emoji": "👑", "name": "Король", "description": "Лидер сообщества"},
    "fire": {"emoji": "🔥", "name": "Огненный", "description": "Невероятная активность"},
    "rocket": {"emoji": "🚀", "name": "Ракета", "description": "Быстрый рост"},
    "diamond": {"emoji": "💎", "name": "Алмаз", "description": "Ценный участник"},
    "heart": {"emoji": "❤️", "name": "Доброе сердце", "description": "Помощь другим"},
    "brain": {"emoji": "🧠", "name": "Гений", "description": "Умные решения"},
    "shield": {"emoji": "🛡️", "name": "Защитник", "description": "Защита сообщества"},
    "trophy": {"emoji": "🏆", "name": "Чемпион", "description": "Победы в розыгрышах"},
    "medal": {"emoji": "🎖️", "name": "Медалист", "description": "Высокие достижения"},
    
    # Сезонные
    "snowman": {"emoji": "⛄", "name": "Снеговик", "description": "Зимний чемпион"},
    "sun": {"emoji": "☀️", "name": "Солнышко", "description": "Летний победитель"},
    "leaf": {"emoji": "🍁", "name": "Осенний лист", "description": "Осенний герой"},
    "flower": {"emoji": "🌼", "name": "Весенний цветок", "description": "Весенний лидер"},
    
    # Роли
    "vip": {"emoji": "💎", "name": "VIP", "description": "Особый статус"},
    "moderator": {"emoji": "⚔️", "name": "Модератор", "description": "Помощник администрации"},
    "streamer": {"emoji": "🎥", "name": "Стример", "description": "Активный стример"},
    "creator": {"emoji": "🎨", "name": "Создатель", "description": "Креативный участник"},
    "drawing_winner": {"emoji": "🎉", "name": "Победитель розыгрыша", "description": "Победитель розыгрыша призов"}
}

# ========== СИСТЕМА ЗАДАНИЙ ==========
TASK_TYPES = {
    "contracts": {
        "emoji": "📜",
        "name": "Контракты",
        "points": 5,
        "description": "Выполнение контрактов в игре (16 штук)",
        "requires_screenshot": True,
        "max_per_day": None,
        "max_per_submission": 16,
        "validation_rules": "На скриншоте должно быть видно выполнение контракта"
    },
    "family_contracts": {
        "emoji": "👨‍👩‍👧‍👦", 
        "name": "Семейные контракты",
        "points": 5,
        "description": "Выполнение семейных контрактов (1 контракт = 5 баллов)",
        "requires_screenshot": True,
        "max_per_day": 10,
        "max_per_submission": 10,
        "validation_rules": "На скриншоте должно быть видно выполнение семейного контракта"
    },
    "pass_tasks": {
        "emoji": "🎫",
        "name": "Задания пасса",
        "points": 5,
        "description": "Выполнение заданий пасса (10 заданий)",
        "requires_screenshot": True,
        "max_per_day": None,
        "max_per_submission": 10,
        "validation_rules": "На скриншоте должно быть видно выполнение задания пасса"
    },
    "woodcutting": {
        "emoji": "🌳",
        "name": "Вырубка леса",
        "points": 5,
        "description": "Вырубка деревьев (10 деревьев)",
        "requires_screenshot": True,
        "max_per_day": None,
        "max_per_submission": 10,
        "validation_rules": "На скриншоте должно быть видно процесс вырубки деревьев"
    },
    "find_players": {
        "emoji": "🔍",
        "name": "Поиск игроков",
        "points": 5,
        "description": "Найти игроков с ID от 100 до 200 (5 игроков, семья не считается)",
        "requires_screenshot": True,
        "max_per_day": None,
        "max_per_submission": 5,
        "validation_rules": "На скриншоте должны быть видны ID игроков (100-200), семья не учитывается"
    },
    "auction_containers": {
        "emoji": "📦",
        "name": "Аукционные контейнеры",
        "points": 5,
        "description": "Открыть аукционные контейнеры (5 контейнеров, от 100к₽)",
        "requires_screenshot": True,
        "max_per_day": None,
        "max_per_submission": 5,
        "validation_rules": "На скриншоте должно быть видно открытие контейнера стоимостью от 100к₽"
    },
    "repair_cars": {
        "emoji": "🚗",
        "name": "Ремонт машин",
        "points": 5,
        "description": "Ремонт машин на сервере (10 машин, семейные/личные не в счет)",
        "requires_screenshot": True,
        "max_per_day": None,
        "max_per_submission": 10,
        "validation_rules": "На скриншоте должно быть видно ремонт машины (не семейной/личной)"
    },
    "fireman_missions": {
        "emoji": "🚒",
        "name": "Пожарный",
        "points": 5,
        "description": "Выполнить миссии пожарного (10 вызовов)",
        "requires_screenshot": True,
        "max_per_day": None,
        "max_per_submission": 10,
        "validation_rules": "На скриншоте должно быть видно выполнение миссии пожарного"
    },
    "help_newbies": {
        "emoji": "🆘",
        "name": "Помощь новичкам",
        "points": 5,
        "description": "Помочь новичкам деньгами (5 раз по 10к)",
        "requires_screenshot": True,
        "max_per_day": None,
        "max_per_submission": 5,
        "validation_rules": "На скриншоте должно быть видно передачу 10к новичку"
    },
    "congratulations": {
        "emoji": "🎉",
        "name": "Поздравления",
        "points": 5,
        "description": "Поздравить игроков с Новым Годом (15 игроков)",
        "requires_screenshot": True,
        "max_per_day": None,
        "max_per_submission": 15,
        "validation_rules": "На скриншоте должно быть видно поздравление с Новым Годом"
    }
}

# ========== СИСТЕМА РОЗЫГРЫШЕЙ ==========
class DrawingStatus(Enum):
    ANNOUNCED = "announced"      # Объявлен, но не начат
    ACTIVE = "active"           # Активный сбор участников
    FINISHED = "finished"       # Завершен, победители определены
    CANCELLED = "cancelled"     # Отменен

class Drawing:
    def __init__(self, name: str, description: str, prize: str, 
                 start_date: datetime, end_date: datetime, 
                 min_participants: int = 5, max_participants: int = 100,
                 entry_cost: int = 0, required_badges: List[str] = None):
        self.name = name
        self.description = description
        self.prize = prize
        self.start_date = start_date
        self.end_date = end_date
        self.min_participants = min_participants
        self.max_participants = max_participants
        self.entry_cost = entry_cost
        self.required_badges = required_badges or []
        self.status = DrawingStatus.ANNOUNCED
        self.participants = []  # Список user_id участников
        self.winners = {}       # place: user_id
        self.ticket_numbers = {}  # user_id: ticket_number
        
    def is_active(self) -> bool:
        now = datetime.now()
        return (self.start_date <= now <= self.end_date and 
                self.status == DrawingStatus.ACTIVE)
    
    def can_participate(self, user: Dict) -> bool:
        """Может ли пользователь участвовать в розыгрыше"""
        # Проверка на бан
        if user.get('is_banned'):
            return False
        
        # Проверка необходимых значков
        if self.required_badges:
            user_badges = user.get('badges', [])
            if not all(badge in user_badges for badge in self.required_badges):
                return False
        
        # Проверка стоимости входа
        if self.entry_cost > 0 and user.get('total_points', 0) < self.entry_cost:
            return False
        
        # Проверка на уже участие
        if user['user_id'] in self.participants:
            return False
        
        # Проверка на максимальное количество участников
        if len(self.participants) >= self.max_participants:
            return False
        
        return True
    
    def add_participant(self, user_id: int, ticket_number: int = None):
        """Добавить участника в розыгрыш"""
        if user_id not in self.participants:
            self.participants.append(user_id)
            if ticket_number:
                self.ticket_numbers[user_id] = ticket_number
            else:
                self.ticket_numbers[user_id] = len(self.participants)
    
    def draw_winners(self, num_winners: int = 5) -> Dict[int, int]:
        """Провести розыгрыш и определить победителей"""
        if len(self.participants) < self.min_participants:
            return {}
        
        # Перемешиваем участников
        participants_copy = self.participants.copy()
        random.shuffle(participants_copy)
        
        # Определяем победителей
        winners = {}
        for i in range(min(num_winners, len(participants_copy))):
            winners[i+1] = participants_copy[i]
        
        self.winners = winners
        self.status = DrawingStatus.FINISHED
        return winners

# ========== БАЗА ДАННЫХ ==========
import sqlite3
from contextlib import contextmanager

class Database:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance.init_db()
        return cls._instance
    
    def init_db(self):
        self.conn = sqlite3.connect('bot_database.db', check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.create_tables()
    
    @contextmanager
    def get_cursor(self):
        cursor = self.conn.cursor()
        try:
            yield cursor
            self.conn.commit()
        except Exception as e:
            self.conn.rollback()
            raise e
        finally:
            cursor.close()
    
    def create_tables(self):
        with self.get_cursor() as cursor:
            # Пользователи
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    username TEXT,
                    nickname TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    total_points INTEGER DEFAULT 0,
                    badges TEXT DEFAULT '[]',
                    custom_emoji TEXT DEFAULT '',
                    daily_family_contracts INTEGER DEFAULT 0,
                    last_family_reset TIMESTAMP,
                    join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_active TIMESTAMP,
                    tasks_completed INTEGER DEFAULT 0,
                    tasks_pending INTEGER DEFAULT 0,
                    tasks_rejected INTEGER DEFAULT 0,
                    is_banned BOOLEAN DEFAULT 0,
                    ban_reason TEXT DEFAULT '',
                    daily_tasks_count INTEGER DEFAULT 0,
                    last_task_date DATE,
                    settings TEXT DEFAULT '{}',
                    drawings_won INTEGER DEFAULT 0,
                    last_drawing_win TIMESTAMP
                )
            ''')
            
            # Задания
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    task_type TEXT NOT NULL,
                    points INTEGER NOT NULL,
                    count INTEGER DEFAULT 1,
                    screenshot_path TEXT,
                    comment TEXT,
                    status TEXT DEFAULT 'pending',
                    drawing_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    reviewed_at TIMESTAMP,
                    reviewed_by INTEGER,
                    rejection_reason TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
                )
            ''')
            
            # История операций админов
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS admin_operations (
                    operation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    admin_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    operation_type TEXT NOT NULL,
                    points_change INTEGER DEFAULT 0,
                    badge_change TEXT,
                    emoji_change TEXT,
                    note TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Розыгрыши
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS drawings (
                    drawing_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    description TEXT,
                    prize TEXT NOT NULL,
                    start_date TIMESTAMP NOT NULL,
                    end_date TIMESTAMP NOT NULL,
                    status TEXT DEFAULT 'announced',
                    min_participants INTEGER DEFAULT 5,
                    max_participants INTEGER DEFAULT 100,
                    entry_cost INTEGER DEFAULT 0,
                    required_badges TEXT DEFAULT '[]',
                    participants TEXT DEFAULT '[]',
                    winners TEXT DEFAULT '{}',
                    ticket_numbers TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Участие в розыгрышах
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS drawing_participations (
                    participation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    drawing_id INTEGER NOT NULL,
                    user_id INTEGER NOT NULL,
                    ticket_number INTEGER,
                    participated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    won_place INTEGER DEFAULT 0,
                    FOREIGN KEY (drawing_id) REFERENCES drawings (drawing_id),
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
                )
            ''')
            
            # Индексы
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_points ON users(total_points DESC)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_nickname ON users(nickname)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_user_date ON tasks(user_id, created_at DESC)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_drawings_status ON drawings(status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_drawings_dates ON drawings(start_date, end_date)')
    
    # ========== МЕТОДЫ ПОЛЬЗОВАТЕЛЕЙ ==========
    def get_user(self, user_id: int):
        with self.get_cursor() as cursor:
            cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
            row = cursor.fetchone()
            if row:
                user = dict(row)
                user['badges'] = json.loads(user['badges']) if user['badges'] else []
                user['settings'] = json.loads(user['settings']) if user['settings'] else {}
                return user
            return None
    
    def save_user(self, user_data: dict):
        with self.get_cursor() as cursor:
            cursor.execute('''
                INSERT OR REPLACE INTO users 
                (user_id, username, nickname, first_name, last_name, total_points, badges, 
                 custom_emoji, daily_family_contracts, last_family_reset, join_date, last_active,
                 tasks_completed, tasks_pending, tasks_rejected, is_banned, ban_reason,
                 daily_tasks_count, last_task_date, settings, drawings_won, last_drawing_win)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                user_data['user_id'],
                user_data.get('username'),
                user_data.get('nickname'),
                user_data.get('first_name'),
                user_data.get('last_name'),
                user_data.get('total_points', 0),
                json.dumps(user_data.get('badges', [])),
                user_data.get('custom_emoji', ''),
                user_data.get('daily_family_contracts', 0),
                user_data.get('last_family_reset'),
                user_data.get('join_date', datetime.now()),
                datetime.now(),
                user_data.get('tasks_completed', 0),
                user_data.get('tasks_pending', 0),
                user_data.get('tasks_rejected', 0),
                int(user_data.get('is_banned', False)),
                user_data.get('ban_reason', ''),
                user_data.get('daily_tasks_count', 0),
                user_data.get('last_task_date'),
                json.dumps(user_data.get('settings', {})),
                user_data.get('drawings_won', 0),
                user_data.get('last_drawing_win')
            ))
    
    def update_user_points(self, user_id: int, points_change: int, admin_id: int = None, note: str = ""):
        with self.get_cursor() as cursor:
            cursor.execute(
                'UPDATE users SET total_points = total_points + ? WHERE user_id = ?',
                (points_change, user_id)
            )
            
            if admin_id:
                operation_type = "add_points" if points_change > 0 else "remove_points"
                cursor.execute('''
                    INSERT INTO admin_operations 
                    (admin_id, user_id, operation_type, points_change, note)
                    VALUES (?, ?, ?, ?, ?)
                ''', (admin_id, user_id, operation_type, points_change, note))
            
            return cursor.rowcount > 0
    
    def update_user_badges(self, user_id: int, badges: list):
        with self.get_cursor() as cursor:
            cursor.execute(
                'UPDATE users SET badges = ? WHERE user_id = ?',
                (json.dumps(badges), user_id)
            )
            return cursor.rowcount > 0
    
    def update_user_emoji(self, user_id: int, emoji: str, admin_id: int = None, note: str = ""):
        with self.get_cursor() as cursor:
            cursor.execute(
                'UPDATE users SET custom_emoji = ? WHERE user_id = ?',
                (emoji, user_id)
            )
            
            if admin_id:
                cursor.execute('''
                    INSERT INTO admin_operations 
                    (admin_id, user_id, operation_type, emoji_change, note)
                    VALUES (?, ?, ?, ?, ?)
                ''', (admin_id, user_id, "set_emoji", emoji, note))
            
            return cursor.rowcount > 0
    
    # ========== МЕТОДЫ ЗАДАНИЙ ==========
    def create_task(self, task_data: dict):
        with self.get_cursor() as cursor:
            cursor.execute('''
                INSERT INTO tasks 
                (user_id, task_type, points, count, screenshot_path, comment, status, drawing_name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                task_data['user_id'],
                task_data['task_type'],
                task_data['points'],
                task_data.get('count', 1),
                task_data.get('screenshot_path'),
                task_data.get('comment'),
                task_data.get('status', 'pending'),
                task_data.get('drawing_name')
            ))
            
            task_id = cursor.lastrowid
            
            # Обновляем статистику пользователя
            if task_data.get('status') == 'pending':
                cursor.execute(
                    'UPDATE users SET tasks_pending = tasks_pending + 1 WHERE user_id = ?',
                    (task_data['user_id'],)
                )
            
            return task_id
    
    def get_pending_tasks(self, limit: int = 50):
        with self.get_cursor() as cursor:
            cursor.execute('''
                SELECT t.*, u.nickname, u.username 
                FROM tasks t 
                LEFT JOIN users u ON t.user_id = u.user_id 
                WHERE t.status = 'pending'
                ORDER BY t.created_at ASC 
                LIMIT ?
            ''', (limit,))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_user_tasks(self, user_id: int, limit: int = 50):
        with self.get_cursor() as cursor:
            cursor.execute('''
                SELECT * FROM tasks 
                WHERE user_id = ? 
                ORDER BY created_at DESC 
                LIMIT ?
            ''', (user_id, limit))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_user_tasks_by_type(self, user_id: int, task_type: str, date: str = None):
        with self.get_cursor() as cursor:
            if date:
                cursor.execute('''
                    SELECT COUNT(*) as count FROM tasks 
                    WHERE user_id = ? AND task_type = ? AND DATE(created_at) = ? AND status != 'rejected'
                ''', (user_id, task_type, date))
            else:
                cursor.execute('''
                    SELECT COUNT(*) as count FROM tasks 
                    WHERE user_id = ? AND task_type = ? AND status != 'rejected'
                ''', (user_id, task_type))
            return cursor.fetchone()[0]
    
    def approve_task(self, task_id: int, admin_id: int):
        with self.get_cursor() as cursor:
            # Получаем задание
            cursor.execute('SELECT * FROM tasks WHERE task_id = ? AND status = "pending"', (task_id,))
            task = cursor.fetchone()
            if not task:
                return False
            
            task = dict(task)
            user_id = task['user_id']
            points = task['points'] * task.get('count', 1)
            
            # Обновляем задание
            cursor.execute('''
                UPDATE tasks 
                SET status = 'approved', reviewed_at = ?, reviewed_by = ?
                WHERE task_id = ?
            ''', (datetime.now(), admin_id, task_id))
            
            # Начисляем баллы пользователю
            cursor.execute('''
                UPDATE users 
                SET total_points = total_points + ?, 
                    tasks_completed = tasks_completed + 1,
                    tasks_pending = tasks_pending - 1
                WHERE user_id = ?
            ''', (points, user_id))
            
            # Записываем операцию
            cursor.execute('''
                INSERT INTO admin_operations 
                (admin_id, user_id, operation_type, points_change, note)
                VALUES (?, ?, ?, ?, ?)
            ''', (admin_id, user_id, "approve_task", points, f"Одобрено задание #{task_id}"))
            
            return True
    
    def reject_task(self, task_id: int, admin_id: int, reason: str):
        with self.get_cursor() as cursor:
            cursor.execute('SELECT user_id FROM tasks WHERE task_id = ?', (task_id,))
            task = cursor.fetchone()
            if not task:
                return False
            
            user_id = task[0]
            
            # Обновляем задание
            cursor.execute('''
                UPDATE tasks 
                SET status = 'rejected', reviewed_at = ?, reviewed_by = ?, rejection_reason = ?
                WHERE task_id = ?
            ''', (datetime.now(), admin_id, reason, task_id))
            
            # Обновляем статистику пользователя
            cursor.execute('''
                UPDATE users 
                SET tasks_rejected = tasks_rejected + 1,
                    tasks_pending = tasks_pending - 1
                WHERE user_id = ?
            ''', (user_id,))
            
            # Записываем операцию
            cursor.execute('''
                INSERT INTO admin_operations 
                (admin_id, user_id, operation_type, note)
                VALUES (?, ?, ?, ?)
            ''', (admin_id, user_id, "reject_task", f"Отклонено задание #{task_id}: {reason}"))
            
            return True
    
    # ========== МЕТОДЫ РОЗЫГРЫШЕЙ ==========
    def create_drawing(self, drawing_data: dict):
        with self.get_cursor() as cursor:
            cursor.execute('''
                INSERT INTO drawings 
                (name, description, prize, start_date, end_date, status, 
                 min_participants, max_participants, entry_cost, required_badges)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                drawing_data['name'],
                drawing_data.get('description', ''),
                drawing_data['prize'],
                drawing_data['start_date'],
                drawing_data['end_date'],
                drawing_data.get('status', 'announced'),
                drawing_data.get('min_participants', 5),
                drawing_data.get('max_participants', 100),
                drawing_data.get('entry_cost', 0),
                json.dumps(drawing_data.get('required_badges', []))
            ))
            return cursor.lastrowid
    
    def get_drawing(self, drawing_id: int = None, drawing_name: str = None):
        with self.get_cursor() as cursor:
            if drawing_id:
                cursor.execute('SELECT * FROM drawings WHERE drawing_id = ?', (drawing_id,))
            elif drawing_name:
                cursor.execute('SELECT * FROM drawings WHERE name = ?', (drawing_name,))
            else:
                return None
            
            row = cursor.fetchone()
            if row:
                drawing = dict(row)
                drawing['required_badges'] = json.loads(drawing['required_badges']) if drawing['required_badges'] else []
                drawing['participants'] = json.loads(drawing['participants']) if drawing['participants'] else []
                drawing['winners'] = json.loads(drawing['winners']) if drawing['winners'] else {}
                drawing['ticket_numbers'] = json.loads(drawing['ticket_numbers']) if drawing['ticket_numbers'] else {}
                return drawing
            return None
    
    def get_active_drawings(self):
        with self.get_cursor() as cursor:
            cursor.execute('''
                SELECT * FROM drawings 
                WHERE status = 'active' 
                AND datetime('now') BETWEEN start_date AND end_date
                ORDER BY end_date ASC
            ''')
            drawings = []
            for row in cursor.fetchall():
                drawing = dict(row)
                drawing['required_badges'] = json.loads(drawing['required_badges']) if drawing['required_badges'] else []
                drawing['participants'] = json.loads(drawing['participants']) if drawing['participants'] else []
                drawing['winners'] = json.loads(drawing['winners']) if drawing['winners'] else {}
                drawing['ticket_numbers'] = json.loads(drawing['ticket_numbers']) if drawing['ticket_numbers'] else {}
                drawings.append(drawing)
            return drawings
    
    def get_finished_drawings(self, limit: int = 10):
        with self.get_cursor() as cursor:
            cursor.execute('''
                SELECT * FROM drawings 
                WHERE status = 'finished'
                ORDER BY end_date DESC
                LIMIT ?
            ''', (limit,))
            drawings = []
            for row in cursor.fetchall():
                drawing = dict(row)
                drawing['required_badges'] = json.loads(drawing['required_badges']) if drawing['required_badges'] else []
                drawing['participants'] = json.loads(drawing['participants']) if drawing['participants'] else []
                drawing['winners'] = json.loads(drawing['winners']) if drawing['winners'] else {}
                drawing['ticket_numbers'] = json.loads(drawing['ticket_numbers']) if drawing['ticket_numbers'] else {}
                drawings.append(drawing)
            return drawings
    
    def add_drawing_participant(self, drawing_id: int, user_id: int, ticket_number: int = None):
        with self.get_cursor() as cursor:
            # Проверяем, не участвует ли уже
            cursor.execute('''
                SELECT * FROM drawing_participations 
                WHERE drawing_id = ? AND user_id = ?
            ''', (drawing_id, user_id))
            if cursor.fetchone():
                return False
            
            # Получаем текущих участников розыгрыша
            cursor.execute('SELECT participants, ticket_numbers FROM drawings WHERE drawing_id = ?', (drawing_id,))
            row = cursor.fetchone()
            if not row:
                return False
            
            participants = json.loads(row[0]) if row[0] else []
            ticket_numbers = json.loads(row[1]) if row[1] else {}
            
            # Добавляем участника
            participants.append(user_id)
            if ticket_number:
                ticket_numbers[user_id] = ticket_number
            else:
                ticket_numbers[user_id] = len(participants)
            
            # Обновляем розыгрыш
            cursor.execute('''
                UPDATE drawings 
                SET participants = ?, ticket_numbers = ?
                WHERE drawing_id = ?
            ''', (json.dumps(participants), json.dumps(ticket_numbers), drawing_id))
            
            # Записываем участие
            cursor.execute('''
                INSERT INTO drawing_participations 
                (drawing_id, user_id, ticket_number)
                VALUES (?, ?, ?)
            ''', (drawing_id, user_id, ticket_numbers[user_id]))
            
            return True
    
    def finish_drawing(self, drawing_id: int, winners: dict):
        with self.get_cursor() as cursor:
            # Обновляем статус розыгрыша и победителей
            cursor.execute('''
                UPDATE drawings 
                SET status = 'finished', winners = ?, end_date = datetime('now')
                WHERE drawing_id = ?
            ''', (json.dumps(winners), drawing_id))
            
            # Обновляем статистику победителей
            for place, user_id in winners.items():
                cursor.execute('''
                    UPDATE users 
                    SET drawings_won = drawings_won + 1,
                        last_drawing_win = datetime('now')
                    WHERE user_id = ?
                ''', (user_id,))
                
                # Обновляем запись участия
                cursor.execute('''
                    UPDATE drawing_participations 
                    SET won_place = ?
                    WHERE drawing_id = ? AND user_id = ?
                ''', (place, drawing_id, user_id))
            
            return True
    
    # ========== ПОИСК И СТАТИСТИКА ==========
    def search_users(self, search_term: str, limit: int = 10):
        with self.get_cursor() as cursor:
            search_pattern = f"%{search_term}%"
            cursor.execute('''
                SELECT user_id, nickname, username, first_name, last_name, total_points
                FROM users 
                WHERE nickname LIKE ? OR username LIKE ? OR first_name LIKE ? OR last_name LIKE ?
                ORDER BY total_points DESC
                LIMIT ?
            ''', (search_pattern, search_pattern, search_pattern, search_pattern, limit))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_top_users(self, limit: int = 10):
        with self.get_cursor() as cursor:
            cursor.execute('''
                SELECT user_id, nickname, username, custom_emoji, total_points as points,
                       drawings_won, tasks_completed
                FROM users 
                WHERE is_banned = 0
                ORDER BY total_points DESC
                LIMIT ?
            ''', (limit,))
            
            users = []
            for row in cursor.fetchall():
                user = dict(row)
                user['badges'] = []  # Можно загрузить отдельно если нужно
                users.append(user)
            return users
    
    def get_user_stats(self, user_id: int):
        with self.get_cursor() as cursor:
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_tasks,
                    SUM(CASE WHEN status = 'approved' THEN points * count ELSE 0 END) as earned_points,
                    SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as approved,
                    SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                    SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as rejected
                FROM tasks 
                WHERE user_id = ?
            ''', (user_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return {'total_tasks': 0, 'earned_points': 0, 'approved': 0, 'pending': 0, 'rejected': 0}
    
    def get_user_drawings_stats(self, user_id: int):
        with self.get_cursor() as cursor:
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_participations,
                    SUM(CASE WHEN won_place > 0 THEN 1 ELSE 0 END) as drawings_won,
                    GROUP_CONCAT(won_place) as winning_places
                FROM drawing_participations 
                WHERE user_id = ?
            ''', (user_id,))
            row = cursor.fetchone()
            if row:
                stats = dict(row)
                stats['winning_places'] = stats['winning_places'].split(',') if stats['winning_places'] else []
                return stats
            return {'total_participations': 0, 'drawings_won': 0, 'winning_places': []}
    
    def get_admin_operations(self, user_id: int, limit: int = 20):
        with self.get_cursor() as cursor:
            cursor.execute('''
                SELECT ao.*, u.username as admin_username
                FROM admin_operations ao
                LEFT JOIN users u ON ao.admin_id = u.user_id
                WHERE ao.user_id = ?
                ORDER BY ao.created_at DESC
                LIMIT ?
            ''', (user_id, limit))
            return [dict(row) for row in cursor.fetchall()]

db = Database()

# ========== СОСТОЯНИЯ ДЛЯ ConversationHandler ==========
(
    TASK_SELECT, TASK_SCREENSHOT, TASK_DETAILS, TASK_COUNT,
    NICKNAME_SET, ADMIN_ADD_POINTS, ADMIN_REMOVE_POINTS,
    ADMIN_GIVE_BADGE, ADMIN_VIEW_USER, ADMIN_SEARCH_USER,
    ADMIN_SET_EMOJI, ADMIN_SEND_BROADCAST, ADMIN_CREATE_DRAWING,
    ADMIN_REVIEW_TASK, ADMIN_EDIT_DRAWING, ADMIN_BAN_USER,
    DRAWING_PARTICIPATE, DRAWING_VIEW
) = range(18)

# ========== КЛАВИАТУРЫ ==========
def create_user_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для участников"""
    keyboard = [
        [KeyboardButton("🎮 Отправить задание"), KeyboardButton("📊 Мой профиль")],
        [KeyboardButton("🏆 ТОП-10"), KeyboardButton("📋 Мои задания")],
        [KeyboardButton("🏅 Мои значки"), KeyboardButton("🎰 Активные розыгрыши")],
        [KeyboardButton("✏️ Мой никнейм"), KeyboardButton("🏆 Мои победы")],
        [KeyboardButton("❓ Помощь"), KeyboardButton("📢 Новости")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, selective=True)

def create_admin_keyboard() -> ReplyKeyboardMarkup:
    """Клавиатура для админов"""
    keyboard = [
        [KeyboardButton("📋 Проверить задания"), KeyboardButton("👥 Управление")],
        [KeyboardButton("📊 Статистика"), KeyboardButton("🎰 Управление розыгрышами")],
        [KeyboardButton("📢 Рассылка"), KeyboardButton("⚙️ Настройки системы")],
        [KeyboardButton("🔍 Поиск участника"), KeyboardButton("📈 Аналитика")],
        [KeyboardButton("🔙 В меню пользователя")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, selective=True)

def create_admin_management_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура управления участниками для админов"""
    keyboard = [
        [
            InlineKeyboardButton("➕ Дать баллы", callback_data="admin_add_points_menu"),
            InlineKeyboardButton("➖ Забрать баллы", callback_data="admin_remove_points_menu")
        ],
        [
            InlineKeyboardButton("🏅 Выдать значок", callback_data="admin_give_badge_menu"),
            InlineKeyboardButton("🎭 Установить эмодзи", callback_data="admin_set_emoji_menu")
        ],
        [
            InlineKeyboardButton("📋 История заданий", callback_data="admin_view_tasks_menu"),
            InlineKeyboardButton("📊 Полная статистика", callback_data="admin_view_stats_menu")
        ],
        [
            InlineKeyboardButton("🎰 Участие в розыгрышах", callback_data="admin_view_drawings_menu"),
            InlineKeyboardButton("🏆 Победители", callback_data="admin_view_winners_menu")
        ],
        [
            InlineKeyboardButton("🚫 Блокировка", callback_data="admin_ban_menu"),
            InlineKeyboardButton("✅ Разблокировка", callback_data="admin_unban_menu")
        ],
        [
            InlineKeyboardButton("🔙 Назад в админ-панель", callback_data="admin_back_to_dashboard")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def create_drawing_management_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура управления розыгрышами"""
    keyboard = [
        [
            InlineKeyboardButton("🎰 Создать розыгрыш", callback_data="admin_create_drawing"),
            InlineKeyboardButton("📋 Активные розыгрыши", callback_data="admin_active_drawings")
        ],
        [
            InlineKeyboardButton("🏆 Завершить розыгрыш", callback_data="admin_finish_drawing"),
            InlineKeyboardButton("📜 История розыгрышей", callback_data="admin_drawing_history")
        ],
        [
            InlineKeyboardButton("⚙️ Настройки розыгрышей", callback_data="admin_drawing_settings"),
            InlineKeyboardButton("📢 Анонс розыгрыша", callback_data="admin_drawing_announce")
        ],
        [
            InlineKeyboardButton("🔙 Назад в админ-панель", callback_data="admin_back_to_dashboard")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def create_task_types_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора типа задания"""
    keyboard = []
    row = []
    
    for i, (task_id, task_info) in enumerate(TASK_TYPES.items()):
        if i % 2 == 0 and row:
            keyboard.append(row)
            row = []
        
        row.append(InlineKeyboardButton(
            f"{task_info['emoji']} {task_info['name']}",
            callback_data=f"task_select_{task_id}"
        ))
    
    if row:
        keyboard.append(row)
    
    keyboard.append([
        InlineKeyboardButton("❓ Как отправлять задания?", callback_data="task_help"),
        InlineKeyboardButton("❌ Отмена", callback_data="task_cancel")
    ])
    
    return InlineKeyboardMarkup(keyboard)

def create_quick_actions_keyboard(user_id: int) -> InlineKeyboardMarkup:
    """Клавиатура быстрых действий для админов"""
    keyboard = [
        [
            InlineKeyboardButton("➕ 10 баллов", callback_data=f"quick_add_{user_id}_10"),
            InlineKeyboardButton("➕ 50 баллов", callback_data=f"quick_add_{user_id}_50"),
            InlineKeyboardButton("➕ 100 баллов", callback_data=f"quick_add_{user_id}_100")
        ],
        [
            InlineKeyboardButton("➖ 10 баллов", callback_data=f"quick_remove_{user_id}_10"),
            InlineKeyboardButton("➖ 50 баллов", callback_data=f"quick_remove_{user_id}_50"),
            InlineKeyboardButton("➖ 100 баллов", callback_data=f"quick_remove_{user_id}_100")
        ],
        [
            InlineKeyboardButton("⭐ Звезда", callback_data=f"quick_badge_{user_id}_star"),
            InlineKeyboardButton("👑 Король", callback_data=f"quick_badge_{user_id}_crown"),
            InlineKeyboardButton("🔥 Огненный", callback_data=f"quick_badge_{user_id}_fire")
        ],
        [
            InlineKeyboardButton("🎭 Эмодзи", callback_data=f"quick_emoji_{user_id}"),
            InlineKeyboardButton("📋 Задания", callback_data=f"view_user_tasks_{user_id}"),
            InlineKeyboardButton("🎰 Розыгрыши", callback_data=f"view_user_drawings_{user_id}")
        ],
        [
            InlineKeyboardButton("🚫 Блокировать", callback_data=f"quick_ban_{user_id}"),
            InlineKeyboardButton("🔙 Назад к поиску", callback_data="admin_back_to_search")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def create_emojis_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора эмодзи"""
    emojis = [
        "⭐", "🌟", "✨", "💫", "🔥", "🎯", "🏆", "🎖️",
        "👑", "💎", "❤️", "💖", "💕", "🎉", "🎊", "✨",
        "🚀", "⚡", "💥", "🛡️", "⚔️", "🎨", "🎥", "🎭",
        "🤴", "👸", "🦸", "🦹", "🧙", "🧚", "🧛", "🧜"
    ]
    
    keyboard = []
    row = []
    
    for i, emoji in enumerate(emojis):
        if i % 8 == 0 and row:
            keyboard.append(row)
            row = []
        
        row.append(InlineKeyboardButton(emoji, callback_data=f"emoji_select_{emoji}"))
    
    if row:
        keyboard.append(row)
    
    keyboard.append([
        InlineKeyboardButton("❌ Без эмодзи", callback_data="emoji_clear"),
        InlineKeyboardButton("🔙 Назад", callback_data="admin_back_to_manage")
    ])
    
    return InlineKeyboardMarkup(keyboard)

def create_drawing_participation_keyboard(drawing_id: int, user_id: int, can_participate: bool = True) -> InlineKeyboardMarkup:
    """Клавиатура для участия в розыгрыше"""
    keyboard = []
    
    if can_participate:
        keyboard.append([
            InlineKeyboardButton("🎰 Участвовать в розыгрыше", callback_data=f"drawing_participate_{drawing_id}")
        ])
    else:
        keyboard.append([
            InlineKeyboardButton("✅ Вы уже участвуете", callback_data="noop")
        ])
    
    keyboard.append([
        InlineKeyboardButton("👥 Участники", callback_data=f"drawing_participants_{drawing_id}"),
        InlineKeyboardButton("📊 Статистика", callback_data=f"drawing_stats_{drawing_id}")
    ])
    
    keyboard.append([
        InlineKeyboardButton("🔙 К списку розыгрышей", callback_data="back_to_drawings")
    ])
    
    return InlineKeyboardMarkup(keyboard)

def create_drawings_list_keyboard(drawings: List[Dict], page: int = 0) -> InlineKeyboardMarkup:
    """Клавиатура списка розыгрышей"""
    keyboard = []
    
    for drawing in drawings:
        status_emoji = "🟢" if drawing['status'] == 'active' else "🟡" if drawing['status'] == 'announced' else "🔴"
        keyboard.append([
            InlineKeyboardButton(
                f"{status_emoji} {drawing['name'][:20]}",
                callback_data=f"drawing_view_{drawing['drawing_id']}"
            )
        ])
    
    # Пагинация
    if len(drawings) == 5:  # Предполагаем 5 на страницу
        keyboard.append([
            InlineKeyboardButton("◀️ Предыдущие", callback_data=f"drawings_page_{page-1}"),
            InlineKeyboardButton("Следующие ▶️", callback_data=f"drawings_page_{page+1}")
        ])
    
    keyboard.append([
        InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu")
    ])
    
    return InlineKeyboardMarkup(keyboard)

def create_confirmation_keyboard(action: str, target_id: int) -> InlineKeyboardMarkup:
    """Клавиатура подтверждения действия"""
    keyboard = [
        [
            InlineKeyboardButton("✅ Да, подтверждаю", callback_data=f"confirm_{action}_{target_id}"),
            InlineKeyboardButton("❌ Нет, отмена", callback_data="cancel_action")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# ========== УТИЛИТЫ ==========
def is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь администратором"""
    return user_id in ADMIN_IDS

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

def format_timedelta(td: timedelta) -> str:
    """Форматирование временного интервала"""
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
    forbidden = ["admin", "админ", "moderator", "модератор", "система", "system"]
    if any(word in nickname.lower() for word in forbidden):
        return False, "❌ Никнейм содержит запрещенные слова"
    
    return True, "✅ Никнейм прошел проверку"

async def ensure_user_exists(user_id: int, username: str = None, 
                           first_name: str = None, last_name: str = None) -> dict:
    """Обеспечивает существование пользователя в базе"""
    user = db.get_user(user_id)
    
    if not user:
        user_data = {
            'user_id': user_id,
            'username': username,
            'first_name': first_name,
            'last_name': last_name,
            'nickname': username or first_name or f"User_{user_id}",
            'join_date': datetime.now(),
            'last_active': datetime.now(),
            'settings': json.dumps({
                'notifications': True,
                'privacy': False,
                'daily_reminder': True,
                'language': 'ru',
                'drawing_notifications': True
            })
        }
        db.save_user(user_data)
        user = db.get_user(user_id)
    
    # Обновляем время последней активности
    db.save_user({
        'user_id': user_id,
        'last_active': datetime.now()
    })
    
    return user

async def send_notification(bot, user_id: int, message: str, parse_mode: str = ParseMode.HTML) -> bool:
    """Отправка уведомления пользователю"""
    try:
        await bot.send_message(
            chat_id=user_id,
            text=message,
            parse_mode=parse_mode,
            disable_web_page_preview=True
        )
        return True
    except Exception as e:
        logger.error(f"Ошибка отправки уведомления пользователю {user_id}: {e}")
        return False

async def notify_admins(bot, message: str, exclude_id: int = None, parse_mode: str = ParseMode.HTML):
    """Уведомление всех администраторов"""
    for admin_id in ADMIN_IDS:
        if admin_id != exclude_id:
            try:
                await bot.send_message(
                    chat_id=admin_id,
                    text=message,
                    parse_mode=parse_mode,
                    disable_web_page_preview=True
                )
                await asyncio.sleep(0.1)  # Задержка чтобы не превысить лимиты
            except Exception as e:
                logger.error(f"Ошибка уведомления администратора {admin_id}: {e}")

# ========== ОСНОВНЫЕ КОМАНДЫ ==========
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    
    # Регистрируем пользователя
    await ensure_user_exists(
        user.id,
        user.username,
        user.first_name,
        user.last_name
    )
    
    # Проверяем, является ли пользователь администратором
    if is_admin(user.id):
        reply_markup = create_admin_keyboard()
        role_text = "👑 <b>Вы вошли как администратор!</b>"
        admin_features = """
        
<b>🎯 Административные функции:</b>
• 📋 Проверить задания
• 👥 Управление участниками  
• 🎰 Управление розыгрышами
• 📊 Полная статистика
• 📢 Массовая рассылка
• ⚙️ Настройки системы
"""
    else:
        reply_markup = create_user_keyboard()
        role_text = "🎮 <b>Добро пожаловать в систему заданий!</b>"
        admin_features = ""
    
    # Получаем информацию о пользователе
    user_data = db.get_user(user.id)
    nickname = user_data.get('nickname', user.first_name)
    
    # Проверяем активные розыгрыши
    active_drawings = db.get_active_drawings()
    drawings_text = ""
    if active_drawings:
        drawings_text = "\n\n<b>🎰 АКТИВНЫЕ РОЗЫГРЫШИ:</b>\n"
        for drawing in active_drawings[:2]:  # Показываем максимум 2 розыгрыша
            time_left = datetime.fromisoformat(drawing['end_date']) - datetime.now()
            time_left_str = format_timedelta(time_left)
            drawings_text += f"• <b>{drawing['name']}</b> - осталось {time_left_str}\n"
            drawings_text += f"  Приз: {drawing['prize'][:30]}...\n"
    
    welcome_text = f"""
{role_text}

👋 Привет, <b>{nickname}</b>!

<b>✨ Доступные функции:</b>
• 🎮 <b>Отправить задание</b> - выполните задание и получите баллы
• 📊 <b>Мой профиль</b> - ваша статистика и достижения
• 🏆 <b>ТОП-10</b> - рейтинг лучших игроков
• 📋 <b>Мои задания</b> - история ваших заданий
• 🏅 <b>Мои значки</b> - коллекция ваших наград
• 🎰 <b>Активные розыгрыши</b> - участвуйте и выигрывайте призы
• ✏️ <b>Мой никнейм</b> - настройте ваш никнейм
• 🏆 <b>Мои победы</b> - история ваших побед в розыгрышах
• ❓ <b>Помощь</b> - справка по использованию
{admin_features}
{drawings_text}

<b>💎 Система баллов:</b>
Каждое задание дает 5 баллов. Накопите баллы для получения уникальных значков и участия в розыгрышах!

<b>🎰 Система розыгрышей:</b>
Участвуйте в розыгрышах призов! Для участия могут потребоваться:
• Определенное количество баллов
• Специальные значки
• Минимальное количество участников

<b>🚀 Начните прямо сейчас!</b>
Нажмите "🎮 Отправить задание" для начала.
    """
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /help"""
    help_text = """
<b>📚 СПРАВКА ПО СИСТЕМЕ</b>
══════════════════════════════

<b>🎮 КАК РАБОТАЕТ СИСТЕМА:</b>
1. Выберите тип задания из списка
2. Отправьте скриншот выполнения
3. Укажите количество выполнений
4. Дождитесь проверки администратором
5. Получите баллы на свой счет

<b>📋 ТИПЫ ЗАДАНИЙ:</b>
"""
    
    # Добавляем информацию о заданиях
    for task_id, task_info in TASK_TYPES.items():
        points = task_info['points']
        emoji = task_info['emoji']
        name = task_info['name']
        max_per_day = task_info.get('max_per_day', 'безлимит')
        
        help_text += f"• <b>{emoji} {name}</b> - {points} баллов/шт (лимит: {max_per_day}/день)\n"
    
    help_text += """
<b>🏆 СИСТЕМА РЕЙТИНГА:</b>
• Баллы начисляются за выполненные задания
• Значки выдаются за особые достижения
• Топ игроков обновляется в реальном времени

<b>🎰 СИСТЕМА РОЗЫГРЫШЕЙ:</b>
• Периодически проводятся розыгрыши призов
• Участвуйте в розыгрышах для получения уникальных наград
• Победители определяются случайным образом
• Для участия могут потребоваться баллы или значки

<b>❓ ЧАСТЫЕ ВОПРОСЫ:</b>
<b>Q:</b> Сколько времени занимает проверка задания?
<b>A:</b> Обычно до 5 часов, чаще всего быстрее.

<b>Q:</b> Как участвовать в розыгрышах?
<b>A:</b> Перейдите в раздел "🎰 Активные розыгрыши" и нажмите "Участвовать"

<b>Q:</b> Что делать если задание отклонено?
<b>A:</b> Проверьте причину отклонения и отправьте исправленный вариант.

<b>📧 ПОДДЕРЖКА:</b>
Если у вас возникли проблемы, обратитесь к администратору.
    """
    
    await update.message.reply_text(
        help_text,
        parse_mode=ParseMode.HTML,
        reply_markup=create_user_keyboard()
    )

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /cancel"""
    await update.message.reply_text(
        "❌ Операция отменена.",
        reply_markup=create_user_keyboard()
    )
    return ConversationHandler.END

# ========== ФУНКЦИИ ДЛЯ УЧАСТНИКОВ ==========
async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать профиль пользователя"""
    user_id = update.effective_user.id
    
    # Получаем данные пользователя
    user = db.get_user(user_id)
    if not user:
        await update.message.reply_text("❌ Пользователь не найден!")
        return
    
    # Получаем статистику
    stats = db.get_user_stats(user_id)
    drawings_stats = db.get_user_drawings_stats(user_id)
    
    # Рассчитываем позицию в топе
    top_users = db.get_top_users(1000)
    position = 1
    for top_user in top_users:
        if top_user['user_id'] == user_id:
            break
        position += 1
    
    # Форматируем никнейм
    display_name = f"{user.get('custom_emoji', '')} {user['nickname']}".strip()
    
    # Рассчитываем эффективность
    total_processed = stats['approved'] + stats['rejected']
    efficiency = (stats['approved'] / total_processed * 100) if total_processed > 0 else 0
    
    # Дни в системе
    join_date = user['join_date']
    if isinstance(join_date, str):
        join_date = datetime.fromisoformat(join_date.replace('Z', '+00:00'))
    days_in_system = (datetime.now() - join_date).days
    
    # Формируем текст профиля
    profile_text = f"""
👤 <b>ПРОФИЛЬ ИГРОКА</b>
══════════════════════════════

<b>{display_name}</b>
{'─' * 30}

<b>📊 ОСНОВНАЯ ИНФОРМАЦИЯ</b>
🆔 ID: <code>{user_id}</code>
📅 В системе: {days_in_system} дней
🏆 Рейтинг: #{position}
💰 Баланс: <code>{format_number(user['total_points'])}</code> баллов

<b>📈 СТАТИСТИКА ВЫПОЛНЕНИЯ</b>
✅ Выполнено: {stats['approved']} заданий
⏳ На проверке: {stats['pending']} заданий  
❌ Отклонено: {stats['rejected']} заданий
📊 Эффективность: {efficiency:.1f}%

<b>🎰 СТАТИСТИКА РОЗЫГРЫШЕЙ</b>
📋 Участий: {drawings_stats['total_participations']}
🏆 Побед: {drawings_stats['drawings_won']}
🎖️ Места: {', '.join(drawings_stats['winning_places']) if drawings_stats['winning_places'] else 'нет'}

<b>📅 СЕГОДНЯ</b>
🎯 Отправлено заданий: {user.get('daily_tasks_count', 0)}
📋 Можно отправить еще: {10 - user.get('daily_tasks_count', 0)}
👨‍👩‍👧‍👦 Сем. контрактов: {user.get('daily_family_contracts', 0)}/10
    """
    
    # Добавляем значки если есть
    badges = user.get('badges', [])
    if badges:
        profile_text += f"\n<b>🏅 ЗНАЧКИ ({len(badges)})</b>\n"
        badges_display = []
        for badge_id in badges[:10]:  # Ограничиваем 10 значками в профиле
            badge = BADGES.get(badge_id, {'emoji': '🏅'})
            badges_display.append(badge['emoji'])
        
        profile_text += " ".join(badges_display)
        
        if len(badges) > 10:
            profile_text += f"\n<i>...и еще {len(badges) - 10} значков</i>"
    
    # Кнопки для профиля
    keyboard = []
    if badges:
        keyboard.append([InlineKeyboardButton("🏅 Показать все значки", callback_data="show_all_badges")])
    
    if user.get('custom_emoji'):
        keyboard.append([InlineKeyboardButton("🎭 Изменить эмодзи", callback_data="change_emoji")])
    
    if drawings_stats['total_participations'] > 0:
        keyboard.append([InlineKeyboardButton("🏆 Мои победы", callback_data="my_wins")])
    
    keyboard.append([InlineKeyboardButton("🎰 Активные розыгрыши", callback_data="active_drawings")])
    
    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    
    await update.message.reply_text(
        profile_text,
        parse_mode=ParseMode.HTML,
        reply_markup=reply_markup,
        disable_web_page_preview=True
    )

async def show_my_wins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать победы пользователя в розыгрышах"""
    user_id = update.effective_user.id
    
    # Получаем все розыгрыши
    finished_drawings = db.get_finished_drawings(limit=50)
    
    # Находим розыгрыши, где пользователь победил
    user_wins = []
    for drawing in finished_drawings:
        winners = drawing['winners']
        for place, winner_id in winners.items():
            if winner_id == user_id:
                user_wins.append({
                    'drawing': drawing,
                    'place': place
                })
    
    if not user_wins:
        await update.message.reply_text(
            """
🏆 <b>МОИ ПОБЕДЫ</b>
══════════════════════════════

📭 У вас пока нет побед в розыгрышах.

🎰 <b>Как выиграть?</b>
• Участвуйте в активных розыгрышах
• Выполняйте задания для получения баллов
• Получайте значки для доступа к специальным розыгрышам
• Чем больше участвуете - тем выше шанс выиграть!

🚀 <b>Участвуйте и побеждайте!</b>
            """,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🎰 Активные розыгрыши", callback_data="active_drawings"),
                InlineKeyboardButton("🔙 В профиль", callback_data="back_to_profile")
            ]])
        )
        return
    
    wins_text = f"""
🏆 <b>МОИ ПОБЕДЫ</b>
══════════════════════════════

Всего побед: <code>{len(user_wins)}</code>

<b>🏅 История побед:</b>

"""
    
    for i, win in enumerate(user_wins[:10]):  # Показываем последние 10 побед
        drawing = win['drawing']
        place = win['place']
        
        place_emoji = {
            '1': '🥇',
            '2': '🥈', 
            '3': '🥉',
            '4': '4️⃣',
            '5': '5️⃣'
        }.get(str(place), '🎖️')
        
        wins_text += f"{place_emoji} <b>{drawing['name']}</b>\n"
        wins_text += f"   🏆 Место: {place}\n"
        wins_text += f"   🎁 Приз: {drawing['prize']}\n"
        wins_text += f"   📅 Дата: {format_date(drawing['end_date'])}\n"
        
        # Участники
        participants = drawing['participants']
        if participants:
            wins_text += f"   👥 Участников: {len(participants)}\n"
        
        wins_text += "\n"
    
    if len(user_wins) > 10:
        wins_text += f"\n<i>...и еще {len(user_wins) - 10} побед</i>"
    
    keyboard = [
        [InlineKeyboardButton("🎰 Активные розыгрыши", callback_data="active_drawings")],
        [InlineKeyboardButton("🔙 В профиль", callback_data="back_to_profile")]
    ]
    
    await update.message.reply_text(
        wins_text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard),
        disable_web_page_preview=True
    )

# ========== СИСТЕМА РОЗЫГРЫШЕЙ ==========
async def show_active_drawings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать активные розыгрыши"""
    active_drawings = db.get_active_drawings()
    
    if not active_drawings:
        await update.message.reply_text(
            """
🎰 <b>АКТИВНЫЕ РОЗЫГРЫШИ</b>
══════════════════════════════

📭 Сейчас нет активных розыгрышей.

✨ <b>Следите за новостями!</b>
Новые розыгрыши будут анонсированы заранее.

🎁 <b>Как подготовиться?</b>
• Выполняйте задания для получения баллов
• Получайте значки за достижения
• Участвуйте в регулярных активностях
            """,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu")
            ]])
        )
        return
    
    text = """
🎰 <b>АКТИВНЫЕ РОЗЫГРЫШИ</b>
══════════════════════════════

"""
    
    for drawing in active_drawings[:5]:  # Показываем максимум 5 розыгрышей
        name = drawing['name']
        description = drawing['description'] or 'Без описания'
        prize = drawing['prize']
        start_date = format_date(drawing['start_date'])
        end_date = format_date(drawing['end_date'])
        participants = len(drawing['participants'])
        max_participants = drawing['max_participants']
        
        # Время до конца
        time_left = datetime.fromisoformat(drawing['end_date']) - datetime.now()
        time_left_str = format_timedelta(time_left)
        
        # Требования для участия
        requirements = []
        if drawing['entry_cost'] > 0:
            requirements.append(f"💳 {drawing['entry_cost']} баллов")
        if drawing['required_badges']:
            badges_text = ", ".join([BADGES.get(b, {'name': b})['name'] for b in drawing['required_badges'][:2]])
            if len(drawing['required_badges']) > 2:
                badges_text += f" и еще {len(drawing['required_badges'])-2}"
            requirements.append(f"🏅 {badges_text}")
        
        text += f"<b>🎁 {name}</b>\n"
        text += f"📝 {description}\n"
        text += f"🏆 Приз: {prize}\n"
        text += f"⏰ Осталось: {time_left_str}\n"
        text += f"👥 Участники: {participants}/{max_participants}\n"
        
        if requirements:
            text += f"📋 Требования: {', '.join(requirements)}\n"
        
        text += "─" * 30 + "\n"
    
    # Кнопки
    keyboard = []
    for drawing in active_drawings[:5]:
        keyboard.append([
            InlineKeyboardButton(
                f"🎰 {drawing['name'][:20]}",
                callback_data=f"drawing_view_{drawing['drawing_id']}"
            )
        ])
    
    keyboard.append([
        InlineKeyboardButton("🏆 Победители прошлых розыгрышей", callback_data="past_winners"),
        InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu")
    ])
    
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard),
        disable_web_page_preview=True
    )

async def show_drawing_details(update: Update, context: ContextTypes.DEFAULT_TYPE, drawing_id: int = None):
    """Показать детали розыгрыша"""
    if not drawing_id:
        query = update.callback_query
        await query.answer()
        drawing_id = int(query.data.replace("drawing_view_", ""))
    
    drawing = db.get_drawing(drawing_id=drawing_id)
    user_id = update.effective_user.id
    
    if not drawing:
        if 'query' in locals():
            await query.edit_message_text("❌ Розыгрыш не найден!")
        else:
            await update.message.reply_text("❌ Розыгрыш не найден!")
        return
    
    name = drawing['name']
    description = drawing['description'] or 'Без описания'
    prize = drawing['prize']
    start_date = format_date(drawing['start_date'])
    end_date = format_date(drawing['end_date'])
    participants = len(drawing['participants'])
    max_participants = drawing['max_participants']
    min_participants = drawing['min_participants']
    
    # Время до конца
    time_left = datetime.fromisoformat(drawing['end_date']) - datetime.now()
    time_left_str = format_timedelta(time_left)
    
    # Статус розыгрыша
    status_emoji = {
        'announced': '🟡',
        'active': '🟢',
        'finished': '🔴',
        'cancelled': '⚫'
    }.get(drawing['status'], '❓')
    
    status_text = {
        'announced': 'Объявлен',
        'active': 'Активен',
        'finished': 'Завершен',
        'cancelled': 'Отменен'
    }.get(drawing['status'], 'Неизвестно')
    
    text = f"""
🎰 <b>РОЗЫГРЫШ: {name}</b>
══════════════════════════════

{status_emoji} <b>Статус:</b> {status_text}
📝 <b>Описание:</b> {description}
🏆 <b>Приз:</b> {prize}

📅 <b>Даты проведения:</b>
Начало: {start_date}
Окончание: {end_date}
⏰ <b>Осталось времени:</b> {time_left_str}

👥 <b>Участники:</b>
Зарегистрировано: {participants} из {max_participants}
Минимум для проведения: {min_participants}

📋 <b>Условия участия:</b>
"""
    
    # Требования для участия
    requirements = []
    if drawing['entry_cost'] > 0:
        requirements.append(f"• 💳 <b>Взнос:</b> {drawing['entry_cost']} баллов")
    if drawing['required_badges']:
        badges_text = ", ".join([BADGES.get(b, {'name': b, 'emoji': '🏅'})['emoji'] + " " + 
                               BADGES.get(b, {'name': b})['name'] for b in drawing['required_badges']])
        requirements.append(f"• 🏅 <b>Необходимые значки:</b> {badges_text}")
    
    if requirements:
        text += "\n".join(requirements) + "\n"
    else:
        text += "• 🎫 <b>Без специальных требований</b>\n"
    
    # Проверяем, может ли пользователь участвовать
    user = db.get_user(user_id)
    can_participate = False
    participation_reason = ""
    
    if drawing['status'] == 'active':
        # Проверяем требования
        if drawing['entry_cost'] > 0 and user['total_points'] < drawing['entry_cost']:
            participation_reason = f"❌ Недостаточно баллов. Нужно: {drawing['entry_cost']}, у вас: {user['total_points']}"
        elif drawing['required_badges']:
            user_badges = user.get('badges', [])
            missing_badges = [b for b in drawing['required_badges'] if b not in user_badges]
            if missing_badges:
                missing_names = [BADGES.get(b, {'name': b})['name'] for b in missing_badges]
                participation_reason = f"❌ Не хватает значков: {', '.join(missing_names)}"
            else:
                can_participate = True
                participation_reason = "✅ Вы можете участвовать!"
        else:
            can_participate = True
            participation_reason = "✅ Вы можете участвовать!"
        
        # Проверяем, не участвует ли уже
        if user_id in drawing['participants']:
            can_participate = False
            ticket_number = drawing['ticket_numbers'].get(user_id, 0)
            participation_reason = f"✅ Вы уже участвуете! Ваш билет №{ticket_number}"
    
    text += f"\n<b>🎫 Ваш статус:</b> {participation_reason}"
    
    # Кнопки
    if 'query' in locals():
        await query.edit_message_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=create_drawing_participation_keyboard(drawing_id, user_id, can_participate),
            disable_web_page_preview=True
        )
    else:
        await update.message.reply_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=create_drawing_participation_keyboard(drawing_id, user_id, can_participate),
            disable_web_page_preview=True
        )

async def participate_in_drawing(update: Update, context: ContextTypes.DEFAULT_TYPE, drawing_id: int = None):
    """Участие в розыгрыше"""
    if not drawing_id:
        query = update.callback_query
        await query.answer()
        drawing_id = int(query.data.replace("drawing_participate_", ""))
    
    drawing = db.get_drawing(drawing_id=drawing_id)
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    
    if not drawing:
        if 'query' in locals():
            await query.answer("❌ Розыгрыш не найден!")
        return
    
    # Проверяем статус розыгрыша
    if drawing['status'] != 'active':
        if 'query' in locals():
            await query.answer("❌ Розыгрыш не активен!")
        return
    
    # Проверяем требования
    if drawing['entry_cost'] > 0 and user['total_points'] < drawing['entry_cost']:
        if 'query' in locals():
            await query.answer(f"❌ Недостаточно баллов! Нужно: {drawing['entry_cost']}")
        return
    
    if drawing['required_badges']:
        user_badges = user.get('badges', [])
        missing_badges = [b for b in drawing['required_badges'] if b not in user_badges]
        if missing_badges:
            if 'query' in locals():
                await query.answer("❌ Не хватает необходимых значков!")
            return
    
    # Проверяем, не участвует ли уже
    if user_id in drawing['participants']:
        if 'query' in locals():
            await query.answer("❌ Вы уже участвуете в этом розыгрыше!")
        return
    
    # Проверяем максимальное количество участников
    if len(drawing['participants']) >= drawing['max_participants']:
        if 'query' in locals():
            await query.answer("❌ Достигнуто максимальное количество участников!")
        return
    
    # Списываем баллы если требуется
    if drawing['entry_cost'] > 0:
        db.update_user_points(user_id, -drawing['entry_cost'], None, f"Участие в розыгрыше: {drawing['name']}")
    
    # Добавляем участника
    success = db.add_drawing_participant(drawing_id, user_id)
    
    if success:
        # Получаем обновленные данные розыгрыша
        drawing = db.get_drawing(drawing_id=drawing_id)
        ticket_number = drawing['ticket_numbers'].get(user_id, 0)
        
        if 'query' in locals():
            await query.answer(f"✅ Вы успешно зарегистрированы! Ваш билет №{ticket_number}")
            
            # Обновляем сообщение
            await show_drawing_details(update, context, drawing_id)
        
        # Уведомляем администраторов
        notification_text = f"""
🎫 <b>НОВЫЙ УЧАСТНИК РОЗЫГРЫША!</b>

🎰 Розыгрыш: <b>{drawing['name']}</b>
👤 Участник: {user.get('nickname', 'Неизвестно')}
🆔 ID: <code>{user_id}</code>
🎫 Билет №: {ticket_number}
👥 Всего участников: {len(drawing['participants'])}/{drawing['max_participants']}

<b>🎁 Приз:</b> {drawing['prize']}
        """
        
        await notify_admins(context.bot, notification_text, exclude_id=user_id)
        
    else:
        if 'query' in locals():
            await query.answer("❌ Ошибка при регистрации!")# ========== АДМИНИСТРАТИВНЫЕ ФУНКЦИИ ==========
def admin_required(func):
    """Декоратор для проверки прав администратора"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user_id = update.effective_user.id
        
        if not is_admin(user_id):
            if update.callback_query:
                await update.callback_query.answer("⛔ У вас нет прав администратора!", show_alert=True)
            else:
                await update.message.reply_text("⛔ У вас нет прав администратора!")
            return
        
        return await func(update, context, *args, **kwargs)
    return wrapper

async def admin_dashboard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Панель администратора"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("⛔ У вас нет прав администратора!")
        return
    
    # Получаем статистику
    with db.get_cursor() as cursor:
        cursor.execute('SELECT COUNT(*) as total_users FROM users WHERE is_banned = 0')
        total_users = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) as pending_tasks FROM tasks WHERE status = "pending"')
        pending_tasks = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(*) as active_drawings FROM drawings WHERE status = "active"')
        active_drawings = cursor.fetchone()[0]
        
        cursor.execute('SELECT SUM(total_points) as total_points FROM users WHERE is_banned = 0')
        total_points = cursor.fetchone()[0] or 0
        
        cursor.execute('''
            SELECT COUNT(*) as today_tasks 
            FROM tasks 
            WHERE DATE(created_at) = DATE('now')
        ''')
        today_tasks = cursor.fetchone()[0]
    
    text = f"""
👑 <b>ПАНЕЛЬ АДМИНИСТРАТОРА</b>
══════════════════════════════

📊 <b>Общая статистика:</b>
👥 Участников: <code>{format_number(total_users)}</code>
📋 Заданий на проверке: <code>{format_number(pending_tasks)}</code>
🎰 Активных розыгрышей: <code>{format_number(active_drawings)}</code>
💰 Всего баллов в системе: <code>{format_number(total_points)}</code>
📅 Заданий сегодня: <code>{format_number(today_tasks)}</code>

⚡ <b>Быстрые действия:</b>
"""
    
    # Кнопки быстрых действий
    keyboard = create_admin_management_keyboard()
    
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard,
        disable_web_page_preview=True
    )

async def check_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Проверить задания на модерации"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("⛔ У вас нет прав администратора!")
        return
    
    pending_tasks = db.get_pending_tasks(limit=10)
    
    if not pending_tasks:
        await update.message.reply_text(
            """
✅ <b>ПРОВЕРКА ЗАДАНИЙ</b>
══════════════════════════════

📭 На данный момент нет заданий на проверке.

🎯 <b>Что можно сделать:</b>
• Подождать новых заданий от участников
• Проверить статистику участников
• Создать новый розыгрыш
• Отправить рассылку участникам
            """,
            parse_mode=ParseMode.HTML,
            reply_markup=create_admin_management_keyboard()
        )
        return
    
    text = f"""
✅ <b>ПРОВЕРКА ЗАДАНИЙ</b>
══════════════════════════════

📋 Заданий на проверке: <code>{len(pending_tasks)}</code>

<b>📝 Последние задания:</b>
"""
    
    # Показываем 3 последних задания
    for task in pending_tasks[:3]:
        task_type = TASK_TYPES.get(task['task_type'], {'name': task['task_type'], 'emoji': '📝'})
        user_nickname = task.get('nickname') or task.get('username') or f"User_{task['user_id']}"
        created_at = format_date(task['created_at'])
        
        text += f"\n<b>{task_type['emoji']} {task_type['name']}</b>"
        text += f"\n👤 {user_nickname}"
        text += f"\n🎯 Баллов: {task['points']} × {task.get('count', 1)} = {task['points'] * task.get('count', 1)}"
        text += f"\n📅 {created_at}"
        
        if task.get('comment'):
            text += f"\n💬 {task['comment'][:50]}..."
        
        text += f"\n{'─' * 25}"
    
    if len(pending_tasks) > 3:
        text += f"\n\n<i>...и еще {len(pending_tasks) - 3} заданий</i>"
    
    # Кнопки
    keyboard = []
    for task in pending_tasks[:5]:  # Максимум 5 кнопок
        task_type = TASK_TYPES.get(task['task_type'], {'name': task['task_type'][:10]})
        keyboard.append([
            InlineKeyboardButton(
                f"👤 {task['task_id']} | {task_type['name'][:15]}",
                callback_data=f"admin_review_task_{task['task_id']}"
            )
        ])
    
    keyboard.append([
        InlineKeyboardButton("🔄 Обновить список", callback_data="admin_refresh_tasks"),
        InlineKeyboardButton("📋 Все задания", callback_data="admin_all_tasks")
    ])
    
    keyboard.append([
        InlineKeyboardButton("🔙 Назад", callback_data="admin_back_to_dashboard")
    ])
    
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard),
        disable_web_page_preview=True
    )

async def review_task(update: Update, context: ContextTypes.DEFAULT_TYPE, task_id: int = None):
    """Просмотр и проверка задания"""
    query = update.callback_query
    await query.answer()
    
    if not task_id:
        task_id = int(query.data.replace("admin_review_task_", ""))
    
    task = None
    with db.get_cursor() as cursor:
        cursor.execute('''
            SELECT t.*, u.nickname, u.username, u.user_id, u.total_points
            FROM tasks t 
            JOIN users u ON t.user_id = u.user_id 
            WHERE t.task_id = ?
        ''', (task_id,))
        row = cursor.fetchone()
        if row:
            task = dict(row)
    
    if not task:
        await query.edit_message_text("❌ Задание не найдено!")
        return
    
    task_type = TASK_TYPES.get(task['task_type'], {'name': task['task_type'], 'emoji': '📝', 'description': ''})
    
    text = f"""
✅ <b>ПРОВЕРКА ЗАДАНИЯ #{task_id}</b>
══════════════════════════════

<b>📋 Информация о задании:</b>
🎮 Тип: {task_type['emoji']} {task_type['name']}
👤 Участник: {task.get('nickname', 'Неизвестно')}
🆔 ID: <code>{task['user_id']}</code>
💰 Текущий баланс: <code>{format_number(task['total_points'])}</code>

<b>📊 Детали задания:</b>
🎯 Баллов за единицу: {task['points']}
📊 Количество: {task.get('count', 1)}
💰 Всего баллов: {task['points'] * task.get('count', 1)}
📅 Отправлено: {format_date(task['created_at'])}

"""
    
    if task.get('comment'):
        text += f"💬 <b>Комментарий:</b>\n{task['comment']}\n\n"
    
    if task.get('screenshot_path'):
        text += f"📸 <b>Скриншот:</b> прикреплен\n"
    else:
        text += f"📸 <b>Скриншот:</b> не прикреплен\n"
    
    text += f"\n<b>📝 Описание задания:</b>\n{task_type.get('description', '')}"
    
    # Получаем статистику пользователя по этому типу задания
    with db.get_cursor() as cursor:
        cursor.execute('''
            SELECT COUNT(*) as total, 
                   SUM(CASE WHEN status = 'approved' THEN 1 ELSE 0 END) as approved,
                   SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as rejected
            FROM tasks 
            WHERE user_id = ? AND task_type = ?
        ''', (task['user_id'], task['task_type']))
        stats = cursor.fetchone()
    
    if stats:
        text += f"""
        
📈 <b>Статистика пользователя по этому типу:</b>
📊 Всего отправлено: {stats[0]}
✅ Одобрено: {stats[1]}
❌ Отклонено: {stats[2]}
"""
    
    # Кнопки
    keyboard = [
        [
            InlineKeyboardButton("✅ Одобрить", callback_data=f"admin_approve_task_{task_id}"),
            InlineKeyboardButton("❌ Отклонить", callback_data=f"admin_reject_task_{task_id}")
        ],
        [
            InlineKeyboardButton("👤 Профиль участника", callback_data=f"admin_view_user_{task['user_id']}"),
            InlineKeyboardButton("📋 Все задания участника", callback_data=f"admin_user_tasks_{task['user_id']}")
        ],
        [
            InlineKeyboardButton("🔄 Следующее задание", callback_data="admin_next_task"),
            InlineKeyboardButton("🔙 К списку", callback_data="admin_back_to_tasks")
        ]
    ]
    
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard),
        disable_web_page_preview=True
    )
    
    # Отправляем скриншот если есть
    if task.get('screenshot_path') and os.path.exists(task['screenshot_path']):
        try:
            await context.bot.send_photo(
                chat_id=query.message.chat_id,
                photo=open(task['screenshot_path'], 'rb'),
                caption=f"📸 Скриншот к заданию #{task_id}",
                reply_to_message_id=query.message.message_id
            )
        except Exception as e:
            logger.error(f"Ошибка отправки скриншота: {e}")

async def approve_task_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Одобрить задание"""
    query = update.callback_query
    await query.answer()
    
    task_id = int(query.data.replace("admin_approve_task_", ""))
    admin_id = query.from_user.id
    
    # Одобряем задание
    success = db.approve_task(task_id, admin_id)
    
    if success:
        # Получаем информацию о задании для уведомления
        with db.get_cursor() as cursor:
            cursor.execute('''
                SELECT t.user_id, t.task_type, t.points, t.count, u.nickname
                FROM tasks t 
                JOIN users u ON t.user_id = u.user_id 
                WHERE t.task_id = ?
            ''', (task_id,))
            task_info = cursor.fetchone()
        
        if task_info:
            user_id, task_type, points, count, nickname = task_info
            total_points = points * count
            
            # Уведомляем пользователя
            notification_text = f"""
✅ <b>ВАШЕ ЗАДАНИЕ ОДОБРЕНО!</b>

🎮 Тип задания: {TASK_TYPES.get(task_type, {'name': task_type})['name']}
💰 Начислено баллов: <code>{format_number(total_points)}</code>
📅 Время проверки: {format_date(datetime.now().isoformat())}

🎯 <b>Текущий баланс:</b> <code>{format_number(db.get_user(user_id)['total_points'])}</code>

🚀 Продолжайте в том же духе!
            """
            
            await send_notification(context.bot, user_id, notification_text)
        
        await query.answer("✅ Задание одобрено и баллы начислены!", show_alert=True)
        await query.edit_message_text(
            "✅ <b>Задание успешно одобрено!</b>\n\nБаллы начислены участнику.",
            parse_mode=ParseMode.HTML
        )
        
        # Переходим к следующему заданию
        await check_tasks(update, context)
    else:
        await query.answer("❌ Ошибка при одобрении задания!", show_alert=True)

async def reject_task_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отклонить задание"""
    query = update.callback_query
    await query.answer()
    
    task_id = int(query.data.replace("admin_reject_task_", ""))
    
    # Сохраняем task_id в контексте
    context.user_data['reject_task_id'] = task_id
    context.user_data['reject_admin_id'] = query.from_user.id
    
    await query.edit_message_text(
        """
❌ <b>ОТКЛОНЕНИЕ ЗАДАНИЯ</b>
══════════════════════════════

📝 Пожалуйста, укажите причину отклонения задания.

💡 <b>Примеры причин:</b>
• Несоответствующий скриншот
• Нарушение правил выполнения
• Неверное количество выполнений
• Дублирование задания
• Нечитаемый скриншот

✏️ <b>Отправьте причину одним сообщением:</b>
        """,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Назад к заданию", callback_data=f"admin_review_task_{task_id}")
        ]])
    )
    
    return ADMIN_REVIEW_TASK

async def process_task_rejection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработать причину отклонения задания"""
    reason = update.message.text.strip()
    task_id = context.user_data.get('reject_task_id')
    admin_id = context.user_data.get('reject_admin_id')
    
    if not task_id or not reason:
        await update.message.reply_text("❌ Ошибка: данные не найдены!")
        return ConversationHandler.END
    
    # Отклоняем задание
    success = db.reject_task(task_id, admin_id, reason)
    
    if success:
        # Получаем информацию о задании для уведомления
        with db.get_cursor() as cursor:
            cursor.execute('''
                SELECT t.user_id, t.task_type, u.nickname
                FROM tasks t 
                JOIN users u ON t.user_id = u.user_id 
                WHERE t.task_id = ?
            ''', (task_id,))
            task_info = cursor.fetchone()
        
        if task_info:
            user_id, task_type, nickname = task_info
            
            # Уведомляем пользователя
            notification_text = f"""
❌ <b>ВАШЕ ЗАДАНИЕ ОТКЛОНЕНО</b>

🎮 Тип задания: {TASK_TYPES.get(task_type, {'name': task_type})['name']}
📝 Причина: {reason}
📅 Время проверки: {format_date(datetime.now().isoformat())}

💡 <b>Что делать дальше:</b>
1. Исправьте указанные ошибки
2. Отправьте задание заново
3. Убедитесь, что скриншот соответствует требованиям

🚀 <b>Требования к заданиям:</b>
• Четкий скриншот
• Соответствие описанию задания
• Правильное количество выполнений
• Отсутствие нарушений правил

🔄 <b>Попробуйте еще раз!</b>
            """
            
            await send_notification(context.bot, user_id, notification_text)
        
        await update.message.reply_text(
            f"✅ <b>Задание #{task_id} отклонено!</b>\n\nПричина отправлена участнику.",
            parse_mode=ParseMode.HTML
        )
        
        # Возвращаемся к проверке заданий
        await check_tasks(update, context)
    else:
        await update.message.reply_text("❌ Ошибка при отклонении задания!")
    
    # Очищаем контекст
    context.user_data.pop('reject_task_id', None)
    context.user_data.pop('reject_admin_id', None)
    
    return ConversationHandler.END

async def search_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Поиск участника"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("⛔ У вас нет прав администратора!")
        return
    
    await update.message.reply_text(
        """
🔍 <b>ПОИСК УЧАСТНИКА</b>
══════════════════════════════

📝 Введите данные для поиска:

💡 <b>Что можно искать:</b>
• Никнейм (полностью или частично)
• Username (с @ или без)
• Имя или фамилию
• ID пользователя

✏️ <b>Отправьте поисковый запрос:</b>

🔄 <b>Примеры:</b>
• <code>Иван</code> - поиск по имени
• <code>@username</code> - поиск по username
• <code>геймер</code> - поиск по никнейму
• <code>123456789</code> - поиск по ID
        """,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Назад", callback_data="admin_back_to_dashboard")
        ]])
    )
    
    return ADMIN_SEARCH_USER

async def process_user_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка поиска пользователя"""
    search_term = update.message.text.strip()
    
    # Если поиск по ID
    if search_term.isdigit():
        user_id = int(search_term)
        user = db.get_user(user_id)
        
        if user:
            await show_user_profile(update, context, user_id)
            return ConversationHandler.END
        else:
            await update.message.reply_text(f"❌ Пользователь с ID <code>{user_id}</code> не найден!", parse_mode=ParseMode.HTML)
            return ADMIN_SEARCH_USER
    
    # Поиск по тексту
    users = db.search_users(search_term, limit=10)
    
    if not users:
        await update.message.reply_text(
            f"❌ По запросу '<b>{search_term}</b>' ничего не найдено.\n\nПопробуйте другой запрос:",
            parse_mode=ParseMode.HTML
        )
        return ADMIN_SEARCH_USER
    
    text = f"""
🔍 <b>РЕЗУЛЬТАТЫ ПОИСКА</b>
══════════════════════════════

🔎 Запрос: <code>{search_term}</code>
👥 Найдено: <code>{len(users)}</code> участников

<b>📋 Результаты:</b>
"""
    
    for i, user in enumerate(users[:8], 1):
        display_name = user.get('nickname') or user.get('username') or user.get('first_name') or f"User_{user['user_id']}"
        points = user.get('total_points', 0)
        
        text += f"\n<b>{i}.</b> {display_name}"
        text += f"\n   🆔 ID: <code>{user['user_id']}</code>"
        text += f"\n   💰 Баллы: <code>{format_number(points)}</code>"
        text += f"\n   {'─' * 25}"
    
    if len(users) > 8:
        text += f"\n\n<i>...и еще {len(users) - 8} участников</i>"
    
    # Кнопки
    keyboard = []
    for user in users[:5]:  # Максимум 5 кнопок
        display_name = user.get('nickname') or user.get('username') or f"User_{user['user_id']}"
        keyboard.append([
            InlineKeyboardButton(
                f"👤 {display_name[:15]} | {format_number(user['total_points'])}",
                callback_data=f"admin_view_user_{user['user_id']}"
            )
        ])
    
    keyboard.append([
        InlineKeyboardButton("🔄 Новый поиск", callback_data="admin_search_again"),
        InlineKeyboardButton("🔙 Назад", callback_data="admin_back_to_dashboard")
    ])
    
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard),
        disable_web_page_preview=True
    )
    
    return ConversationHandler.END

async def show_user_profile(update: Update, context: ContextTypes.DEFAULT_TYPE, target_user_id: int = None):
    """Показать профиль пользователя для админа"""
    if not target_user_id:
        if update.callback_query:
            query = update.callback_query
            await query.answer()
            target_user_id = int(query.data.replace("admin_view_user_", ""))
        else:
            await update.message.reply_text("❌ Укажите ID пользователя!")
            return
    
    # Проверяем права
    admin_id = update.effective_user.id
    if not is_admin(admin_id):
        if update.callback_query:
            await query.answer("⛔ У вас нет прав администратора!", show_alert=True)
        return
    
    user = db.get_user(target_user_id)
    if not user:
        if 'query' in locals():
            await query.edit_message_text("❌ Пользователь не найден!")
        else:
            await update.message.reply_text("❌ Пользователь не найден!")
        return
    
    # Получаем статистику
    stats = db.get_user_stats(target_user_id)
    drawings_stats = db.get_user_drawings_stats(target_user_id)
    admin_operations = db.get_admin_operations(target_user_id, limit=5)
    
    # Форматируем никнейм
    display_name = f"{user.get('custom_emoji', '')} {user['nickname']}".strip()
    if user.get('is_banned'):
        display_name = f"🚫 {display_name}"
    
    # Рассчитываем эффективность
    total_processed = stats['approved'] + stats['rejected']
    efficiency = (stats['approved'] / total_processed * 100) if total_processed > 0 else 0
    
    # Дни в системе
    join_date = user['join_date']
    if isinstance(join_date, str):
        join_date = datetime.fromisoformat(join_date.replace('Z', '+00:00'))
    days_in_system = (datetime.now() - join_date).days
    
    # Последняя активность
    last_active = user['last_active']
    if last_active:
        if isinstance(last_active, str):
            last_active = datetime.fromisoformat(last_active.replace('Z', '+00:00'))
        last_active_str = format_date(last_active)
        last_active_delta = datetime.now() - last_active
        days_inactive = last_active_delta.days
    else:
        last_active_str = "Неизвестно"
        days_inactive = None
    
    # Формируем текст профиля
    profile_text = f"""
👤 <b>ПРОФИЛЬ УЧАСТНИКА</b>
══════════════════════════════

<b>{display_name}</b>
{'─' * 30}

<b>📊 ОСНОВНАЯ ИНФОРМАЦИЯ</b>
🆔 ID: <code>{target_user_id}</code>
📅 В системе: {days_in_system} дней
📝 Никнейм: {user['nickname']}
👤 Username: @{user.get('username', 'не указан')}
👥 Имя: {user.get('first_name', 'не указано')} {user.get('last_name', 'не указано')}
💰 Баланс: <code>{format_number(user['total_points'])}</code> баллов

<b>📈 СТАТИСТИКА ВЫПОЛНЕНИЯ</b>
✅ Выполнено: {stats['approved']} заданий
⏳ На проверке: {stats['pending']} заданий  
❌ Отклонено: {stats['rejected']} заданий
📊 Эффективность: {efficiency:.1f}%

<b>🎰 СТАТИСТИКА РОЗЫГРЫШЕЙ</b>
📋 Участий: {drawings_stats['total_participations']}
🏆 Побед: {drawings_stats['drawings_won']}
🎖️ Места: {', '.join(drawings_stats['winning_places']) if drawings_stats['winning_places'] else 'нет'}

<b>📅 АКТИВНОСТЬ</b>
📅 Дата регистрации: {format_date(join_date)}
🕐 Последняя активность: {last_active_str}
"""
    
    if days_inactive is not None:
        if days_inactive == 0:
            profile_text += "✨ Сегодня активен\n"
        elif days_inactive == 1:
            profile_text += "✨ Вчера активен\n"
        elif days_inactive < 7:
            profile_text += f"📅 Активен {days_inactive} дней назад\n"
        else:
            profile_text += f"⚠️ Не активен {days_inactive} дней\n"
    
    # Добавляем значки если есть
    badges = user.get('badges', [])
    if badges:
        profile_text += f"\n<b>🏅 ЗНАЧКИ ({len(badges)})</b>\n"
        badges_display = []
        for badge_id in badges[:8]:
            badge = BADGES.get(badge_id, {'emoji': '🏅'})
            badges_display.append(badge['emoji'])
        
        profile_text += " ".join(badges_display)
        
        if len(badges) > 8:
            profile_text += f"\n<i>...и еще {len(badges) - 8} значков</i>"
    
    # Добавляем последние операции админов
    if admin_operations:
        profile_text += f"\n\n<b>📝 ПОСЛЕДНИЕ ОПЕРАЦИИ АДМИНИСТРАТОРОВ</b>\n"
        
        for op in admin_operations[:3]:
            op_type = {
                'add_points': '➕ Даны баллы',
                'remove_points': '➖ Сняты баллы',
                'set_emoji': '🎭 Установлен эмодзи',
                'approve_task': '✅ Одобрено задание',
                'reject_task': '❌ Отклонено задание'
            }.get(op['operation_type'], op['operation_type'])
            
            admin_name = op.get('admin_username', f"ID:{op['admin_id']}")
            date = format_date(op['created_at'])
            
            profile_text += f"\n{op_type}"
            if op.get('points_change'):
                profile_text += f": {op['points_change']}"
            if op.get('note'):
                profile_text += f" - {op['note'][:30]}..."
            profile_text += f"\n👤 {admin_name} | 📅 {date}\n"
    
    # Кнопки для админ-управления
    keyboard = create_quick_actions_keyboard(target_user_id)
    
    if 'query' in locals():
        await query.edit_message_text(
            profile_text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
            disable_web_page_preview=True
        )
    else:
        await update.message.reply_text(
            profile_text,
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
            disable_web_page_preview=True
        )

async def quick_admin_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Быстрое действие администратора"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    admin_id = query.from_user.id
    
    if not is_admin(admin_id):
        await query.answer("⛔ У вас нет прав администратора!", show_alert=True)
        return
    
    # Разбираем callback_data
    if data.startswith("quick_add_"):
        # Добавить баллы
        parts = data.replace("quick_add_", "").split("_")
        user_id = int(parts[0])
        points = int(parts[1])
        
        success = db.update_user_points(user_id, points, admin_id, f"Быстрое добавление {points} баллов")
        
        if success:
            await query.answer(f"✅ Добавлено {points} баллов!", show_alert=True)
            await show_user_profile(update, context, user_id)
        else:
            await query.answer("❌ Ошибка при добавлении баллов!", show_alert=True)
    
    elif data.startswith("quick_remove_"):
        # Забрать баллы
        parts = data.replace("quick_remove_", "").split("_")
        user_id = int(parts[0])
        points = int(parts[1])
        
        # Проверяем, что у пользователя достаточно баллов
        user = db.get_user(user_id)
        if user['total_points'] < points:
            await query.answer(f"❌ Недостаточно баллов! У пользователя: {user['total_points']}", show_alert=True)
            return
        
        success = db.update_user_points(user_id, -points, admin_id, f"Быстрое снятие {points} баллов")
        
        if success:
            await query.answer(f"✅ Снято {points} баллов!", show_alert=True)
            await show_user_profile(update, context, user_id)
        else:
            await query.answer("❌ Ошибка при снятии баллов!", show_alert=True)
    
    elif data.startswith("quick_badge_"):
        # Выдать значок
        parts = data.replace("quick_badge_", "").split("_")
        user_id = int(parts[0])
        badge_id = parts[1]
        
        user = db.get_user(user_id)
        badges = user.get('badges', [])
        
        if badge_id not in badges:
            badges.append(badge_id)
            success = db.update_user_badges(user_id, badges)
            
            if success:
                badge_info = BADGES.get(badge_id, {'emoji': '🏅', 'name': badge_id})
                await query.answer(f"✅ Выдан значок: {badge_info['emoji']} {badge_info['name']}", show_alert=True)
                
                # Записываем операцию
                with db.get_cursor() as cursor:
                    cursor.execute('''
                        INSERT INTO admin_operations 
                        (admin_id, user_id, operation_type, badge_change, note)
                        VALUES (?, ?, ?, ?, ?)
                    ''', (admin_id, user_id, "give_badge", badge_id, f"Выдан значок: {badge_info['name']}"))
                
                await show_user_profile(update, context, user_id)
            else:
                await query.answer("❌ Ошибка при выдаче значка!", show_alert=True)
        else:
            await query.answer("❌ У пользователя уже есть этот значок!", show_alert=True)
    
    elif data.startswith("quick_emoji_"):
        # Установить эмодзи
        user_id = int(data.replace("quick_emoji_", ""))
        
        # Сохраняем user_id в контексте
        context.user_data['emoji_user_id'] = user_id
        
        await query.edit_message_text(
            """
🎭 <b>УСТАНОВКА ЭМОДЗИ</b>
══════════════════════════════

✨ Выберите эмодзи для пользователя:

💡 <b>Как это работает:</b>
• Эмодзи отображается перед никнеймом в рейтингах
• Можно выбрать любой эмодзи из списка
• Для удаления эмодзи нажмите "Без эмодзи"

🎨 <b>Выберите эмодзи:</b>
            """,
            parse_mode=ParseMode.HTML,
            reply_markup=create_emojis_keyboard()
        )
    
    elif data.startswith("quick_ban_"):
        # Блокировка пользователя
        user_id = int(data.replace("quick_ban_", ""))
        
        user = db.get_user(user_id)
        
        if user.get('is_banned'):
            await query.answer("❌ Пользователь уже заблокирован!", show_alert=True)
            return
        
        # Сохраняем данные для подтверждения
        context.user_data['ban_user_id'] = user_id
        
        await query.edit_message_text(
            f"""
🚫 <b>БЛОКИРОВКА ПОЛЬЗОВАТЕЛЯ</b>
══════════════════════════════

👤 <b>Пользователь:</b> {user['nickname']}
🆔 <b>ID:</b> <code>{user_id}</code>
💰 <b>Баллы:</b> <code>{format_number(user['total_points'])}</code>

⚠️ <b>Внимание!</b> Это действие:
• Заблокирует доступ к функциям бота
• Не удалит историю заданий
• Можно будет разблокировать позже

📝 <b>Укажите причину блокировки:</b>
            """,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 Назад к профилю", callback_data=f"admin_view_user_{user_id}")
            ]])
        )
        
        return ADMIN_BAN_USER

async def process_ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка блокировки пользователя"""
    reason = update.message.text.strip()
    user_id = context.user_data.get('ban_user_id')
    admin_id = update.effective_user.id
    
    if not user_id or not reason:
        await update.message.reply_text("❌ Ошибка: данные не найдены!")
        return ConversationHandler.END
    
    if not is_admin(admin_id):
        await update.message.reply_text("⛔ У вас нет прав администратора!")
        return ConversationHandler.END
    
    # Блокируем пользователя
    with db.get_cursor() as cursor:
        cursor.execute('''
            UPDATE users 
            SET is_banned = 1, ban_reason = ?
            WHERE user_id = ?
        ''', (reason, user_id))
        
        # Записываем операцию
        cursor.execute('''
            INSERT INTO admin_operations 
            (admin_id, user_id, operation_type, note)
            VALUES (?, ?, ?, ?)
        ''', (admin_id, user_id, "ban_user", f"Блокировка: {reason}"))
    
    await update.message.reply_text(
        f"✅ <b>Пользователь заблокирован!</b>\n\nПричина: {reason}",
        parse_mode=ParseMode.HTML
    )
    
    # Очищаем контекст
    context.user_data.pop('ban_user_id', None)
    
    # Возвращаемся к профилю пользователя
    await show_user_profile(update, context, user_id)
    
    return ConversationHandler.END

async def manage_drawings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Управление розыгрышами"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("⛔ У вас нет прав администратора!")
        return
    
    # Получаем статистику розыгрышей
    active_drawings = db.get_active_drawings()
    finished_drawings = db.get_finished_drawings(limit=5)
    
    text = f"""
🎰 <b>УПРАВЛЕНИЕ РОЗЫГРЫШАМИ</b>
══════════════════════════════

📊 <b>Статистика розыгрышей:</b>
🟢 Активных: <code>{len(active_drawings)}</code>
🔴 Завершенных: <code>{len(finished_drawings)}</code>
👥 Всего участников за все время: <code>{sum(len(d['participants']) for d in finished_drawings)}</code>

📋 <b>Активные розыгрыши:</b>
"""
    
    if active_drawings:
        for drawing in active_drawings[:3]:
            time_left = datetime.fromisoformat(drawing['end_date']) - datetime.now()
            time_left_str = format_timedelta(time_left)
            participants = len(drawing['participants'])
            
            text += f"\n🎁 <b>{drawing['name']}</b>"
            text += f"\n⏰ Осталось: {time_left_str}"
            text += f"\n👥 Участники: {participants}/{drawing['max_participants']}"
            text += f"\n🏆 Приз: {drawing['prize'][:30]}..."
            text += f"\n{'─' * 25}"
    else:
        text += "\n📭 Нет активных розыгрышей"
    
    text += f"\n\n📜 <b>Последние завершенные розыгрыши:</b>"
    
    if finished_drawings:
        for drawing in finished_drawings[:2]:
            winners_count = len(drawing['winners'])
            participants = len(drawing['participants'])
            
            text += f"\n🎁 <b>{drawing['name']}</b>"
            text += f"\n👑 Победителей: {winners_count}"
            text += f"\n👥 Участников: {participants}"
            text += f"\n🏆 Приз: {drawing['prize'][:30]}..."
            text += f"\n{'─' * 25}"
    else:
        text += "\n📭 Нет завершенных розыгрышей"
    
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=create_drawing_management_keyboard(),
        disable_web_page_preview=True
    )

async def create_drawing_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню создания розыгрыша"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        """
🎰 <b>СОЗДАНИЕ РОЗЫГРЫША</b>
══════════════════════════════

📝 Для создания розыгрыша заполните информацию:

🎯 <b>Шаг 1/7: Название розыгрыша</b>

💡 <b>Требования к названию:</b>
• Уникальное и запоминающееся
• Максимум 50 символов
• Без специальных символов

✏️ <b>Отправьте название розыгрыша:</b>

🔄 <b>Примеры:</b>
• Новогодний розыгрыш 2024
• Летняя лотерея
• Розыгрыш VIP-статуса
• Специальный приз от администрации
        """,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Назад", callback_data="admin_back_to_drawings")
        ]])
    )
    
    context.user_data['drawing_creation'] = {}
    return ADMIN_CREATE_DRAWING

async def process_drawing_creation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка создания розыгрыша"""
    user_id = update.effective_user.id
    
    if not is_admin(user_id):
        await update.message.reply_text("⛔ У вас нет прав администратора!")
        return ConversationHandler.END
    
    drawing_data = context.user_data.get('drawing_creation', {})
    
    if 'step' not in drawing_data:
        # Шаг 1: Название
        name = update.message.text.strip()
        
        if len(name) < 3:
            await update.message.reply_text("❌ Название слишком короткое! Минимум 3 символа.")
            return ADMIN_CREATE_DRAWING
        
        if len(name) > 50:
            await update.message.reply_text("❌ Название слишком длинное! Максимум 50 символов.")
            return ADMIN_CREATE_DRAWING
        
        # Проверяем уникальность
        existing = db.get_drawing(drawing_name=name)
        if existing:
            await update.message.reply_text("❌ Розыгрыш с таким названием уже существует!")
            return ADMIN_CREATE_DRAWING
        
        drawing_data['name'] = name
        drawing_data['step'] = 2
        
        await update.message.reply_text(
            f"""
✅ <b>Название сохранено:</b> {name}

🎯 <b>Шаг 2/7: Описание розыгрыша</b>

💡 <b>Что писать в описании:</b>
• Цель розыгрыша
• Условия участия
• Особые правила
• Любую дополнительную информацию

✏️ <b>Отправьте описание розыгрыша:</b>

🔄 <b>Пример:</b>
<i>Специальный новогодний розыгрыш для самых активных участников! 
Участвуйте и выигрывайте уникальные призы. 
Для участия требуется иметь значок "Звезда" и минимум 100 баллов.</i>
            """,
            parse_mode=ParseMode.HTML
        )
        return ADMIN_CREATE_DRAWING
    
    elif drawing_data['step'] == 2:
        # Шаг 2: Описание
        description = update.message.text.strip()
        drawing_data['description'] = description
        drawing_data['step'] = 3
        
        await update.message.reply_text(
            f"""
✅ <b>Описание сохранено!</b>

🎯 <b>Шаг 3/7: Приз розыгрыша</b>

💡 <b>Что может быть призом:</b>
• Игровая валюта
• Уникальные значки
• VIP-статус
• Реальные призы
• Специальные возможности

✏️ <b>Опишите приз подробно:</b>

🔄 <b>Примеры:</b>
• 1.000.000 игровой валюты
• Значок "Золотой чемпион"
• VIP-статус на 30 дней
• Личная консультация от администратора
            """,
            parse_mode=ParseMode.HTML
        )
        return ADMIN_CREATE_DRAWING
    
    elif drawing_data['step'] == 3:
        # Шаг 3: Приз
        prize = update.message.text.strip()
        drawing_data['prize'] = prize
        drawing_data['step'] = 4
        
        await update.message.reply_text(
            f"""
✅ <b>Приз сохранен:</b> {prize}

🎯 <b>Шаг 4/7: Даты проведения</b>

📅 <b>Начало розыгрыша:</b>
Отправьте дату и время в формате <b>ДД.ММ.ГГГГ ЧЧ:ММ</b>

💡 <b>Примеры:</b>
• <code>25.12.2023 12:00</code> - 25 декабря 2023, 12:00
• <code>01.01.2024 00:00</code> - 1 января 2024, 00:00
• <code>сейчас</code> - начать сразу после создания

✏️ <b>Отправьте дату начала:</b>
            """,
            parse_mode=ParseMode.HTML
        )
        return ADMIN_CREATE_DRAWING
    
    elif drawing_data['step'] == 4:
        # Шаг 4: Дата начала
        start_date_str = update.message.text.strip()
        
        if start_date_str.lower() == 'сейчас':
            start_date = datetime.now()
        else:
            try:
                start_date = datetime.strptime(start_date_str, "%d.%m.%Y %H:%M")
            except ValueError:
                await update.message.reply_text(
                    "❌ Неверный формат даты! Используйте: ДД.ММ.ГГГГ ЧЧ:ММ\nНапример: 25.12.2023 12:00"
                )
                return ADMIN_CREATE_DRAWING
        
        drawing_data['start_date'] = start_date.isoformat()
        drawing_data['step'] = 5
        
        await update.message.reply_text(
            f"""
✅ <b>Дата начала сохранена:</b> {format_date(start_date.isoformat())}

🎯 <b>Шаг 5/7: Дата окончания</b>

📅 <b>Окончание розыгрыша:</b>
Отправьте дату и время в формате <b>ДД.ММ.ГГГГ ЧЧ:ММ</b>

💡 <b>Рекомендации:</b>
• Розыгрыш должен длиться минимум 1 день
• Максимальная длительность - 30 дней
• Учитывайте время на проверку участников

✏️ <b>Отправьте дату окончания:</b>
            """,
            parse_mode=ParseMode.HTML
        )
        return ADMIN_CREATE_DRAWING
    
    elif drawing_data['step'] == 5:
        # Шаг 5: Дата окончания
        end_date_str = update.message.text.strip()
        
        try:
            end_date = datetime.strptime(end_date_str, "%d.%m.%Y %H:%M")
        except ValueError:
            await update.message.reply_text(
                "❌ Неверный формат даты! Используйте: ДД.ММ.ГГГГ ЧЧ:ММ\nНапример: 31.12.2023 23:59"
            )
            return ADMIN_CREATE_DRAWING
        
        # Проверяем, что окончание позже начала
        start_date = datetime.fromisoformat(drawing_data['start_date'])
        if end_date <= start_date:
            await update.message.reply_text(
                "❌ Дата окончания должна быть позже даты начала!"
            )
            return ADMIN_CREATE_DRAWING
        
        # Проверяем максимальную длительность
        max_duration = timedelta(days=30)
        if (end_date - start_date) > max_duration:
            await update.message.reply_text(
                "❌ Слишком длительный розыгрыш! Максимальная длительность - 30 дней."
            )
            return ADMIN_CREATE_DRAWING
        
        drawing_data['end_date'] = end_date.isoformat()
        drawing_data['step'] = 6
        
        await update.message.reply_text(
            f"""
✅ <b>Дата окончания сохранена:</b> {format_date(end_date.isoformat())}

🎯 <b>Шаг 6/7: Условия участия</b>

👥 <b>Количество участников:</b>
Введите минимальное и максимальное количество участников в формате:
<b>мин макс</b>

💡 <b>Рекомендации:</b>
• Минимум: 5-10 участников
• Максимум: 50-100 участников
• Пример: <code>5 50</code>

✏️ <b>Отправьте минимальное и максимальное количество участников:</b>
            """,
            parse_mode=ParseMode.HTML
        )
        return ADMIN_CREATE_DRAWING
    
    elif drawing_data['step'] == 6:
        # Шаг 6: Количество участников
        try:
            min_participants, max_participants = map(int, update.message.text.strip().split())
        except ValueError:
            await update.message.reply_text(
                "❌ Неверный формат! Используйте: мин макс\nНапример: 5 50"
            )
            return ADMIN_CREATE_DRAWING
        
        if min_participants < 2:
            await update.message.reply_text("❌ Минимум должен быть не менее 2 участников!")
            return ADMIN_CREATE_DRAWING
        
        if max_participants > 1000:
            await update.message.reply_text("❌ Максимум не может превышать 1000 участников!")
            return ADMIN_CREATE_DRAWING
        
        if min_participants >= max_participants:
            await update.message.reply_text("❌ Максимум должен быть больше минимума!")
            return ADMIN_CREATE_DRAWING
        
        drawing_data['min_participants'] = min_participants
        drawing_data['max_participants'] = max_participants
        drawing_data['step'] = 7
        
        await update.message.reply_text(
            f"""
✅ <b>Количество участников сохранено:</b>
Минимум: {min_participants}, Максимум: {max_participants}

🎯 <b>Шаг 7/7: Дополнительные условия</b>

🎫 <b>Стоимость участия (в баллах):</b>
Введите количество баллов, необходимое для участия.
Или <code>0</code> если участие бесплатное.

💡 <b>Примеры:</b>
• <code>0</code> - бесплатное участие
• <code>100</code> - 100 баллов за участие
• <code>500</code> - 500 баллов за участие

✏️ <b>Отправьте стоимость участия:</b>
            """,
            parse_mode=ParseMode.HTML
        )
        return ADMIN_CREATE_DRAWING
    
    elif drawing_data['step'] == 7:
        # Шаг 7: Стоимость участия
        try:
            entry_cost = int(update.message.text.strip())
        except ValueError:
            await update.message.reply_text("❌ Введите число!")
            return ADMIN_CREATE_DRAWING
        
        if entry_cost < 0:
            await update.message.reply_text("❌ Стоимость не может быть отрицательной!")
            return ADMIN_CREATE_DRAWING
        
        drawing_data['entry_cost'] = entry_cost
        drawing_data['required_badges'] = []
        
        # Завершаем создание
        try:
            # Сохраняем розыгрыш в базу
            drawing_id = db.create_drawing({
                'name': drawing_data['name'],
                'description': drawing_data['description'],
                'prize': drawing_data['prize'],
                'start_date': drawing_data['start_date'],
                'end_date': drawing_data['end_date'],
                'status': 'active' if datetime.fromisoformat(drawing_data['start_date']) <= datetime.now() else 'announced',
                'min_participants': drawing_data['min_participants'],
                'max_participants': drawing_data['max_participants'],
                'entry_cost': drawing_data['entry_cost'],
                'required_badges': drawing_data['required_badges']
            })
            
            # Отправляем подтверждение
            confirmation_text = f"""
🎉 <b>РОЗЫГРЫШ СОЗДАН!</b>
══════════════════════════════

🎰 <b>Название:</b> {drawing_data['name']}
📝 <b>Описание:</b> {drawing_data['description']}
🏆 <b>Приз:</b> {drawing_data['prize']}

📅 <b>Даты проведения:</b>
Начало: {format_date(drawing_data['start_date'])}
Окончание: {format_date(drawing_data['end_date'])}

👥 <b>Участники:</b>
Минимум: {drawing_data['min_participants']}
Максимум: {drawing_data['max_participants']}

🎫 <b>Стоимость участия:</b> {drawing_data['entry_cost']} баллов
🆔 <b>ID розыгрыша:</b> <code>{drawing_id}</code>

✨ <b>Розыгрыш успешно создан и добавлен в систему!</b>
            """
            
            # Уведомляем всех администраторов
            admin_notification = f"""
🎰 <b>НОВЫЙ РОЗЫГРЫШ СОЗДАН!</b>

👤 Создал: {update.effective_user.first_name}
🎁 Розыгрыш: {drawing_data['name']}
🏆 Приз: {drawing_data['prize']}
⏰ Длительность: {format_date(drawing_data['start_date'])} - {format_date(drawing_data['end_date'])}

🚀 <b>Участники могут начать регистрироваться!</b>
            """
            
            await notify_admins(context.bot, admin_notification, exclude_id=user_id)
            
            # Очищаем контекст
            context.user_data.pop('drawing_creation', None)
            
            await update.message.reply_text(
                confirmation_text,
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("🎰 Управление розыгрышами", callback_data="admin_back_to_drawings"),
                    InlineKeyboardButton("📢 Анонсировать", callback_data=f"admin_announce_drawing_{drawing_id}")
                ]])
            )
            
            return ConversationHandler.END
            
        except Exception as e:
            logger.error(f"Ошибка создания розыгрыша: {e}")
            await update.message.reply_text(
                f"❌ <b>Ошибка при создании розыгрыша!</b>\n\n{str(e)}",
                parse_mode=ParseMode.HTML
            )
            return ADMIN_CREATE_DRAWING

# ========== ОБРАБОТЧИКИ CALLBACK-ЗАПРОСОВ ==========
async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик callback-запросов"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    # Навигация
    if data == "back_to_menu":
        await start_command(update, context)
        return
    
    elif data == "back_to_profile":
        await show_profile(update, context)
        return
    
    elif data == "back_to_drawings":
        await show_active_drawings(update, context)
        return
    
    # Пользовательские функции
    elif data == "show_all_badges":
        await show_all_badges(update, context)
    
    elif data == "my_wins":
        await show_my_wins(update, context)
    
    elif data == "active_drawings":
        await show_active_drawings(update, context)
    
    elif data.startswith("drawing_view_"):
        await show_drawing_details(update, context)
    
    elif data.startswith("drawing_participate_"):
        await participate_in_drawing(update, context)
    
    elif data == "past_winners":
        await show_past_winners(update, context)
    
    # Админ-функции
    elif data == "admin_back_to_dashboard":
        await admin_dashboard(update, context)
    
    elif data == "admin_back_to_tasks":
        await check_tasks(update, context)
    
    elif data == "admin_refresh_tasks":
        await check_tasks(update, context)
    
    elif data.startswith("admin_review_task_"):
        await review_task(update, context)
    
    elif data.startswith("admin_approve_task_"):
        await approve_task_callback(update, context)
    
    elif data.startswith("admin_reject_task_"):
        await reject_task_callback(update, context)
    
    elif data == "admin_next_task":
        await check_tasks(update, context)
    
    elif data == "admin_search_again":
        await search_user(update, context)
        return ADMIN_SEARCH_USER
    
    elif data.startswith("admin_view_user_"):
        await show_user_profile(update, context)
    
    elif data.startswith("quick_"):
        await quick_admin_action(update, context)
    
    elif data.startswith("emoji_select_"):
        await set_user_emoji(update, context)
    
    elif data == "emoji_clear":
        await clear_user_emoji(update, context)
    
    elif data == "admin_back_to_manage":
        await admin_dashboard(update, context)
    
    elif data == "admin_back_to_drawings":
        await manage_drawings(update, context)
    
    elif data == "admin_create_drawing":
        await create_drawing_menu(update, context)
        return ADMIN_CREATE_DRAWING
    
    # Остальные callback-обработчики
    else:
        await query.answer("ℹ️ Функция в разработке", show_alert=True)

async def set_user_emoji(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Установка эмодзи пользователю"""
    query = update.callback_query
    await query.answer()
    
    emoji = query.data.replace("emoji_select_", "")
    user_id = context.user_data.get('emoji_user_id')
    admin_id = query.from_user.id
    
    if not user_id:
        await query.answer("❌ Ошибка: пользователь не найден!", show_alert=True)
        return
    
    # Устанавливаем эмодзи
    success = db.update_user_emoji(user_id, emoji, admin_id, f"Установлен эмодзи: {emoji}")
    
    if success:
        await query.answer(f"✅ Эмодзи {emoji} установлен!", show_alert=True)
        await show_user_profile(update, context, user_id)
    else:
        await query.answer("❌ Ошибка при установке эмодзи!", show_alert=True)

async def clear_user_emoji(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Очистка эмодзи пользователя"""
    query = update.callback_query
    await query.answer()
    
    user_id = context.user_data.get('emoji_user_id')
    admin_id = query.from_user.id
    
    if not user_id:
        await query.answer("❌ Ошибка: пользователь не найден!", show_alert=True)
        return
    
    # Очищаем эмодзи
    success = db.update_user_emoji(user_id, "", admin_id, "Эмодзи очищен")
    
    if success:
        await query.answer("✅ Эмодзи очищен!", show_alert=True)
        await show_user_profile(update, context, user_id)
    else:
        await query.answer("❌ Ошибка при очистке эмодзи!", show_alert=True)

async def show_all_badges(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать все значки пользователя"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    
    if not user:
        await query.edit_message_text("❌ Пользователь не найден!")
        return
    
    badges = user.get('badges', [])
    
    if not badges:
        await query.edit_message_text(
            """
🏅 <b>ВАШИ ЗНАЧКИ</b>
══════════════════════════════

📭 У вас пока нет значков.

🎯 <b>Как получить значки?</b>
• Активно участвуйте в заданиях
• Выигрывайте розыгрыши
• Достигайте высоких результатов
• Помогайте другим участникам
• Участвуйте в специальных активностях

✨ <b>Значки - это награда за ваши достижения!</b>
            """,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🔙 В профиль", callback_data="back_to_profile")
            ]])
        )
        return
    
    text = f"""
🏅 <b>ВАШИ ЗНАЧКИ</b>
══════════════════════════════

Всего значков: <code>{len(badges)}</code>

<b>📋 Коллекция:</b>

"""
    
    # Группируем значки по категориям
    special_badges = []
    regular_badges = []
    
    for badge_id in badges:
        badge = BADGES.get(badge_id)
        if badge:
            if badge_id in ['star', 'crown', 'vip', 'moderator']:
                special_badges.append(badge)
            else:
                regular_badges.append(badge)
    
    if special_badges:
        text += "\n<b>🌟 ОСОБЫЕ ЗНАЧКИ:</b>\n"
        for badge in special_badges:
            text += f"\n{badge['emoji']} <b>{badge['name']}</b>"
            text += f"\n   {badge['description']}\n"
    
    if regular_badges:
        if special_badges:
            text += "\n"
        text += "<b>🏅 ОБЫЧНЫЕ ЗНАЧКИ:</b>\n"
        
        # Показываем по 3 в строке
        for i in range(0, len(regular_badges), 3):
            row = regular_badges[i:i+3]
            text += "\n"
            for badge in row:
                text += f"{badge['emoji']} "
            text += "\n"
            for badge in row:
                text += f"<b>{badge['name'][:10]}</b>  "
    
    text += f"\n\n✨ <b>Продолжайте собирать коллекцию!</b>"
    
    keyboard = [[
        InlineKeyboardButton("🔙 В профиль", callback_data="back_to_profile"),
        InlineKeyboardButton("🎰 К розыгрышам", callback_data="active_drawings")
    ]]
    
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard),
        disable_web_page_preview=True
    )

async def show_past_winners(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать победителей прошлых розыгрышей"""
    query = update.callback_query
    await query.answer()
    
    finished_drawings = db.get_finished_drawings(limit=10)
    
    if not finished_drawings:
        await query.edit_message_text(
            """
🏆 <b>ПОБЕДИТЕЛИ РОЗЫГРЫШЕЙ</b>
══════════════════════════════

📭 Пока не было завершенных розыгрышей.

🎰 <b>Будьте первым победителем!</b>
Участвуйте в активных розыгрышах и выигрывайте призы!
            """,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("🎰 Активные розыгрыши", callback_data="active_drawings"),
                InlineKeyboardButton("🔙 Назад", callback_data="back_to_drawings")
            ]])
        )
        return
    
    text = """
🏆 <b>ПОБЕДИТЕЛИ РОЗЫГРЫШЕЙ</b>
══════════════════════════════

"""
    
    for drawing in finished_drawings[:5]:  # Показываем последние 5 розыгрышей
        name = drawing['name']
        prize = drawing['prize']
        end_date = format_date(drawing['end_date'])
        winners = drawing['winners']
        participants = len(drawing['participants'])
        
        text += f"\n🎁 <b>{name}</b>"
        text += f"\n🏆 Приз: {prize}"
        text += f"\n📅 Дата: {end_date}"
        text += f"\n👥 Участников: {participants}"
        
        if winners:
            text += "\n👑 Победители:\n"
            for place, user_id in winners.items():
                user = db.get_user(user_id)
                if user:
                    display_name = user.get('nickname', f"ID:{user_id}")
                    place_emoji = {
                        '1': '🥇',
                        '2': '🥈',
                        '3': '🥉'
                    }.get(str(place), '🎖️')
                    text += f"   {place_emoji} {display_name}\n"
        else:
            text += "\n👑 Победители: не определены\n"
        
        text += f"{'─' * 30}\n"
    
    if len(finished_drawings) > 5:
        text += f"\n<i>...и еще {len(finished_drawings) - 5} розыгрышей</i>"
    
    keyboard = [
        [InlineKeyboardButton("🎰 Активные розыгрыши", callback_data="active_drawings")],
        [InlineKeyboardButton("🔙 Назад", callback_data="back_to_drawings")]
    ]
    
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard),
        disable_web_page_preview=True
    )

# ========== ЗАПУСК БОТА ==========
def main():
    """Основная функция запуска бота"""
    # Создаем Application
    application = ApplicationBuilder() \
        .token(BOT_TOKEN) \
        .concurrent_updates(True) \
        .pool_timeout(30) \
        .connect_timeout(30) \
        .read_timeout(30) \
        .write_timeout(30) \
        .get_updates_connect_timeout(30) \
        .get_updates_read_timeout(30) \
        .get_updates_write_timeout(30) \
        .get_updates_pool_timeout(30) \
        .build()
    
    # ConversationHandler для отправки заданий
    task_conversation = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^🎮 Отправить задание$"), lambda u, c: start_task_submission(u, c)),
            CommandHandler("task", lambda u, c: start_task_submission(u, c))
        ],
        states={
            TASK_SELECT: [
                CallbackQueryHandler(lambda u, c: select_task_type(u, c), pattern="^task_select_"),
                CallbackQueryHandler(lambda u, c: show_task_help(u, c), pattern="^task_help$"),
                CallbackQueryHandler(lambda u, c: cancel_task_submission(u, c), pattern="^task_cancel$")
            ],
            TASK_COUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: process_task_count(u, c))
            ],
            TASK_SCREENSHOT: [
                MessageHandler(filters.PHOTO, lambda u, c: process_screenshot(u, c)),
                MessageHandler(filters.Document.IMAGE, lambda u, c: process_screenshot(u, c)),
                MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: skip_screenshot(u, c))
            ],
            TASK_DETAILS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: process_task_details(u, c))
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel_command),
            MessageHandler(filters.Regex("^❌ Отмена$"), cancel_command)
        ],
        name="task_conversation",
        persistent=False
    )
    
    # ConversationHandler для админ-функций
    admin_conversation = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^📋 Проверить задания$"), check_tasks),
            MessageHandler(filters.Regex("^👥 Управление$"), admin_dashboard),
            MessageHandler(filters.Regex("^🎰 Управление розыгрышами$"), manage_drawings),
            MessageHandler(filters.Regex("^🔍 Поиск участника$"), search_user)
        ],
        states={
            ADMIN_REVIEW_TASK: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_task_rejection)
            ],
            ADMIN_SEARCH_USER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_user_search)
            ],
            ADMIN_CREATE_DRAWING: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_drawing_creation)
            ],
            ADMIN_BAN_USER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_ban_user)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel_command),
            MessageHandler(filters.Regex("^🔙 В меню пользователя$"), start_command),
            CallbackQueryHandler(lambda u, c: admin_dashboard(u, c), pattern="^admin_back_to_dashboard$")
        ],
        name="admin_conversation",
        persistent=False
    )
    
    # ConversationHandler для управления никнеймом
    nickname_conversation = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^✏️ Мой никнейм$"), start_nickname_change),
            CommandHandler("nickname", start_nickname_change)
        ],
        states={
            NICKNAME_SET: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, process_nickname_change)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel_command),
            MessageHandler(filters.Regex("^❌ Отмена$"), cancel_command)
        ],
        name="nickname_conversation",
        persistent=False
    )
    
    # Обработчики команд
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("profile", show_profile))
    application.add_handler(CommandHandler("top", show_top_users))
    application.add_handler(CommandHandler("tasks", show_my_tasks))
    application.add_handler(CommandHandler("drawings", show_active_drawings))
    application.add_handler(CommandHandler("admin", admin_dashboard))
    
    # Обработчики сообщений
    application.add_handler(MessageHandler(filters.Regex("^📊 Мой профиль$"), show_profile))
    application.add_handler(MessageHandler(filters.Regex("^🏆 ТОП-10$"), show_top_users))
    application.add_handler(MessageHandler(filters.Regex("^📋 Мои задания$"), show_my_tasks))
    application.add_handler(MessageHandler(filters.Regex("^🏅 Мои значки$"), show_all_badges))
    application.add_handler(MessageHandler(filters.Regex("^🎰 Активные розыгрыши$"), show_active_drawings))
    application.add_handler(MessageHandler(filters.Regex("^✏️ Мой никнейм$"), start_nickname_change))
    application.add_handler(MessageHandler(filters.Regex("^🏆 Мои победы$"), show_my_wins))
    application.add_handler(MessageHandler(filters.Regex("^❓ Помощь$"), help_command))
    application.add_handler(MessageHandler(filters.Regex("^📢 Новости$"), show_news))
    
    # Добавляем ConversationHandler
    application.add_handler(task_conversation)
    application.add_handler(admin_conversation)
    application.add_handler(nickname_conversation)
    
    # Обработчик callback-запросов
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    
    # Обработчик ошибок
    application.add_error_handler(error_handler)
    
    # Запускаем бота
    if WEBHOOK_URL:
        # Webhook режим
        logger.info("Запуск в режиме Webhook...")
        application.run_webhook(
            listen="0.0.0.0",
            port=WEBHOOK_PORT,
            url_path=BOT_TOKEN,
            webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}"
        )
    else:
        # Polling режим
        logger.info("Запуск в режиме Polling...")
        application.run_polling(
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
            timeout=30,
            poll_interval=1.0
        )

# ========== ДОПОЛНИТЕЛЬНЫЕ ФУНКЦИИ ==========
async def start_task_submission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало отправки задания"""
    user_id = update.effective_user.id
    
    # Проверяем, не заблокирован ли пользователь
    user = db.get_user(user_id)
    if user and user.get('is_banned'):
        await update.message.reply_text(
            f"""
🚫 <b>ВЫ ЗАБЛОКИРОВАНЫ!</b>

Причина: {user.get('ban_reason', 'не указана')}

📧 Для разблокировки обратитесь к администратору.
            """,
            parse_mode=ParseMode.HTML
        )
        return ConversationHandler.END
    
    # Проверяем дневной лимит заданий
    today = datetime.now().strftime("%Y-%m-%d")
    last_task_date = user.get('last_task_date')
    
    if last_task_date != today:
        # Сбрасываем счетчик на новый день
        db.save_user({
            'user_id': user_id,
            'daily_tasks_count': 0,
            'last_task_date': today
        })
        user['daily_tasks_count'] = 0
    
    if user.get('daily_tasks_count', 0) >= 10:
        await update.message.reply_text(
            """
📊 <b>ДНЕВНОЙ ЛИМИТ ИСЧЕРПАН</b>

Вы уже отправили 10 заданий сегодня.

🔄 <b>Лимит сбросится:</b> в 00:00 по МСК

🎯 <b>Что можно сделать:</b>
• Проверьте свои отправленные задания
• Посмотрите активные розыгрыши
• Изучите свой профиль и статистику

✨ <b>Завтра вы сможете отправить новые задания!</b>
            """,
            parse_mode=ParseMode.HTML
        )
        return ConversationHandler.END
    
    await update.message.reply_text(
        """
🎮 <b>ОТПРАВКА ЗАДАНИЯ</b>
══════════════════════════════

✨ Выберите тип задания из списка:

💡 <b>Как это работает:</b>
1. Выберите тип задания
2. Укажите количество выполнений
3. Отправьте скриншот (если требуется)
4. Добавьте комментарий (необязательно)
5. Задание будет отправлено на проверку

📊 <b>Лимиты на сегодня:</b>
• Всего заданий: 10 (осталось: {remaining})
• Семейные контракты: {family_contracts}/10

🎯 <b>Выберите тип задания:</b>
        """.format(
            remaining=10 - user.get('daily_tasks_count', 0),
            family_contracts=user.get('daily_family_contracts', 0)
        ),
        parse_mode=ParseMode.HTML,
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
    
    # Сохраняем тип задания в контексте
    context.user_data['task_type'] = task_type
    context.user_data['task_info'] = task_info
    
    # Проверяем лимиты для этого типа задания
    user_id = query.from_user.id
    today = datetime.now().strftime("%Y-%m-%d")
    
    # Для семейных контрактов проверяем дневной лимит
    if task_type == "family_contracts":
        user = db.get_user(user_id)
        family_contracts_today = user.get('daily_family_contracts', 0)
        
        if family_contracts_today >= task_info['max_per_day']:
            await query.edit_message_text(
                f"""
❌ <b>ДНЕВНОЙ ЛИМИТ ДОСТИГНУТ</b>

Вы уже выполнили {family_contracts_today} семейных контрактов сегодня.
Максимум в день: {task_info['max_per_day']}

🔄 <b>Лимит сбросится:</b> в 00:00 по МСК

🎯 <b>Выберите другой тип задания:</b>
                """,
                parse_mode=ParseMode.HTML,
                reply_markup=create_task_types_keyboard()
            )
            return TASK_SELECT
    
    text = f"""
🎮 <b>ВЫБРАНО ЗАДАНИЕ:</b> {task_info['emoji']} {task_info['name']}

📝 <b>Описание:</b> {task_info['description']}
🎯 <b>Баллов за единицу:</b> {task_info['points']}
📊 <b>Максимум за отправку:</b> {task_info.get('max_per_submission', 'безлимит')}
📋 <b>Требования:</b> {task_info['validation_rules']}

💡 <b>Советы по выполнению:</b>
• Делайте четкие скриншоты
• Следуйте требованиям задания
• Указывайте точное количество выполнений
• При необходимости добавляйте комментарий

✏️ <b>Сколько раз вы выполнили это задание?</b>
Введите число от 1 до {task_info.get('max_per_submission', 100)}:
        """
    
    await query.edit_message_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Назад к выбору", callback_data="task_back_to_select")
        ]])
    )
    
    return TASK_COUNT

async def process_task_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка количества выполнений"""
    try:
        count = int(update.message.text.strip())
    except ValueError:
        await update.message.reply_text("❌ Пожалуйста, введите число!")
        return TASK_COUNT
    
    task_info = context.user_data.get('task_info')
    max_per_submission = task_info.get('max_per_submission', 100)
    
    if count < 1:
        await update.message.reply_text("❌ Количество должно быть не менее 1!")
        return TASK_COUNT
    
    if count > max_per_submission:
        await update.message.reply_text(f"❌ Максимальное количество за одну отправку: {max_per_submission}!")
        return TASK_COUNT
    
    # Сохраняем количество в контексте
    context.user_data['task_count'] = count
    
    task_type = context.user_data.get('task_type')
    
    # Проверяем лимиты для семейных контрактов
    if task_type == "family_contracts":
        user_id = update.effective_user.id
        user = db.get_user(user_id)
        family_contracts_today = user.get('daily_family_contracts', 0)
        
        if family_contracts_today + count > task_info['max_per_day']:
            available = task_info['max_per_day'] - family_contracts_today
            await update.message.reply_text(
                f"""
❌ <b>ПРЕВЫШЕН ДНЕВНОЙ ЛИМИТ</b>

Вы уже выполнили {family_contracts_today} семейных контрактов.
Максимум в день: {task_info['max_per_day']}
Доступно еще: {available}

🎯 <b>Введите количество не более {available}:</b>
                """,
                parse_mode=ParseMode.HTML
            )
            return TASK_COUNT
    
    # Проверяем, требуется ли скриншот
    if task_info['requires_screenshot']:
        text = f"""
📸 <b>СКРИНШОТ ЗАДАНИЯ</b>

Задание требует подтверждения скриншотом.

💡 <b>Требования к скриншоту:</b>
• Должен быть четким и читаемым
• Должен подтверждать выполнение задания
• Может содержать несколько изображений
• Формат: JPG, PNG (до 10 МБ)

✏️ <b>Отправьте скриншот выполнения:</b>

🔄 <b>Если нет скриншота:</b>
Нажмите "Пропустить", но учтите, что задание без скриншота может быть отклонено.
        """
        
        keyboard = [[
            InlineKeyboardButton("⏭️ Пропустить скриншот", callback_data="task_skip_screenshot")
        ]]
        
        await update.message.reply_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        return TASK_SCREENSHOT
    else:
        # Если скриншот не требуется, переходим к комментарию
        text = """
💬 <b>КОММЕНТАРИЙ К ЗАДАНИЮ</b>

Вы можете добавить комментарий к заданию (необязательно).

💡 <b>Что можно указать:</b>
• Особенности выполнения
• Номер сервера/локации
• Дополнительную информацию
• Ссылки на дополнительные материалы

✏️ <b>Отправьте комментарий или нажмите "Пропустить":</b>

🔄 <b>Пример комментария:</b>
<i>Выполнено на сервере EU-1, все контракты в семейном кабинете.</i>
        """
        
        keyboard = [[
            InlineKeyboardButton("⏭️ Пропустить комментарий", callback_data="task_skip_comment")
        ]]
        
        await update.message.reply_text(
            text,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        
        context.user_data['task_screenshot_path'] = None
        return TASK_DETAILS

async def process_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка скриншота"""
    # Получаем файл скриншота
    if update.message.photo:
        photo = update.message.photo[-1]  # Берем самое большое изображение
        file_id = photo.file_id
    elif update.message.document:
        if update.message.document.mime_type.startswith('image/'):
            file_id = update.message.document.file_id
        else:
            await update.message.reply_text("❌ Пожалуйста, отправьте изображение!")
            return TASK_SCREENSHOT
    else:
        await update.message.reply_text("❌ Пожалуйста, отправьте изображение!")
        return TASK_SCREENSHOT
    
    # Скачиваем файл
    file = await context.bot.get_file(file_id)
    
    # Сохраняем скриншот
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    user_id = update.effective_user.id
    filename = f"screenshots/{user_id}_{timestamp}.jpg"
    
    try:
        await file.download_to_drive(filename)
        context.user_data['task_screenshot_path'] = filename
    except Exception as e:
        logger.error(f"Ошибка сохранения скриншота: {e}")
        await update.message.reply_text("❌ Ошибка сохранения скриншота!")
        return TASK_SCREENSHOT
    
    # Переходим к комментарию
    text = """
💬 <b>КОММЕНТАРИЙ К ЗАДАНИЮ</b>

✅ Скриншот успешно сохранен!

Теперь вы можете добавить комментарий к заданию (необязательно).

💡 <b>Что можно указать:</b>
• Особенности выполнения
• Номер сервера/локации
• Дополнительную информацию
• Ссылки на дополнительные материалы

✏️ <b>Отправьте комментарий или нажмите "Пропустить":</b>
        """
    
    keyboard = [[
        InlineKeyboardButton("⏭️ Пропустить комментарий", callback_data="task_skip_comment")
    ]]
    
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    return TASK_DETAILS

async def skip_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пропуск скриншота"""
    if update.message.text.strip().lower() != "пропустить":
        await update.message.reply_text("❌ Пожалуйста, отправьте скриншот или напишите 'пропустить'!")
        return TASK_SCREENSHOT
    
    context.user_data['task_screenshot_path'] = None
    
    text = """
💬 <b>КОММЕНТАРИЙ К ЗАДАНИЮ</b>

⚠️ Вы пропустили отправку скриншота.

Учтите, что задание без скриншота может быть отклонено администратором.

Теперь вы можете добавить комментарий к заданию (необязательно).

✏️ <b>Отправьте комментарий или нажмите "Пропустить":</b>
    """
    
    keyboard = [[
        InlineKeyboardButton("⏭️ Пропустить комментарий", callback_data="task_skip_comment")
    ]]
    
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    
    return TASK_DETAILS

async def process_task_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка комментария к заданию"""
    comment = update.message.text.strip()
    
    # Сохраняем комментарий в контексте
    context.user_data['task_comment'] = comment if comment and comment.lower() != "пропустить" else ""
    
    # Завершаем отправку задания
    return await finalize_task_submission(update, context)

async def skip_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Пропуск комментария"""
    query = update.callback_query
    await query.answer()
    
    context.user_data['task_comment'] = ""
    
    # Завершаем отправку задания
    return await finalize_task_submission(update, context)

async def finalize_task_submission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Завершение отправки задания"""
    user_id = update.effective_user.id
    
    # Получаем данные из контекста
    task_type = context.user_data.get('task_type')
    task_info = context.user_data.get('task_info')
    count = context.user_data.get('task_count', 1)
    screenshot_path = context.user_data.get('task_screenshot_path')
    comment = context.user_data.get('task_comment', '')
    
    if not task_type or not task_info:
        if 'query' in locals():
            await query.edit_message_text("❌ Ошибка: данные задания не найдены!")
        else:
            await update.message.reply_text("❌ Ошибка: данные задания не найдены!")
        return ConversationHandler.END
    
    # Проверяем лимиты для семейных контрактов
    if task_type == "family_contracts":
        user = db.get_user(user_id)
        family_contracts_today = user.get('daily_family_contracts', 0) + count
        
        # Обновляем дневной счетчик семейных контрактов
        db.save_user({
            'user_id': user_id,
            'daily_family_contracts': family_contracts_today,
            'last_family_reset': datetime.now().isoformat()
        })
    
    # Создаем задание в базе данных
    task_data = {
        'user_id': user_id,
        'task_type': task_type,
        'points': task_info['points'],
        'count': count,
        'screenshot_path': screenshot_path,
        'comment': comment,
        'status': 'pending'
    }
    
    task_id = db.create_task(task_data)
    
    # Обновляем счетчик дневных заданий
    today = datetime.now().strftime("%Y-%m-%d")
    user = db.get_user(user_id)
    daily_tasks = user.get('daily_tasks_count', 0) + 1
    
    db.save_user({
        'user_id': user_id,
        'daily_tasks_count': daily_tasks,
        'last_task_date': today
    })
    
    # Формируем текст подтверждения
    total_points = task_info['points'] * count
    
    confirmation_text = f"""
✅ <b>ЗАДАНИЕ ОТПРАВЛЕНО НА ПРОВЕРКУ!</b>
══════════════════════════════

🎮 <b>Тип задания:</b> {task_info['emoji']} {task_info['name']}
📊 <b>Количество:</b> {count} выполнений
💰 <b>Баллов:</b> {task_info['points']} × {count} = <code>{format_number(total_points)}</code>
🆔 <b>Номер задания:</b> <code>#{task_id}</code>

⏳ <b>Время проверки:</b> до 24 часов
📝 <b>Статус:</b> отправлено на модерацию

📊 <b>Ваша статистика сегодня:</b>
📋 Отправлено заданий: {daily_tasks}/10
👨‍👩‍👧‍👦 Сем. контрактов: {user.get('daily_family_contracts', 0)}/10

✨ <b>Следите за уведомлениями!</b>
Администратор проверит ваше задание и начислит баллы.
    """
    
    # Уведомляем администраторов
    user_info = db.get_user(user_id)
    nickname = user_info.get('nickname', 'Неизвестно')
    
    admin_notification = f"""
📋 <b>НОВОЕ ЗАДАНИЕ НА ПРОВЕРКУ!</b>

🎮 <b>Тип:</b> {task_info['emoji']} {task_info['name']}
👤 <b>Участник:</b> {nickname}
🆔 <b>ID:</b> <code>{user_id}</code>
💰 <b>Баллов:</b> {task_info['points']} × {count} = {total_points}
📊 <b>Количество:</b> {count}
🆔 <b>ID задания:</b> <code>#{task_id}</code>

💬 <b>Комментарий:</b> {comment[:50] if comment else 'нет'}
📸 <b>Скриншот:</b> {'есть' if screenshot_path else 'нет'}

🚀 <b>Быстро проверить:</b> /check_tasks
    """
    
    await notify_admins(context.bot, admin_notification, exclude_id=user_id)
    
    # Отправляем подтверждение пользователю
    if 'query' in locals():
        await query.edit_message_text(
            confirmation_text,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📋 Мои задания", callback_data="my_tasks"),
                InlineKeyboardButton("🎮 Новое задание", callback_data="new_task")
            ]])
        )
    else:
        await update.message.reply_text(
            confirmation_text,
            parse_mode=ParseMode.HTML,
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📋 Мои задания", callback_data="my_tasks"),
                InlineKeyboardButton("🎮 Новое задание", callback_data="new_task")
            ]])
        )
    
    # Очищаем контекст
    for key in ['task_type', 'task_info', 'task_count', 'task_screenshot_path', 'task_comment']:
        context.user_data.pop(key, None)
    
    return ConversationHandler.END

async def cancel_task_submission(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена отправки задания"""
    query = update.callback_query
    await query.answer()
    
    await query.edit_message_text(
        "❌ Отправка задания отменена.",
        reply_markup=create_user_keyboard()
    )
    
    # Очищаем контекст
    for key in ['task_type', 'task_info', 'task_count', 'task_screenshot_path', 'task_comment']:
        context.user_data.pop(key, None)
    
    return ConversationHandler.END

async def show_task_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать справку по заданиям"""
    query = update.callback_query
    await query.answer()
    
    help_text = """
📚 <b>ПОМОЩЬ ПО ОТПРАВКЕ ЗАДАНИЙ</b>
══════════════════════════════

🎯 <b>КАК ПРАВИЛЬНО ОТПРАВЛЯТЬ ЗАДАНИЯ:</b>

1. <b>Выберите тип задания</b>
   • Изучите требования к каждому типу
   • Проверьте необходимые скриншоты

2. <b>Укажите количество выполнений</b>
   • Только фактическое количество
   • Не превышайте максимальный лимит
   • Для семейных контрактов есть дневной лимит

3. <b>Подготовьте скриншоты</b>
   • Делайте четкие и читаемые скриншоты
   • На скриншоте должно быть видно выполнение
   • Можно отправлять несколько скриншотов

4. <b>Добавьте комментарий (необязательно)</b>
   • Укажите особенности выполнения
   • Добавьте пояснения если нужно

⚠️ <b>ЧАСТЫЕ ОШИБКИ:</b>
• Нечеткие скриншоты
• Несоответствие требованиям задания
• Превышение лимитов
• Дублирование заданий

✅ <b>СОВЕТЫ ДЛЯ УСПЕШНОЙ ПРОВЕРКИ:</b>
• Внимательно читайте требования
• Делайте качественные скриншоты
• Следуйте правилам
• Будьте активны и честны

🚀 <b>Удачи в выполнении заданий!</b>
    """
    
    await query.edit_message_text(
        help_text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🔙 Назад к выбору задания", callback_data="task_back_to_select")
        ]])
    )

async def show_top_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать топ-10 пользователей"""
    top_users = db.get_top_users(limit=10)
    
    if not top_users:
        await update.message.reply_text("📊 Рейтинг пока пуст. Будьте первым!")
        return
    
    text = """
🏆 <b>ТОП-10 УЧАСТНИКОВ</b>
══════════════════════════════

"""
    
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    
    for i, user in enumerate(top_users):
        if i < len(medals):
            medal = medals[i]
        else:
            medal = f"{i+1}."
        
        display_name = f"{user.get('custom_emoji', '')} {user['nickname']}".strip()
        points = user.get('points', 0)
        drawings_won = user.get('drawings_won', 0)
        tasks_completed = user.get('tasks_completed', 0)
        
        text += f"\n{medal} <b>{display_name}</b>"
        text += f"\n   💰 Баллы: <code>{format_number(points)}</code>"
        text += f"\n   ✅ Заданий: {tasks_completed}"
        text += f"\n   🏆 Побед: {drawings_won}"
        text += "\n   " + "─" * 25
    
    text += f"""
    
📊 <b>Всего участников в системе:</b> {len(db.get_top_users(limit=1000))}
🕐 <b>Обновлено:</b> {datetime.now().strftime('%d.%m.%Y %H:%M')}

🚀 <b>Поднимайтесь в рейтинге!</b>
Выполняйте задания, участвуйте в розыгрышах и получайте значки.
    """
    
    keyboard = []
    
    # Добавляем кнопку "Моя позиция" если пользователь не в топ-10
    user_id = update.effective_user.id
    user_position = None
    
    all_users = db.get_top_users(limit=1000)
    for i, user in enumerate(all_users, 1):
        if user['user_id'] == user_id:
            user_position = i
            break
    
    if user_position and user_position > 10:
        keyboard.append([
            InlineKeyboardButton(f"📊 Моя позиция: #{user_position}", callback_data="my_position")
        ])
    
    keyboard.append([
        InlineKeyboardButton("📈 Полная статистика", callback_data="full_stats"),
        InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu")
    ])
    
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard),
        disable_web_page_preview=True
    )

async def show_my_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать задания пользователя"""
    user_id = update.effective_user.id
    
    tasks = db.get_user_tasks(user_id, limit=20)
    
    if not tasks:
        await update.message.reply_text(
            """
📋 <b>МОИ ЗАДАНИЯ</b>
══════════════════════════════

📭 Вы еще не отправляли заданий.

🎯 <b>Начните прямо сейчас!</b>
Выполняйте задания, получайте баллы и поднимайтесь в рейтинге.

🚀 <b>Как начать:</b>
1. Нажмите "🎮 Отправить задание"
2. Выберите тип задания
3. Отправьте скриншот выполнения
4. Получите баллы после проверки

✨ <b>Удачи в выполнении заданий!</b>
            """,
            parse_mode=ParseMode.HTML
        )
        return
    
    # Группируем задания по статусу
    pending_tasks = []
    approved_tasks = []
    rejected_tasks = []
    
    for task in tasks:
        if task['status'] == 'pending':
            pending_tasks.append(task)
        elif task['status'] == 'approved':
            approved_tasks.append(task)
        elif task['status'] == 'rejected':
            rejected_tasks.append(task)
    
    text = f"""
📋 <b>МОИ ЗАДАНИЯ</b>
══════════════════════════════

📊 <b>Общая статистика:</b>
✅ Одобрено: {len(approved_tasks)}
⏳ На проверке: {len(pending_tasks)}
❌ Отклонено: {len(rejected_tasks)}

"""
    
    # Показываем задания на проверке
    if pending_tasks:
        text += f"\n<b>⏳ ЗАДАНИЯ НА ПРОВЕРКЕ ({len(pending_tasks)}):</b>\n"
        
        for task in pending_tasks[:3]:  # Показываем 3 последних
            task_type = TASK_TYPES.get(task['task_type'], {'name': task['task_type'], 'emoji': '📝'})
            created_at = format_date(task['created_at'])
            
            text += f"\n{task_type['emoji']} <b>{task_type['name']}</b>"
            text += f"\n🎯 Баллов: {task['points']} × {task.get('count', 1)} = {task['points'] * task.get('count', 1)}"
            text += f"\n📅 Отправлено: {created_at}"
            
            if task.get('comment'):
                text += f"\n💬 {task['comment'][:30]}..."
            
            text += f"\n🆔 ID: #{task['task_id']}"
            text += "\n" + "─" * 25 + "\n"
        
        if len(pending_tasks) > 3:
            text += f"\n<i>...и еще {len(pending_tasks) - 3} заданий на проверке</i>\n"
    
    # Показываем последние одобренные задания
    if approved_tasks:
        text += f"\n<b>✅ ПОСЛЕДНИЕ ОДОБРЕННЫЕ ({len(approved_tasks)}):</b>\n"
        
        for task in approved_tasks[:2]:  # Показываем 2 последних
            task_type = TASK_TYPES.get(task['task_type'], {'name': task['task_type'], 'emoji': '📝'})
            reviewed_at = format_date(task.get('reviewed_at', task['created_at']))
            
            text += f"\n{task_type['emoji']} <b>{task_type['name']}</b>"
            text += f"\n💰 Получено: {task['points']} × {task.get('count', 1)} = {task['points'] * task.get('count', 1)} баллов"
            text += f"\n📅 Проверено: {reviewed_at}"
            text += "\n" + "─" * 25 + "\n"
    
    # Кнопки
    keyboard = []
    
    if pending_tasks:
        keyboard.append([
            InlineKeyboardButton("⏳ Все задания на проверке", callback_data="all_pending_tasks")
        ])
    
    keyboard.append([
        InlineKeyboardButton("✅ История заданий", callback_data="task_history"),
        InlineKeyboardButton("📊 Статистика", callback_data="task_stats")
    ])
    
    keyboard.append([
        InlineKeyboardButton("🎮 Новое задание", callback_data="new_task"),
        InlineKeyboardButton("🔙 В меню", callback_data="back_to_menu")
    ])
    
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(keyboard),
        disable_web_page_preview=True
    )

async def start_nickname_change(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало изменения никнейма"""
    user_id = update.effective_user.id
    user = db.get_user(user_id)
    
    current_nickname = user.get('nickname', 'Не установлен')
    
    await update.message.reply_text(
        f"""
✏️ <b>ИЗМЕНЕНИЕ НИКНЕЙМА</b>
══════════════════════════════

📝 <b>Текущий никнейм:</b> {current_nickname}

💡 <b>Требования к никнейму:</b>
• От 3 до 20 символов
• Только буквы, цифры, пробелы, дефисы и подчеркивания
• Без запрещенных слов
• Уникальный (не проверяется автоматически)

🚫 <b>Запрещено:</b>
• Слова: admin, админ, moderator, модератор
• Оскорбительные слова
• Специальные символы (@, #, $ и т.д.)

✏️ <b>Отправьте новый никнейм:</b>

🔄 <b>Примеры хороших никнеймов:</b>
• КрутойГеймер
• Игрок_2024
• Супер-Стример
• Просто Вася
        """,
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("❌ Отмена", callback_data="cancel_nickname")
        ]])
    )
    
    return NICKNAME_SET

async def process_nickname_change(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка изменения никнейма"""
    new_nickname = update.message.text.strip()
    user_id = update.effective_user.id
    
    # Валидация никнейма
    is_valid, message = validate_nickname(new_nickname)
    
    if not is_valid:
        await update.message.reply_text(
            f"{message}\n\n✏️ <b>Попробуйте еще раз:</b>",
            parse_mode=ParseMode.HTML
        )
        return NICKNAME_SET
    
    # Проверяем длину
    if len(new_nickname) < 3 or len(new_nickname) > 20:
        await update.message.reply_text(
            "❌ Никнейм должен быть от 3 до 20 символов!\n\n✏️ <b>Попробуйте еще раз:</b>",
            parse_mode=ParseMode.HTML
        )
        return NICKNAME_SET
    
    # Обновляем никнейм в базе данных
    db.save_user({
        'user_id': user_id,
        'nickname': new_nickname
    })
    
    await update.message.reply_text(
        f"""
✅ <b>НИКНЕЙМ УСПЕШНО ИЗМЕНЕН!</b>

✨ <b>Новый никнейм:</b> {new_nickname}

🎭 <b>Он будет отображаться:</b>
• В вашем профиле
• В рейтингах
• В списках участников
• В уведомлениях администраторам

🚀 <b>Продолжайте участвовать в заданиях и розыгрышах!</b>
        """,
        parse_mode=ParseMode.HTML,
        reply_markup=create_user_keyboard()
    )
    
    return ConversationHandler.END

async def show_news(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать новости и объявления"""
    # Здесь можно получать новости из базы данных или файла
    # Пока используем статический текст
    
    text = """
📢 <b>НОВОСТИ И ОБЪЯВЛЕНИЯ</b>
══════════════════════════════

🎉 <b>СИСТЕМА РОЗЫГРЫШЕЙ ЗАПУЩЕНА!</b>

✨ <b>Что нового:</b>
• 🎰 Система розыгрышей призов
• 🏆 Новые значки и достижения
• 📊 Улучшенная статистика
• 👑 Административная панель

🚀 <b>Новые возможности:</b>
1. <b>Участие в розыгрышах</b> - выигрывайте уникальные призы!
2. <b>Коллекция значков</b> - собирайте достижения
3. <b>Расширенная статистика</b> - отслеживайте свой прогресс
4. <b>Быстрые действия админов</b> - улучшенная модерация

🎯 <b>Ближайшие мероприятия:</b>
• 🎄 Новогодний розыгрыш (25-31 декабря)
• 🏆 Турнир чемпионов (январь 2024)
• 💝 Валентиновский ивент (февраль 2024)

📋 <b>Обновления системы:</b>
• Исправлены ошибки при отправке заданий
• Улучшена производительность
• Добавлены новые типы заданий
• Улучшена система уведомлений

📧 <b>Поддержка:</b>
По всем вопросам обращайтесь к администраторам.

✨ <b>Удачи в выполнении заданий и розыгрышах!</b>
    """
    
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=create_user_keyboard(),
        disable_web_page_preview=True
    )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик ошибок"""
    logger.error(f"Exception while handling an update: {context.error}", exc_info=context.error)
    
    try:
        # Пытаемся уведомить пользователя об ошибке
        if update and update.effective_chat:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="❌ Произошла ошибка при обработке вашего запроса. Пожалуйста, попробуйте позже."
            )
    except:
        pass
    
    # Уведомляем администраторов об ошибке
    error_message = f"""
⚠️ <b>ОШИБКА В БОТЕ</b>

📝 <b>Детали:</b>
<code>{str(context.error)[:1000]}</code>

🔄 <b>Обновление:</b>
<code>{update.to_dict() if update else 'Нет данных'}</code>
    """
    
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(
                chat_id=admin_id,
                text=error_message,
                parse_mode=ParseMode.HTML
            )
        except:
            pass

# ========== ФУНКЦИИ ДЛЯ ПЛАНИРОВАНИЯ ЗАДАЧ ==========
async def daily_reset(context: CallbackContext):
    """Ежедневный сброс счетчиков"""
    logger.info("Выполнение ежедневного сброса...")
    
    try:
        # Сбрасываем дневные счетчики у всех пользователей
        with db.get_cursor() as cursor:
            cursor.execute('''
                UPDATE users 
                SET daily_tasks_count = 0,
                    daily_family_contracts = 0,
                    last_family_reset = datetime('now')
                WHERE last_task_date != DATE('now') OR last_task_date IS NULL
            ''')
            
            logger.info(f"Сброшены счетчики для {cursor.rowcount} пользователей")
        
        # Проверяем завершение розыгрышей
        with db.get_cursor() as cursor:
            cursor.execute('''
                SELECT drawing_id, name, participants, min_participants, winners
                FROM drawings 
                WHERE status = 'active' 
                AND datetime('now') > end_date
            ''')
            
            expired_drawings = cursor.fetchall()
            
            for drawing in expired_drawings:
                drawing_id, name, participants_json, min_participants, winners_json = drawing
                participants = json.loads(participants_json) if participants_json else []
                winners = json.loads(winners_json) if winners_json else {}
                
                if len(participants) >= min_participants and not winners:
                    # Нужно провести розыгрыш
                    await conduct_drawing(context.bot, drawing_id)
        
    except Exception as e:
        logger.error(f"Ошибка при ежедневном сбросе: {e}")

async def conduct_drawing(bot, drawing_id: int):
    """Провести розыгрыш"""
    try:
        drawing = db.get_drawing(drawing_id=drawing_id)
        if not drawing or drawing['status'] != 'active':
            return
        
        participants = drawing['participants']
        min_participants = drawing['min_participants']
        
        if len(participants) < min_participants:
            # Недостаточно участников - отмена розыгрыша
            with db.get_cursor() as cursor:
                cursor.execute('''
                    UPDATE drawings 
                    SET status = 'cancelled'
                    WHERE drawing_id = ?
                ''', (drawing_id,))
            
            # Уведомляем участников
            for user_id in participants:
                await send_notification(bot, user_id, 
                    f"❌ Розыгрыш '{drawing['name']}' отменен из-за недостаточного количества участников.")
            
            return
        
        # Проводим розыгрыш
        num_winners = min(5, len(participants) // 10 + 1)  # От 1 до 5 победителей
        winners_list = random.sample(participants, num_winners)
        
        winners = {}
        for i, user_id in enumerate(winners_list, 1):
            winners[i] = user_id
        
        # Сохраняем победителей
        db.finish_drawing(drawing_id, winners)
        
        # Уведомляем победителей
        for place, user_id in winners.items():
            place_emoji = {
                1: '🥇',
                2: '🥈',
                3: '🥉'
            }.get(place, '🎖️')
            
            await send_notification(bot, user_id,
                f"""
{place_emoji} <b>ПОЗДРАВЛЯЕМ! ВЫ ВЫИГРАЛИ В РОЗЫГРЫШЕ!</b>

🎰 Розыгрыш: <b>{drawing['name']}</b>
🏆 Место: {place}
🎁 Приз: {drawing['prize']}

✨ <b>Ваш приз будет отправлен в ближайшее время!</b>

🎉 <b>Поздравляем с победой!</b>
                """)
        
        # Уведомляем всех участников
        notification_text = f"""
🎉 <b>РОЗЫГРЫШ ЗАВЕРШЕН!</b>

🎰 Розыгрыш: <b>{drawing['name']}</b>
👥 Участников: {len(participants)}
👑 Победителей: {len(winners)}

🏆 <b>Победители:</b>
"""
        
        for place, user_id in winners.items():
            user = db.get_user(user_id)
            nickname = user.get('nickname', f"ID:{user_id}")
            place_emoji = {
                1: '🥇',
                2: '🥈',
                3: '🥉'
            }.get(place, '🎖️')
            
            notification_text += f"\n{place_emoji} {nickname}"
        
        notification_text += f"\n\n🎁 <b>Приз:</b> {drawing['prize']}"
        notification_text += "\n\n🚀 <b>Участвуйте в следующих розыгрышах!</b>"
        
        # Отправляем уведомление всем участникам
        for user_id in participants:
            if user_id not in winners_list:  # Не отправляем победителям повторно
                await send_notification(bot, user_id, notification_text)
        
        # Уведомляем администраторов
        admin_notification = f"""
🎰 <b>РОЗЫГРЫШ АВТОМАТИЧЕСКИ ЗАВЕРШЕН</b>

🎁 Розыгрыш: {drawing['name']}
👥 Участников: {len(participants)}
👑 Победителей: {len(winners)}
⏰ Завершен автоматически по расписанию

✅ <b>Победители определены и уведомлены.</b>
        """
        
        await notify_admins(bot, admin_notification)
        
    except Exception as e:
        logger.error(f"Ошибка при проведении розыгрыша {drawing_id}: {e}")

# ========== ЗАПУСК ПРИЛОЖЕНИЯ ==========
if __name__ == "__main__":
    # Инициализация базы данных
    db.init_db()
    
    # Проверка переменных окружения
    if not BOT_TOKEN:
        logger.error("❌ BOT_TOKEN не установлен!")
        exit(1)
    
    if not ADMIN_IDS:
        logger.warning("⚠️ ADMIN_IDS не установлены!")
    
    logger.info("🚀 Запуск Telegram Task Bot PRO v5.0...")
    logger.info(f"🤖 Токен бота: {BOT_TOKEN[:10]}...")
    logger.info(f"👑 Администраторы: {ADMIN_IDS}")
    
    # Запускаем бота
    try:
        main()
    except KeyboardInterrupt:
        logger.info("👋 Бот остановлен пользователем")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}")
        raise
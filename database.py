"""
Модуль работы с базой данных SQLite
"""
import sqlite3
import json
from datetime import datetime
from contextlib import contextmanager
import logging
from config import DB_PATH

logger = logging.getLogger(__name__)

class Database:
    """Класс для работы с базой данных"""
    
    def __init__(self):
        self.db_path = DB_PATH
        self.init_db()
    
    @contextmanager
    def get_connection(self):
        """Контекстный менеджер для подключения к БД"""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()
    
    def init_db(self):
        """Инициализация базы данных"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
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
                    daily_regular_tasks INTEGER DEFAULT 0,  -- переименовано
                    daily_tasks_count INTEGER DEFAULT 0,
                    last_task_date TEXT,
                    join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_active TIMESTAMP,
                    is_banned BOOLEAN DEFAULT 0,
                    ban_reason TEXT DEFAULT ''
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
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    reviewed_at TIMESTAMP,
                    reviewed_by INTEGER,
                    rejection_reason TEXT,
                    FOREIGN KEY (user_id) REFERENCES users (user_id)
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
                    participants TEXT DEFAULT '[]',
                    winners TEXT DEFAULT '{}'
                )
            ''')
            
            # Индексы
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_users_points ON users(total_points DESC)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_user ON tasks(user_id)')
            
            logger.info("✅ База данных инициализирована")
    
    # ========== МЕТОДЫ ДЛЯ ПОЛЬЗОВАТЕЛЕЙ ==========
    
    def get_user(self, user_id: int):
        """Получить пользователя по ID"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
            row = cursor.fetchone()
            
            if row:
                user = dict(row)
                user['badges'] = json.loads(user['badges']) if user['badges'] else []
                return user
            return None
    
    def save_user(self, user_data: dict):
        """Сохранить пользователя"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Проверяем, существует ли пользователь
            cursor.execute('SELECT user_id FROM users WHERE user_id = ?', (user_data['user_id'],))
            exists = cursor.fetchone() is not None
            
            if exists:
                # Обновляем
                fields = []
                values = []
                
                for key, value in user_data.items():
                    if key != 'user_id':
                        fields.append(f"{key} = ?")
                        values.append(value)
                
                values.append(user_data['user_id'])
                query = f"UPDATE users SET {', '.join(fields)} WHERE user_id = ?"
                cursor.execute(query, values)
            else:
                # Создаем нового
                keys = user_data.keys()
                placeholders = ', '.join(['?' for _ in keys])
                query = f"INSERT INTO users ({', '.join(keys)}) VALUES ({placeholders})"
                cursor.execute(query, list(user_data.values()))
    
    def update_user_points(self, user_id: int, points_change: int):
        """Обновить баллы пользователя"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE users SET total_points = total_points + ? WHERE user_id = ?',
                (points_change, user_id)
            )
            return cursor.rowcount > 0
    
    def update_daily_counter(self, user_id: int, task_type: str, count: int):
        """Обновить дневной счетчик для типа заданий"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            if task_type == "regular_tasks":
                cursor.execute(
                    'UPDATE users SET daily_regular_tasks = daily_regular_tasks + ? WHERE user_id = ?',
                    (count, user_id)
                )
            else:
                cursor.execute(
                    'UPDATE users SET daily_tasks_count = daily_tasks_count + ? WHERE user_id = ?',
                    (count, user_id)
                )
            
            return cursor.rowcount > 0
    
    def reset_daily_counters(self):
        """Сбросить дневные счетчики"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            today = datetime.now().strftime("%Y-%m-%d")
            
            cursor.execute('''
                UPDATE users 
                SET daily_tasks_count = 0,
                    daily_regular_tasks = 0,
                    last_task_date = ?
                WHERE last_task_date != ? OR last_task_date IS NULL
            ''', (today, today))
            
            return cursor.rowcount
    
    def get_top_users(self, limit: int = 10):
        """Получить топ пользователей"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT user_id, nickname, username, custom_emoji, total_points
                FROM users 
                WHERE is_banned = 0
                ORDER BY total_points DESC
                LIMIT ?
            ''', (limit,))
            
            return [dict(row) for row in cursor.fetchall()]
    
    # ========== МЕТОДЫ ДЛЯ ЗАДАНИЙ ==========
    
    def create_task(self, task_data: dict):
        """Создать задание"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO tasks 
                (user_id, task_type, points, count, screenshot_path, comment, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                task_data['user_id'],
                task_data['task_type'],
                task_data['points'],
                task_data.get('count', 1),
                task_data.get('screenshot_path'),
                task_data.get('comment', ''),
                task_data.get('status', 'pending')
            ))
            
            task_id = cursor.lastrowid
            
            # Обновляем дневной счетчик
            today = datetime.now().strftime("%Y-%m-%d")
            cursor.execute('''
                UPDATE users 
                SET daily_tasks_count = daily_tasks_count + 1,
                    last_task_date = ?
                WHERE user_id = ?
            ''', (today, task_data['user_id']))
            
            return task_id
    
    def get_user_tasks(self, user_id: int, limit: int = 20):
        """Получить задания пользователя"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM tasks 
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
            ''', (user_id, limit))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def get_pending_tasks(self, limit: int = 50):
        """Получить задания на проверке"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT t.*, u.nickname, u.username 
                FROM tasks t 
                LEFT JOIN users u ON t.user_id = u.user_id 
                WHERE t.status = 'pending'
                ORDER BY t.created_at ASC 
                LIMIT ?
            ''', (limit,))
            
            return [dict(row) for row in cursor.fetchall()]
    
    def approve_task(self, task_id: int, admin_id: int):
        """Одобрить задание"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
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
            
            # Начисляем баллы
            cursor.execute('''
                UPDATE users 
                SET total_points = total_points + ?
                WHERE user_id = ?
            ''', (points, user_id))
            
            return True
    
    def reject_task(self, task_id: int, admin_id: int, reason: str):
        """Отклонить задание"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Обновляем задание
            cursor.execute('''
                UPDATE tasks 
                SET status = 'rejected', 
                    reviewed_at = ?, 
                    reviewed_by = ?, 
                    rejection_reason = ?
                WHERE task_id = ?
            ''', (datetime.now(), admin_id, reason, task_id))
            
            return True
    
    # ========== МЕТОДЫ ДЛЯ РОЗЫГРЫШЕЙ ==========
    
    def create_drawing(self, drawing_data: dict):
        """Создать розыгрыш"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO drawings 
                (name, description, prize, start_date, end_date, status, 
                 min_participants, max_participants, entry_cost)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                drawing_data['name'],
                drawing_data.get('description', ''),
                drawing_data['prize'],
                drawing_data['start_date'],
                drawing_data['end_date'],
                drawing_data.get('status', 'announced'),
                drawing_data.get('min_participants', 5),
                drawing_data.get('max_participants', 100),
                drawing_data.get('entry_cost', 0)
            ))
            
            return cursor.lastrowid
    
    def get_active_drawings(self):
        """Получить активные розыгрыши"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM drawings 
                WHERE status = 'active' 
                AND datetime('now') BETWEEN start_date AND end_date
                ORDER BY end_date ASC
            ''')
            
            drawings = []
            for row in cursor.fetchall():
                drawing = dict(row)
                drawing['participants'] = json.loads(drawing['participants']) if drawing['participants'] else []
                drawing['winners'] = json.loads(drawing['winners']) if drawing['winners'] else {}
                drawings.append(drawing)
            
            return drawings

# Создаем глобальный экземпляр БД
db = Database()
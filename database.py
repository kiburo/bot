import psycopg2
from psycopg2 import errors
from psycopg2.extras import RealDictCursor
import json
from datetime import datetime
from typing import Optional, Dict, Any

class Database:
    def __init__(self, database_url: str = None):
        if database_url is None:
            from config import DATABASE_URL
            database_url = DATABASE_URL
        self.database_url = database_url
        self.init_database()
    
    def get_connection(self):
        """Получить подключение к базе данных"""
        return psycopg2.connect(self.database_url)
    
    def init_database(self):
        """Инициализация базы данных"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Таблица пользователей
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username VARCHAR(255),
                first_name VARCHAR(255),
                last_name VARCHAR(255),
                contact_name VARCHAR(255),
                contact_email VARCHAR(255),
                contact_phone VARCHAR(255),
                birth_date VARCHAR(255),
                birth_time VARCHAR(255),
                birth_city VARCHAR(255),
                timezone VARCHAR(255),
                bazi_data TEXT,
                personality_type VARCHAR(255),
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            )
        ''')
        
        # Добавляем новые колонки если их нет (для обновления существующих БД)
        # Используем отдельные транзакции для каждого ALTER TABLE
        try:
            cursor.execute('ALTER TABLE users ADD COLUMN contact_name VARCHAR(255)')
            conn.commit()
        except errors.DuplicateColumn:
            conn.rollback()  # Откатываем транзакцию после ошибки
            pass  # Колонка уже существует
        
        try:
            cursor.execute('ALTER TABLE users ADD COLUMN contact_email VARCHAR(255)')
            conn.commit()
        except errors.DuplicateColumn:
            conn.rollback()  # Откатываем транзакцию после ошибки
            pass  # Колонка уже существует
        
        try:
            cursor.execute('ALTER TABLE users ADD COLUMN contact_phone VARCHAR(255)')
            conn.commit()
        except errors.DuplicateColumn:
            conn.rollback()  # Откатываем транзакцию после ошибки
            pass  # Колонка уже существует
        
        # Таблица сессий
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_sessions (
                user_id BIGINT,
                step VARCHAR(255),
                data TEXT,
                created_at TIMESTAMP DEFAULT NOW(),
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        
        conn.commit()
        cursor.close()
        conn.close()
    
    def save_bazi_data(self, user_id: int, bazi_data: str):
        """Сохранить данные БаЦзы для пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE users 
            SET bazi_data = %s, updated_at = NOW()
            WHERE user_id = %s
        ''', (bazi_data, user_id))
        
        conn.commit()
        cursor.close()
        conn.close()
    
    def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Получить данные пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        
        cursor.execute('SELECT * FROM users WHERE user_id = %s', (user_id,))
        row = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if row:
            return dict(row)
        return None
    
    def save_user(self, user_id: int, **kwargs):
        """Сохранить/обновить данные пользователя"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Проверяем, существует ли пользователь
        cursor.execute('SELECT user_id FROM users WHERE user_id = %s', (user_id,))
        exists = cursor.fetchone()
        
        if exists:
            # Обновляем существующего пользователя
            set_clause = ', '.join([f"{key} = %s" for key in kwargs.keys()])
            set_clause += ', updated_at = NOW()'
            values = list(kwargs.values()) + [user_id]
            
            cursor.execute(f'UPDATE users SET {set_clause} WHERE user_id = %s', values)
        else:
            # Создаем нового пользователя
            columns = ['user_id'] + list(kwargs.keys())
            placeholders = ['%s'] * len(columns)
            values = [user_id] + list(kwargs.values())
            
            cursor.execute(f'''
                INSERT INTO users ({', '.join(columns)})
                VALUES ({', '.join(placeholders)})
            ''', values)
        
        conn.commit()
        cursor.close()
        conn.close()
    
    def save_session(self, user_id: int, step: str, data: Dict[str, Any]):
        """Сохранить данные сессии"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Удаляем старые записи сессии для этого пользователя
        cursor.execute('DELETE FROM user_sessions WHERE user_id = %s', (user_id,))
        
        # Сохраняем новую запись
        cursor.execute('''
            INSERT INTO user_sessions (user_id, step, data)
            VALUES (%s, %s, %s)
        ''', (user_id, step, json.dumps(data)))
        
        conn.commit()
        cursor.close()
        conn.close()
    
    def get_session(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Получить данные сессии"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT step, data FROM user_sessions WHERE user_id = %s', (user_id,))
        row = cursor.fetchone()
        
        cursor.close()
        conn.close()
        
        if row:
            return {
                'step': row[0],
                'data': json.loads(row[1])
            }
        return None
    
    def clear_session(self, user_id: int):
        """Очистить данные сессии"""
        conn = self.get_connection()
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM user_sessions WHERE user_id = %s', (user_id,))
        
        conn.commit()
        cursor.close()
        conn.close()

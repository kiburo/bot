import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Optional, Dict, Any
from config import DATABASE_URL

class Database:
    def __init__(self, database_url: str = None):
        self.database_url = database_url or DATABASE_URL
        if not self.database_url:
            raise ValueError("DATABASE_URL не указан. Установите переменную окружения DATABASE_URL")
        self.init_database()
    
    def _get_connection(self):
        """Получить подключение к базе данных"""
        try:
            return psycopg2.connect(self.database_url)
        except psycopg2.Error as e:
            raise ConnectionError(f"Ошибка подключения к базе данных: {e}")
    
    def init_database(self):
        """Инициализация базы данных"""
        conn = None
        cursor = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Таблица пользователей - только необходимые поля
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    username VARCHAR(255),
                    first_name VARCHAR(255),
                    last_name VARCHAR(255),
                    birth_date VARCHAR(255),
                    contact_name VARCHAR(255),
                    contact_email VARCHAR(255),
                    contact_phone VARCHAR(255),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Получить данные пользователя"""
        conn = None
        cursor = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            cursor.execute('SELECT * FROM users WHERE user_id = %s', (user_id,))
            row = cursor.fetchone()
            
            if row:
                return dict(row)
            return None
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    
    def save_user(self, user_id: int, **kwargs):
        """Сохранить/обновить данные пользователя"""
        conn = None
        cursor = None
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            
            # Проверяем, существует ли пользователь
            cursor.execute('SELECT user_id FROM users WHERE user_id = %s', (user_id,))
            exists = cursor.fetchone()
            
            if exists:
                # Обновляем существующего пользователя
                set_clause = ', '.join([f"{key} = %s" for key in kwargs.keys()])
                set_clause += ', updated_at = CURRENT_TIMESTAMP'
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
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
    

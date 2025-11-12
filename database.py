import json
from typing import Any, Dict, Optional

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Json

from config import DATABASE_URL


class Database:
    """Класс для работы с базой данных PostgreSQL."""

    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or DATABASE_URL
        if not self.database_url:
            raise ValueError("DATABASE_URL is not configured.")
        self.init_database()

    def init_database(self) -> None:
        """Инициализация схемы базы данных."""
        with psycopg.connect(self.database_url, autocommit=True) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS users (
                        user_id BIGINT PRIMARY KEY,
                        username TEXT,
                        first_name TEXT,
                        last_name TEXT,
                        contact_name TEXT,
                        contact_email TEXT,
                        contact_phone TEXT,
                        birth_date TEXT,
                        birth_time TEXT,
                        birth_city TEXT,
                        timezone TEXT,
                        bazi_data TEXT,
                        personality_type TEXT,
                        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )

                cursor.execute(
                    "ALTER TABLE users ADD COLUMN IF NOT EXISTS contact_name TEXT"
                )
                cursor.execute(
                    "ALTER TABLE users ADD COLUMN IF NOT EXISTS contact_email TEXT"
                )
                cursor.execute(
                    "ALTER TABLE users ADD COLUMN IF NOT EXISTS contact_phone TEXT"
                )

                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS user_sessions (
                        user_id BIGINT PRIMARY KEY,
                        step TEXT,
                        data JSONB,
                        created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
                    )
                    """
                )

    def save_bazi_data(self, user_id: int, bazi_data: str) -> None:
        """Сохранить данные БаЦзы для пользователя."""
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE users
                    SET bazi_data = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = %s
                    """,
                    (bazi_data, user_id),
                )
            conn.commit()

    def get_user(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Получить данные пользователя."""
        with psycopg.connect(self.database_url, row_factory=dict_row) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT * FROM users WHERE user_id = %s",
                    (user_id,),
                )
                return cursor.fetchone()

    def save_user(self, user_id: int, **kwargs: Any) -> None:
        """Сохранить или обновить данные пользователя."""
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT 1 FROM users WHERE user_id = %s",
                    (user_id,),
                )
                exists = cursor.fetchone()

                if exists:
                    if kwargs:
                        set_clause = ", ".join(f"{key} = %s" for key in kwargs.keys())
                        set_clause += ", updated_at = CURRENT_TIMESTAMP"
                        values = list(kwargs.values()) + [user_id]
                        cursor.execute(
                            f"UPDATE users SET {set_clause} WHERE user_id = %s",
                            values,
                        )
                    else:
                        cursor.execute(
                            """
                            UPDATE users
                            SET updated_at = CURRENT_TIMESTAMP
                            WHERE user_id = %s
                            """,
                            (user_id,),
                        )
                else:
                    columns = ["user_id"] + list(kwargs.keys())
                    placeholders = ", ".join(["%s"] * len(columns))
                    values = [user_id] + list(kwargs.values())
                    cursor.execute(
                        f"INSERT INTO users ({', '.join(columns)}) VALUES ({placeholders})",
                        values,
                    )
            conn.commit()

    def save_session(self, user_id: int, step: str, data: Dict[str, Any]) -> None:
        """Сохранить данные сессии пользователя."""
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO user_sessions (user_id, step, data, created_at)
                    VALUES (%s, %s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (user_id) DO UPDATE
                    SET step = EXCLUDED.step,
                        data = EXCLUDED.data,
                        created_at = CURRENT_TIMESTAMP
                    """,
                    (user_id, step, Json(data)),
                )
            conn.commit()

    def get_session(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Получить сохранённую сессию пользователя."""
        with psycopg.connect(self.database_url, row_factory=dict_row) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT step, data FROM user_sessions WHERE user_id = %s",
                    (user_id,),
                )
                row = cursor.fetchone()

        if not row:
            return None

        stored_data = row.get("data")
        if isinstance(stored_data, str):
            stored_data = json.loads(stored_data)

        return {"step": row.get("step"), "data": stored_data or {}}

    def clear_session(self, user_id: int) -> None:
        """Удалить данные сессии пользователя."""
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM user_sessions WHERE user_id = %s",
                    (user_id,),
                )
            conn.commit()

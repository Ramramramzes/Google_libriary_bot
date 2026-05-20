import json
import os
import sqlite3
from contextlib import contextmanager

DB_PATH = os.getenv('DB_PATH', 'data/bot.db')


def init_db():
    os.makedirs(os.path.dirname(DB_PATH) or '.', exist_ok=True)
    with get_connection() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                chat_id INTEGER NOT NULL,
                ui_message_id INTEGER,
                subscribed INTEGER NOT NULL DEFAULT 0,
                ignore_flag INTEGER NOT NULL DEFAULT 0,
                last_button_click REAL NOT NULL DEFAULT 0,
                result_message_ids TEXT NOT NULL DEFAULT '[]'
            )
        ''')


@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def get_user(user_id):
    with get_connection() as conn:
        row = conn.execute(
            'SELECT * FROM users WHERE user_id = ?', (user_id,)
        ).fetchone()
        return dict(row) if row else None


def upsert_user(user_id, chat_id, **fields):
    user = get_user(user_id)
    if user is None:
        with get_connection() as conn:
            conn.execute(
                'INSERT INTO users (user_id, chat_id) VALUES (?, ?)',
                (user_id, chat_id),
            )
    updates = {'chat_id': chat_id, **fields}
    set_clause = ', '.join(f'{k} = ?' for k in updates)
    values = list(updates.values()) + [user_id]
    with get_connection() as conn:
        conn.execute(
            f'UPDATE users SET {set_clause} WHERE user_id = ?',
            values,
        )


def set_ui_message_id(user_id, chat_id, message_id):
    upsert_user(user_id, chat_id, ui_message_id=message_id)


def clear_ui_message_id(user_id, chat_id):
    upsert_user(user_id, chat_id, ui_message_id=None)


def set_subscribed(user_id, chat_id, subscribed):
    upsert_user(user_id, chat_id, subscribed=1 if subscribed else 0)


def set_ignore_flag(user_id, chat_id, ignore_flag):
    upsert_user(user_id, chat_id, ignore_flag=1 if ignore_flag else 0)


def set_last_button_click(user_id, chat_id, timestamp):
    upsert_user(user_id, chat_id, last_button_click=timestamp)


def get_result_message_ids(user_id):
    user = get_user(user_id)
    if not user:
        return []
    return json.loads(user.get('result_message_ids') or '[]')


def set_result_message_ids(user_id, chat_id, message_ids):
    upsert_user(
        user_id,
        chat_id,
        result_message_ids=json.dumps(message_ids),
    )


def clear_result_messages(user_id, chat_id):
    set_result_message_ids(user_id, chat_id, [])


def reset_session(user_id, chat_id):
    """Сброс после очистки истории чата — старые message_id недействительны."""
    upsert_user(
        user_id,
        chat_id,
        ui_message_id=None,
        ignore_flag=0,
        result_message_ids='[]',
    )

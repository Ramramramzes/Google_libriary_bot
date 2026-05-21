import json
import os
import sqlite3
import time
from contextlib import contextmanager
from datetime import date

DB_PATH = os.getenv('DB_PATH', 'data/bot.db')
DAILY_FREE_LIMIT = int(os.getenv('DAILY_FREE_LIMIT', '5'))
PREMIUM_DAYS = int(os.getenv('PREMIUM_DAYS', '30'))


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
                result_message_ids TEXT NOT NULL DEFAULT '[]',
                extra_message_ids TEXT NOT NULL DEFAULT '[]',
                last_search_results TEXT NOT NULL DEFAULT '[]',
                last_search_query TEXT NOT NULL DEFAULT '',
                downloaded_indices TEXT NOT NULL DEFAULT '[]',
                premium_until REAL NOT NULL DEFAULT 0,
                daily_books_count INTEGER NOT NULL DEFAULT 0,
                daily_reset_date TEXT NOT NULL DEFAULT ''
            )
        ''')
        for ddl in (
            'ALTER TABLE users ADD COLUMN premium_until REAL NOT NULL DEFAULT 0',
            'ALTER TABLE users ADD COLUMN daily_books_count INTEGER NOT NULL DEFAULT 0',
            'ALTER TABLE users ADD COLUMN daily_reset_date TEXT NOT NULL DEFAULT \'\'',
            'ALTER TABLE users ADD COLUMN extra_message_ids TEXT NOT NULL DEFAULT \'[]\'',
            'ALTER TABLE users ADD COLUMN last_search_results TEXT NOT NULL DEFAULT \'[]\'',
            'ALTER TABLE users ADD COLUMN downloaded_indices TEXT NOT NULL DEFAULT \'[]\'',
            'ALTER TABLE users ADD COLUMN last_search_query TEXT NOT NULL DEFAULT \'\'',
        ):
            try:
                conn.execute(ddl)
            except sqlite3.OperationalError:
                pass
        conn.execute('''
            CREATE TABLE IF NOT EXISTS payments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                stars INTEGER NOT NULL,
                payload TEXT NOT NULL,
                paid_at REAL NOT NULL
            )
        ''')
        conn.execute('''
            CREATE TABLE IF NOT EXISTS bot_meta (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
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


def get_extra_message_ids(user_id):
    user = get_user(user_id)
    if not user:
        return []
    return json.loads(user.get('extra_message_ids') or '[]')


def add_extra_message_id(user_id, chat_id, message_id):
    ids = get_extra_message_ids(user_id)
    if message_id not in ids:
        ids.append(message_id)
    upsert_user(user_id, chat_id, extra_message_ids=json.dumps(ids))


def clear_extra_messages(user_id, chat_id):
    upsert_user(user_id, chat_id, extra_message_ids='[]')


def reset_session(user_id, chat_id):
    upsert_user(
        user_id,
        chat_id,
        ui_message_id=None,
        ignore_flag=0,
        result_message_ids='[]',
        extra_message_ids='[]',
        last_search_results='[]',
        last_search_query='',
    )


def _today():
    return date.today().isoformat()


def _ensure_daily_reset(user_id, chat_id):
    user = get_user(user_id)
    if not user:
        upsert_user(user_id, chat_id)
        user = get_user(user_id)
    if user.get('daily_reset_date') != _today():
        upsert_user(
            user_id,
            chat_id,
            daily_books_count=0,
            daily_reset_date=_today(),
            downloaded_indices='[]',
        )


def has_premium(user_id):
    user = get_user(user_id)
    if not user:
        return False
    return float(user.get('premium_until') or 0) > time.time()


def get_daily_books_used(user_id, chat_id):
    _ensure_daily_reset(user_id, chat_id)
    user = get_user(user_id)
    return int(user.get('daily_books_count') or 0)


def get_books_remaining(user_id, chat_id):
    _ensure_daily_reset(user_id, chat_id)
    used = get_daily_books_used(user_id, chat_id)
    return max(0, DAILY_FREE_LIMIT - used)


def add_books_used(user_id, chat_id, count):
    if count <= 0:
        return
    _ensure_daily_reset(user_id, chat_id)
    used = get_daily_books_used(user_id, chat_id)
    upsert_user(
        user_id,
        chat_id,
        daily_books_count=used + count,
        daily_reset_date=_today(),
    )


def grant_premium(user_id, chat_id, days=None):
    days = days or PREMIUM_DAYS
    user = get_user(user_id)
    now = time.time()
    current = float(user.get('premium_until') or 0) if user else 0
    base = max(now, current)
    upsert_user(user_id, chat_id, premium_until=base + days * 86400)


def log_payment(user_id, stars, payload):
    with get_connection() as conn:
        conn.execute(
            'INSERT INTO payments (user_id, stars, payload, paid_at) VALUES (?, ?, ?, ?)',
            (user_id, stars, payload, time.time()),
        )


def get_status_text(user_id, chat_id):
    _ensure_daily_reset(user_id, chat_id)
    used = get_daily_books_used(user_id, chat_id)
    remaining = max(0, DAILY_FREE_LIMIT - used)
    if has_premium(user_id):
        user = get_user(user_id)
        until = float(user.get('premium_until') or 0)
        from datetime import datetime
        dt = datetime.fromtimestamp(until).strftime('%d.%m.%Y')
        return (
            f'⭐ Premium активен до {dt}\n'
            f'📥 Сегодня скачано: {used}/{DAILY_FREE_LIMIT} '
            f'(осталось {remaining})'
        )
    return f'🔒 Premium не активен\n📥 Лимит после оплаты: {DAILY_FREE_LIMIT} скачиваний/день'


def set_last_search_results(user_id, chat_id, results, query=''):
    upsert_user(
        user_id,
        chat_id,
        last_search_results=json.dumps(results),
        last_search_query=query or '',
    )


def get_last_search_query(user_id):
    user = get_user(user_id)
    if not user:
        return ''
    return user.get('last_search_query') or ''


def get_downloaded_file_ids(user_id):
    """ID файлов Google Drive, уже скачанных сегодня (между поисками)."""
    user = get_user(user_id)
    if not user:
        return set()
    raw = json.loads(user.get('downloaded_indices') or '[]')
    return {str(x) for x in raw}


def mark_downloaded_file(user_id, chat_id, file_id):
    file_ids = get_downloaded_file_ids(user_id)
    file_ids.add(str(file_id))
    upsert_user(
        user_id,
        chat_id,
        downloaded_indices=json.dumps(sorted(file_ids)),
    )


def is_downloaded_file(user_id, file_id):
    return str(file_id) in get_downloaded_file_ids(user_id)


def get_last_search_results(user_id):
    user = get_user(user_id)
    if not user:
        return []
    return json.loads(user.get('last_search_results') or '[]')


def clear_last_search_results(user_id, chat_id):
    upsert_user(
        user_id,
        chat_id,
        last_search_results='[]',
        last_search_query='',
    )


def get_meta(key, default=None):
    with get_connection() as conn:
        row = conn.execute(
            'SELECT value FROM bot_meta WHERE key = ?', (key,)
        ).fetchone()
        return row['value'] if row else default


def set_meta(key, value):
    with get_connection() as conn:
        conn.execute(
            'INSERT INTO bot_meta (key, value) VALUES (?, ?) '
            'ON CONFLICT(key) DO UPDATE SET value = excluded.value',
            (key, str(value)),
        )


def get_maintenance_notify_targets(notify_all=False):
    """Пользователи для уведомления о сбросе чата после деплоя."""
    with get_connection() as conn:
        if notify_all:
            rows = conn.execute(
                'SELECT user_id, chat_id FROM users WHERE chat_id IS NOT NULL'
            ).fetchall()
        else:
            now = time.time()
            rows = conn.execute(
                '''
                SELECT user_id, chat_id FROM users
                WHERE chat_id IS NOT NULL
                AND (
                    ui_message_id IS NOT NULL
                    OR result_message_ids != '[]'
                    OR extra_message_ids != '[]'
                    OR premium_until > ?
                    OR last_button_click > ?
                )
                ''',
                (now, now - 30 * 86400),
            ).fetchall()
        return [dict(row) for row in rows]

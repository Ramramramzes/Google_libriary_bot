import logging
import os

import telebot

import db

DEFAULT_NOTICE_TEXT = (
    '⚠️ Техническое обновление бота.\n\n'
    'Для корректной работы удалите текущий чат с ботом и начните заново: /start'
)


def _is_truthy(value):
    return str(value).strip().lower() in {'1', 'true', 'yes', 'on'}


def _build_notice_text(custom_text=None):
    text = (custom_text or '').strip()
    if text:
        return text
    env_text = os.getenv('MAINTENANCE_MESSAGE', '').strip()
    if env_text:
        return env_text
    return DEFAULT_NOTICE_TEXT


def _is_blocked_error(exc):
    err = str(exc).lower()
    return (
        'bot was blocked by the user' in err
        or 'user is deactivated' in err
        or 'chat not found' in err
    )


def broadcast_reset_notice(bot, notify_all=True, custom_text=None):
    text = _build_notice_text(custom_text=custom_text)
    targets = db.get_maintenance_notify_targets(notify_all=notify_all)
    sent = 0
    failed = 0
    skipped = 0

    for target in targets:
        chat_id = target.get('chat_id')
        if not chat_id:
            continue
        try:
            bot.send_message(chat_id, text)
            sent += 1
        except telebot.apihelper.ApiTelegramException as exc:
            if _is_blocked_error(exc):
                skipped += 1
            else:
                failed += 1
                logging.warning(
                    'maintenance notify failed chat=%s user=%s: %s',
                    chat_id,
                    target.get('user_id'),
                    exc,
                )
        except Exception as exc:
            failed += 1
            logging.warning(
                'maintenance notify unexpected chat=%s user=%s: %s',
                chat_id,
                target.get('user_id'),
                exc,
            )

    return sent, failed, skipped


def run_startup_notify(bot):
    revision = os.getenv('MAINTENANCE_REVISION', '').strip()
    if not revision:
        return

    key = 'maintenance_revision_sent'
    last_sent = (db.get_meta(key, '') or '').strip()
    if last_sent == revision:
        return

    notify_all = _is_truthy(os.getenv('MAINTENANCE_NOTIFY_ALL', '1'))
    sent, failed, skipped = broadcast_reset_notice(
        bot,
        notify_all=notify_all,
    )
    db.set_meta(key, revision)
    logging.warning(
        'Maintenance notify revision=%s sent=%s failed=%s skipped=%s notify_all=%s',
        revision,
        sent,
        failed,
        skipped,
        notify_all,
    )

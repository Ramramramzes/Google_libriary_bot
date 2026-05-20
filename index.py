import html
import json
import telebot
import os
import time
import logging
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
import db
import payments

load_dotenv()
myToken = os.getenv('myToken')
channel_id = os.getenv('channel_id')
CHANNEL_USERNAME = os.getenv('CHANNEL_USERNAME', 'omfsrus').strip().lstrip('@')
PREMIUM_STARS = payments.PREMIUM_STARS
DAILY_FREE_LIMIT = db.DAILY_FREE_LIMIT
ADMIN_USER_IDS = {
    int(x.strip())
    for x in os.getenv('ADMIN_USER_IDS', '').split(',')
    if x.strip().isdigit()
}
bot = telebot.TeleBot(myToken)

db.init_db()

try:
    BOT_USERNAME = bot.get_me().username
except Exception:
    BOT_USERNAME = 'your_bot'

credentials_file = 'myKey.json'
creds = None
if os.path.exists(credentials_file):
    creds = service_account.Credentials.from_service_account_file(
        credentials_file, scopes=['https://www.googleapis.com/auth/drive.readonly']
    )

service = build('drive', 'v3', credentials=creds)
folder_id = os.getenv('folder_id')

PROMPT_TEXT = 'Отправьте слово из названия или имени автора 📕'
LOADING_TEXT = '🔎 Ищем книги в библиотеке…'
SUBSCRIBE_TEXT = (
    'Подпишитесь чтобы продолжить 🌐\n'
    f'https://t.me/{CHANNEL_USERNAME or "omfsrus"}'
)
CHANNEL_ADMIN_TEXT = (
    '⚠️ Бот не может проверить подписку на канал.\n\n'
    f'Администратору: добавьте @{BOT_USERNAME} в администраторы '
    f'@{CHANNEL_USERNAME or "omfsrus"}.\n\n'
    'После этого отправьте /start'
)
SUBSCRIBE_MARKUP = telebot.types.InlineKeyboardMarkup()
SUBSCRIBE_MARKUP.add(
    telebot.types.InlineKeyboardButton('Подписался ✅', callback_data='main')
)
EMPTY_MARKUP = telebot.types.InlineKeyboardMarkup()

SEARCH_DONE_HINT = (
    'Поиск завершен ✅\n'
    'Для скачивания нажмите кнопку под нужной книгой.\n'
    'Новый поиск — введите слово из названия или имени автора 📕'
)
MAX_UI_TEXT = 4000
LIMIT_TEXT = (
    f'Лимит скачиваний на сегодня исчерпан 📚 ({DAILY_FREE_LIMIT}/день)\n\n'
    f'Premium активен, новый лимит будет завтра.\n'
    'Для нового поиска введите название книги или автора 📕'
)
PREMIUM_REQUIRED_TEXT = (
    '🔒 Доступ к библиотеке открыт только с Premium.\n\n'
    f'Premium на {payments.PREMIUM_DAYS} дней — {PREMIUM_STARS} ⭐\n'
    f'Включает {DAILY_FREE_LIMIT} скачиваний книг в день.\n\n'
    'Нажмите кнопку ниже или отправьте /premium'
)
DOWNLOAD_PREFIX = 'download:'


def build_premium_markup():
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(
        telebot.types.InlineKeyboardButton(
            f'💳 Оплатить {PREMIUM_STARS} ⭐',
            callback_data='buy_premium',
        )
    )
    return markup


def build_book_message_text(name, link=None):
    safe_name = html.escape(name)
    if link:
        return f'📖 <a href="{link}"><b>{safe_name}</b></a>'
    return f'📖 <b>{safe_name}</b>'


def build_download_markup(index, link=None):
    markup = telebot.types.InlineKeyboardMarkup()
    if link:
        markup.add(
            telebot.types.InlineKeyboardButton('📥 Скачать', url=link),
        )
    else:
        markup.add(
            telebot.types.InlineKeyboardButton(
                '📥 Скачать',
                callback_data=f'{DOWNLOAD_PREFIX}{index}',
            )
        )
    return markup


def refresh_search_footer(user_id, chat_id):
    """Обновляет нижнее сообщение со статусом и лимитами после скачивания."""
    user = db.get_user(user_id)
    if not user or not user.get('ui_message_id'):
        return
    query = db.get_last_search_query(user_id)
    results = db.get_last_search_results(user_id)
    if not query or not results:
        return
    text = build_search_footer_text(query, len(results), user_id, chat_id)
    try:
        bot.edit_message_text(
            text,
            chat_id,
            user['ui_message_id'],
            parse_mode='HTML',
            disable_web_page_preview=True,
        )
    except telebot.apihelper.ApiTelegramException as e:
        if 'message is not modified' not in str(e).lower():
            logging.warning(
                'refresh_search_footer failed user=%s: %s', user_id, e
            )
    except Exception as e:
        logging.exception('refresh_search_footer failed user=%s: %s', user_id, e)


def unlock_book_message(call, item, index):
    """Делает книгу кликабельной: ссылка в названии и URL-кнопка."""
    link = item['link']
    text = build_book_message_text(item['name'], link=link)
    markup = build_download_markup(index, link=link)
    bot.edit_message_text(
        text,
        call.message.chat.id,
        call.message.message_id,
        parse_mode='HTML',
        disable_web_page_preview=True,
        reply_markup=markup,
    )


def is_admin(user_id):
    return user_id in ADMIN_USER_IDS


def is_subscribed(user_id):
    user = db.get_user(user_id)
    return bool(user and user['subscribed'])


def is_ignore_flag(user_id):
    user = db.get_user(user_id)
    return bool(user and user['ignore_flag'])


def delete_user_message(chat_id, message_id):
    if not message_id:
        return
    try:
        bot.delete_message(chat_id, message_id)
    except telebot.apihelper.ApiTelegramException:
        pass


def purge_recent_messages(chat_id, current_message_id, window=25):
    """Best-effort очистка недавних сообщений, если старые ID потерялись."""
    start_id = max(1, current_message_id - window)
    for message_id in range(start_id, current_message_id + 1):
        delete_user_message(chat_id, message_id)


def purge_extra_messages(user_id, chat_id, keep_message_id=None, keep_extra_ids=None):
    """Удаляет все вспомогательные сообщения бота (счета, старые результаты)."""
    user = db.get_user(user_id)
    ui_id = user['ui_message_id'] if user else None
    if keep_message_id is None:
        keep_message_id = ui_id
    keep_extra_ids = set(keep_extra_ids or [])

    for msg_id in db.get_result_message_ids(user_id):
        if msg_id != keep_message_id:
            delete_user_message(chat_id, msg_id)
    db.clear_result_messages(user_id, chat_id)

    kept_extras = []
    for msg_id in db.get_extra_message_ids(user_id):
        if msg_id in keep_extra_ids:
            kept_extras.append(msg_id)
            continue
        if msg_id != keep_message_id:
            delete_user_message(chat_id, msg_id)
    db.upsert_user(
        user_id,
        chat_id,
        extra_message_ids=json.dumps(kept_extras),
    )


def purge_all_bot_messages(user_id, chat_id):
    """Удаляет все сообщения бота в чате (полная очистка)."""
    user = db.get_user(user_id)
    if user and user.get('ui_message_id'):
        delete_user_message(chat_id, user['ui_message_id'])
    purge_extra_messages(user_id, chat_id)
    db.clear_ui_message_id(user_id, chat_id)


def track_extra_message(user_id, chat_id, message):
    if message and getattr(message, 'message_id', None):
        db.add_extra_message_id(user_id, chat_id, message.message_id)


def update_ui_message(
    chat_id,
    user_id,
    text,
    reply_markup=None,
    parse_mode=None,
    disable_web_page_preview=None,
    force_new=False,
    keep_extra_ids=None,
):
    """Одно рабочее сообщение: перед обновлением удаляет все лишние."""
    user = db.get_user(user_id)
    old_ui_id = user['ui_message_id'] if user else None

    if force_new:
        purge_all_bot_messages(user_id, chat_id)
        old_ui_id = None
    else:
        purge_extra_messages(
            user_id,
            chat_id,
            keep_message_id=old_ui_id,
            keep_extra_ids=keep_extra_ids,
        )

    if len(text) > MAX_UI_TEXT:
        text = text[: MAX_UI_TEXT - 20] + '\n…'

    user = db.get_user(user_id)
    message_id = user['ui_message_id'] if user else None
    kwargs = {}
    if reply_markup is not None:
        kwargs['reply_markup'] = reply_markup
    elif message_id:
        kwargs['reply_markup'] = EMPTY_MARKUP
    if parse_mode:
        kwargs['parse_mode'] = parse_mode
    if disable_web_page_preview is not None:
        kwargs['disable_web_page_preview'] = disable_web_page_preview

    if message_id:
        try:
            bot.edit_message_text(text, chat_id, message_id, **kwargs)
            return message_id
        except telebot.apihelper.ApiTelegramException as e:
            err = str(e).lower()
            if 'message is not modified' in err:
                return message_id
            logging.warning(
                'edit_message_text failed user=%s msg=%s: %s',
                user_id, message_id, e,
            )
        except Exception as e:
            logging.exception(
                'edit_message_text unexpected error user=%s: %s', user_id, e
            )
        db.clear_ui_message_id(user_id, chat_id)

    try:
        msg = bot.send_message(chat_id, text, **kwargs)
        db.set_ui_message_id(user_id, chat_id, msg.message_id)
        return msg.message_id
    except Exception as e:
        logging.exception('send_message failed user=%s: %s', user_id, e)
        return None


def format_search_summary(book_name, results_count):
    lines = [
        f'Похожие на «{html.escape(book_name)}»: {results_count}',
        '',
        'Каждая книга отправлена отдельным сообщением выше.',
        SEARCH_DONE_HINT,
    ]
    return '\n'.join(lines)


def build_search_footer_text(book_name, results_count, user_id, chat_id):
    results_text = format_search_summary(book_name, results_count)
    if is_subscribed(user_id):
        status = db.get_status_text(user_id, chat_id)
        return f'Вы подписаны ✅\n{status}\n\n{results_text}'
    return results_text


def show_premium_required(chat_id, user_id, force_new=False):
    return update_ui_message(
        chat_id,
        user_id,
        PREMIUM_REQUIRED_TEXT,
        reply_markup=build_premium_markup(),
        force_new=force_new,
    )


def send_premium_invoice_tracked(chat_id, user_id):
    """Только счёт Stars — без второго сообщения с подсказкой."""
    purge_extra_messages(user_id, chat_id)
    user = db.get_user(user_id)
    if user and user.get('ui_message_id'):
        delete_user_message(chat_id, user['ui_message_id'])
        db.clear_ui_message_id(user_id, chat_id)
    invoice_msg = payments.send_premium_invoice(bot, chat_id, user_id)
    track_extra_message(user_id, chat_id, invoice_msg)
    return invoice_msg


def show_prompt(chat_id, user_id, force_new=False):
    db.set_ignore_flag(user_id, chat_id, False)
    lines = []
    if is_subscribed(user_id):
        lines.append('Вы подписаны ✅')
        lines.append(db.get_status_text(user_id, chat_id))
        lines.append('')
        if db.has_premium(user_id):
            lines.append(PROMPT_TEXT)
            markup = None
        else:
            lines.append(PREMIUM_REQUIRED_TEXT)
            markup = build_premium_markup()
        text = '\n'.join(lines)
    else:
        text = SUBSCRIBE_TEXT
        markup = None
    return update_ui_message(
        chat_id, user_id, text, reply_markup=markup, force_new=force_new
    )


def show_limit_reached(chat_id, user_id):
    return update_ui_message(
        chat_id,
        user_id,
        LIMIT_TEXT,
        reply_markup=build_premium_markup(),
        force_new=True,
    )


def show_subscribe(
    chat_id,
    user_id,
    force_new=False,
    ui_message_id=None,
    check_error=None,
):
    db.set_ignore_flag(user_id, chat_id, True)
    if ui_message_id:
        db.set_ui_message_id(user_id, chat_id, ui_message_id)
        force_new = False
    elif db.get_user(user_id) and db.get_user(user_id).get('ui_message_id'):
        force_new = False

    if check_error == 'member_list_inaccessible':
        text = CHANNEL_ADMIN_TEXT
        markup = None
    else:
        text = SUBSCRIBE_TEXT
        markup = SUBSCRIBE_MARKUP

    return update_ui_message(
        chat_id,
        user_id,
        text,
        reply_markup=markup,
        force_new=force_new,
    )


def _channel_chat_ids():
    ids = []
    if CHANNEL_USERNAME:
        ids.append(f'@{CHANNEL_USERNAME}')
    if channel_id:
        try:
            numeric_id = int(channel_id)
            if numeric_id not in ids:
                ids.append(numeric_id)
        except (TypeError, ValueError):
            if channel_id not in ids:
                ids.append(channel_id)
    return ids


def get_chat_member_safe(channel_id, user_id):
    """Проверка подписки без падения бота при ошибках API."""
    chat_ids = _channel_chat_ids()
    if not chat_ids:
        logging.error('channel_id / CHANNEL_USERNAME не заданы в .env')
        return None, 'no_channel'

    last_error = 'api_error'
    for chat_id in chat_ids:
        try:
            return bot.get_chat_member(chat_id, user_id), None
        except telebot.apihelper.ApiTelegramException as e:
            err = str(e).lower()
            logging.error(
                'get_chat_member failed channel=%s user=%s: %s',
                chat_id, user_id, e,
            )
            if 'member list is inaccessible' in err:
                last_error = 'member_list_inaccessible'
            elif 'chat not found' in err:
                last_error = 'chat_not_found'
            else:
                last_error = 'api_error'

    return None, last_error


def is_member_status(status):
    return status in ['member', 'administrator', 'creator']


@bot.message_handler(commands=['premium'])
def cmd_premium(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    db.upsert_user(user_id, chat_id)
    delete_user_message(chat_id, message.message_id)
    if not is_subscribed(user_id):
        if not check_subscription_mess(user_id, channel_id, message, force_new=True):
            return
    if db.has_premium(user_id):
        show_prompt(chat_id, user_id, force_new=True)
        return
    try:
        send_premium_invoice_tracked(chat_id, user_id)
    except Exception as e:
        logging.exception('send_invoice failed: %s', e)
        update_ui_message(
            chat_id,
            user_id,
            'Оплата Stars недоступна. Включите платежи в @BotFather → '
            'Monetization / Payments.',
            force_new=True,
        )


@bot.message_handler(commands=['status'])
def cmd_status(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    db.upsert_user(user_id, chat_id)
    delete_user_message(chat_id, message.message_id)
    text = db.get_status_text(user_id, chat_id)
    if not db.has_premium(user_id):
        text += f'\n\nPremium ({PREMIUM_STARS} ⭐) нужен для доступа к поиску.'
    lines = []
    if is_subscribed(user_id):
        lines.extend(['Вы подписаны ✅', text])
        if db.has_premium(user_id):
            lines.extend(['', PROMPT_TEXT])
    else:
        lines.append(text)
    update_ui_message(
        chat_id,
        user_id,
        '\n'.join(lines),
        reply_markup=build_premium_markup() if not db.has_premium(user_id) else None,
        force_new=True,
    )


@bot.message_handler(commands=['test_premium'])
def cmd_test_premium(message):
    """Тест Premium без оплаты (только ADMIN_USER_IDS в .env)."""
    user_id = message.from_user.id
    chat_id = message.chat.id
    if not is_admin(user_id):
        delete_user_message(chat_id, message.message_id)
        update_ui_message(
            chat_id, user_id, 'Команда только для администратора.', force_new=True
        )
        return
    db.upsert_user(user_id, chat_id)
    db.grant_premium(user_id, chat_id)
    purge_recent_messages(chat_id, message.message_id)
    purge_all_bot_messages(user_id, chat_id)
    db.reset_session(user_id, chat_id)
    show_prompt(chat_id, user_id, force_new=True)


@bot.pre_checkout_query_handler(func=lambda q: True)
def pre_checkout(query):
    payments.handle_pre_checkout(bot, query)


@bot.message_handler(content_types=['successful_payment'])
def successful_payment(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    db.upsert_user(user_id, chat_id)
    delete_user_message(chat_id, message.message_id)
    if payments.handle_successful_payment(message):
        purge_all_bot_messages(user_id, chat_id)
        show_prompt(chat_id, user_id, force_new=True)


@bot.callback_query_handler(func=lambda call: call.data == 'buy_premium')
def buy_premium_callback(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    db.upsert_user(user_id, chat_id)

    # Как у «Подписался ✅»: если подписка уже сохранена в БД — не гоняем API
    # (иначе при сбое API снова экран подписки → цикл с кнопкой «Подписался»).
    if not is_subscribed(user_id):
        if not check_subscription_call_checker(user_id, channel_id, chat_id):
            check_subscription_call(user_id, channel_id, call)
            return

    if db.has_premium(user_id):
        bot.answer_callback_query(call.id, 'Premium уже активен ✅')
        show_prompt(chat_id, user_id)
        return

    try:
        send_premium_invoice_tracked(chat_id, user_id)
        bot.answer_callback_query(call.id)
    except Exception as e:
        logging.exception('send_invoice failed: %s', e)
        bot.answer_callback_query(
            call.id,
            'Ошибка счёта. Проверьте Stars в @BotFather',
            show_alert=True,
        )


@bot.callback_query_handler(func=lambda call: call.data.startswith(DOWNLOAD_PREFIX))
def download_book_callback(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    db.upsert_user(user_id, chat_id)

    if not check_subscription_call_checker(user_id, channel_id, chat_id):
        check_subscription_call(user_id, channel_id, call)
        return

    if not db.has_premium(user_id):
        bot.answer_callback_query(
            call.id,
            'Для скачивания нужен Premium',
            show_alert=True,
        )
        show_premium_required(chat_id, user_id)
        return

    try:
        index = int(call.data.replace(DOWNLOAD_PREFIX, '', 1))
    except ValueError:
        bot.answer_callback_query(call.id, 'Книга не найдена', show_alert=True)
        return

    results = db.get_last_search_results(user_id)
    if index < 0 or index >= len(results):
        bot.answer_callback_query(
            call.id,
            'Результаты устарели. Выполните поиск заново.',
            show_alert=True,
        )
        return

    item = results[index]

    file_id = item['id']

    if db.is_downloaded_file(user_id, file_id):
        try:
            unlock_book_message(call, item, index)
        except Exception as e:
            logging.warning('unlock_book_message repeat failed: %s', e)
        bot.answer_callback_query(call.id, text='✅ Откройте по названию или кнопке')
        return

    remaining = db.get_books_remaining(user_id, chat_id)
    if remaining <= 0:
        bot.answer_callback_query(
            call.id,
            'Лимит скачиваний на сегодня исчерпан',
            show_alert=True,
        )
        show_limit_reached(chat_id, user_id)
        return

    db.add_books_used(user_id, chat_id, 1)
    db.mark_downloaded_file(user_id, chat_id, file_id)
    try:
        unlock_book_message(call, item, index)
    except Exception as e:
        logging.exception('unlock_book_message failed: %s', e)
        bot.answer_callback_query(
            call.id,
            'Не удалось открыть ссылку. Попробуйте ещё раз.',
            show_alert=True,
        )
        return

    refresh_search_footer(user_id, chat_id)
    bot.answer_callback_query(call.id, text='✅ Откройте по названию или кнопке')


@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    db.upsert_user(user_id, chat_id)
    purge_all_bot_messages(user_id, chat_id)
    db.reset_session(user_id, chat_id)

    subscribed = check_subscription_mess(
        user_id, channel_id, message, force_new=True
    )
    if subscribed:
        show_prompt(chat_id, user_id, force_new=True)
    delete_user_message(chat_id, message.message_id)


@bot.message_handler(
    content_types=[
        'text', 'audio', 'document', 'photo', 'sticker', 'video',
        'video_note', 'voice', 'location', 'contact', 'new_chat_members',
        'left_chat_member', 'new_chat_title', 'new_chat_photo',
        'delete_chat_photo', 'group_chat_created', 'supergroup_chat_created',
        'channel_chat_created', 'migrate_to_chat_id', 'migrate_from_chat_id',
        'pinned_message', 'web_app_data',
    ]
)
def send_book(message):
    if message.text and message.text.startswith('/'):
        return

    user_id = message.from_user.id
    chat_id = message.chat.id
    db.upsert_user(user_id, chat_id)

    if message.content_type != 'text':
        delete_user_message(chat_id, message.message_id)
        return

    purge_extra_messages(user_id, chat_id)
    db.set_ignore_flag(user_id, chat_id, False)

    if not check_subscription_call_checker(user_id, channel_id, chat_id):
        check_subscription_mess(user_id, channel_id, message, force_new=True)
        delete_user_message(chat_id, message.message_id)
        return

    if not db.has_premium(user_id):
        show_premium_required(chat_id, user_id, force_new=True)
        delete_user_message(chat_id, message.message_id)
        return

    book_name = message.text.strip()
    user_msg_id = message.message_id

    if len(book_name) <= 2:
        if update_ui_message(
            chat_id,
            user_id,
            f'Слишком короткий запрос 🤏\n\n{PROMPT_TEXT}',
        ):
            delete_user_message(chat_id, user_msg_id)
        db.set_ignore_flag(user_id, chat_id, False)
        return

    bot.send_chat_action(chat_id, action='typing')
    ui_id = update_ui_message(chat_id, user_id, LOADING_TEXT)
    if ui_id:
        delete_user_message(chat_id, user_msg_id)

    results = service.files().list(
        q=f"'{folder_id}' in parents",
        fields='files(id, name)',
        pageSize=1000,
    ).execute()
    files = results.get('files', [])

    final_arr = []
    seen_links = set()
    for file in files:
        file_id = file['id']
        file_name = file['name']
        file_link = f'https://docs.google.com/file/d/{file_id}'
        if book_name.lower() in file_name.lower():
            if file_link not in seen_links:
                seen_links.add(file_link)
                final_arr.append({
                    'id': file_id,
                    'name': file_name,
                    'link': file_link,
                })

    if final_arr:
        db.set_last_search_results(user_id, chat_id, final_arr, query=book_name)
        result_message_ids = []
        for index, item in enumerate(final_arr):
            sent = bot.send_message(
                chat_id,
                build_book_message_text(item['name']),
                parse_mode='HTML',
                disable_web_page_preview=True,
                reply_markup=build_download_markup(index),
            )
            result_message_ids.append(sent.message_id)
            time.sleep(0.1)
        db.set_result_message_ids(user_id, chat_id, result_message_ids)

        if ui_id:
            delete_user_message(chat_id, ui_id)
            db.clear_ui_message_id(user_id, chat_id)

        footer_text = build_search_footer_text(
            book_name, len(final_arr), user_id, chat_id
        )
        summary = bot.send_message(
            chat_id,
            footer_text,
            parse_mode='HTML',
            disable_web_page_preview=True,
        )
        db.set_ui_message_id(user_id, chat_id, summary.message_id)
        db.set_ignore_flag(user_id, chat_id, False)
    else:
        db.clear_last_search_results(user_id, chat_id)
        update_ui_message(chat_id, user_id, f'Ничего не найдено ❌\n\n{PROMPT_TEXT}')
        db.set_ignore_flag(user_id, chat_id, False)


@bot.callback_query_handler(func=lambda call: call.data == 'main')
def main_handler(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    db.upsert_user(user_id, chat_id)

    user = db.get_user(user_id)
    last_click = user['last_button_click'] if user else 0

    if (
        last_click
        and time.time() - last_click < 3
        and not is_subscribed(user_id)
    ):
        bot.answer_callback_query(call.id, 'Вы уже нажали кнопку 😡', show_alert=True)
        return

    db.set_last_button_click(user_id, chat_id, time.time())

    if not is_subscribed(user_id):
        bot.answer_callback_query(call.id, 'Проверяем ⌛', show_alert=True)
        purge_extra_messages(
            user_id, chat_id, keep_message_id=call.message.message_id
        )
        check_subscription_call(user_id, channel_id, call)
    else:
        purge_all_bot_messages(user_id, chat_id)
        show_prompt(chat_id, user_id, force_new=True)
        bot.answer_callback_query(call.id)


def _handle_subscription_check(user_id, chat_id):
    """
    Возвращает (True, None) если подписка подтверждена.
    (False, error_code) — показать экран подписки или ошибку настройки.
    """
    chat_member, error = get_chat_member_safe(channel_id, user_id)

    if error in ('chat_not_found', 'no_channel', 'member_list_inaccessible', 'api_error'):
        db.set_subscribed(user_id, chat_id, False)
        return False, error

    if is_member_status(chat_member.status):
        db.set_subscribed(user_id, chat_id, True)
        return True, None

    db.set_subscribed(user_id, chat_id, False)
    return False, 'not_subscribed'


def check_subscription_mess(user_id, channel_id, message, force_new=False):
    chat_id = message.chat.id
    ok, error = _handle_subscription_check(user_id, chat_id)
    if ok:
        return True
    user = db.get_user(user_id)
    use_force_new = force_new and not (user and user.get('ui_message_id'))
    show_subscribe(chat_id, user_id, force_new=use_force_new, check_error=error)
    return False


def check_subscription_call(user_id, channel_id, call):
    chat_id = call.message.chat.id
    ok, error = _handle_subscription_check(user_id, chat_id)
    if ok:
        db.set_ui_message_id(user_id, chat_id, call.message.message_id)
        show_prompt(chat_id, user_id, force_new=False)
        bot.answer_callback_query(call.id, 'Подписка подтверждена ✅')
        return True

    show_subscribe(
        chat_id,
        user_id,
        ui_message_id=call.message.message_id,
        check_error=error,
    )
    if error == 'member_list_inaccessible':
        bot.answer_callback_query(
            call.id,
            'Добавьте бота администратором канала',
            show_alert=True,
        )
    elif error == 'not_subscribed':
        bot.answer_callback_query(
            call.id,
            'Подписка не найдена. Подпишитесь на канал.',
            show_alert=True,
        )
    else:
        bot.answer_callback_query(
            call.id,
            'Не удалось проверить подписку',
            show_alert=True,
        )
    return False


def check_subscription_call_checker(user_id, channel_id, chat_id=None):
    if chat_id is None:
        user = db.get_user(user_id)
        chat_id = user['chat_id'] if user else None
    if chat_id is None:
        return False

    ok, _ = _handle_subscription_check(user_id, chat_id)
    return ok


@bot.callback_query_handler(func=lambda call: call.data == 'short')
def short_book_name(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    purge_all_bot_messages(user_id, chat_id)
    if is_subscribed(user_id):
        show_prompt(chat_id, user_id, force_new=True)
    else:
        check_subscription_call(user_id, channel_id, call)


logging.basicConfig(filename='myapp.log', level=logging.ERROR)
stderr_logger = logging.getLogger('stderr_logger')


class StderrLogHandler(logging.Handler):
    def emit(self, record):
        log_message = self.format(record)
        stderr_logger.error(log_message)


stderr_logger.addHandler(StderrLogHandler())

if __name__ == '__main__':
    while True:
        try:
            bot.polling(none_stop=True)
        except Exception as e:
            print(f'An error occurred: {e}')
            time.sleep(1)

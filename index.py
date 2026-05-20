import telebot
import os
import time
import logging
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
import db

load_dotenv()
myToken = os.getenv('myToken')
channel_id = os.getenv('channel_id')
bot = telebot.TeleBot(myToken)

db.init_db()

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
SUBSCRIBE_TEXT = 'Подпишитесь чтобы продолжить 🌐\nhttps://t.me/omfsrus'
SUBSCRIBE_MARKUP = telebot.types.InlineKeyboardMarkup()
SUBSCRIBE_MARKUP.add(
    telebot.types.InlineKeyboardButton('Подписался ✅', callback_data='main')
)
EMPTY_MARKUP = telebot.types.InlineKeyboardMarkup()

SEARCH_DONE_TEXT = (
    'Поиск завершен ✅\n\n'
    'Для нового поиска введите слово из названия или имени автора 📕'
)


def is_subscribed(user_id):
    user = db.get_user(user_id)
    return bool(user and user['subscribed'])


def is_ignore_flag(user_id):
    user = db.get_user(user_id)
    return bool(user and user['ignore_flag'])


def update_ui_message(
    chat_id,
    user_id,
    text,
    reply_markup=None,
    parse_mode=None,
    disable_web_page_preview=None,
    force_new=False,
):
    """Редактирует одно UI-сообщение или создаёт новое, если старое недоступно."""
    if force_new:
        db.clear_ui_message_id(user_id, chat_id)

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


def delete_user_message(chat_id, message_id):
    try:
        bot.delete_message(chat_id, message_id)
    except telebot.apihelper.ApiTelegramException:
        pass


def delete_result_messages(user_id, chat_id):
    for msg_id in db.get_result_message_ids(user_id):
        delete_user_message(chat_id, msg_id)
    db.clear_result_messages(user_id, chat_id)


def show_prompt(chat_id, user_id, force_new=False):
    db.set_ignore_flag(user_id, chat_id, False)
    text = PROMPT_TEXT
    if is_subscribed(user_id):
        text = f'Вы подписаны ✅\n\n{PROMPT_TEXT}'
    return update_ui_message(chat_id, user_id, text, force_new=force_new)


def show_subscribe(chat_id, user_id, force_new=False):
    db.set_ignore_flag(user_id, chat_id, True)
    return update_ui_message(
        chat_id,
        user_id,
        SUBSCRIBE_TEXT,
        reply_markup=SUBSCRIBE_MARKUP,
        force_new=force_new,
    )


def get_chat_member_safe(channel_id, user_id):
    """Проверка подписки без падения бота при ошибках API."""
    if not channel_id:
        logging.error('channel_id не задан в .env')
        return None, 'no_channel'
    try:
        return bot.get_chat_member(
            chat_id=int(channel_id), user_id=int(user_id)
        ), None
    except telebot.apihelper.ApiTelegramException as e:
        err = str(e).lower()
        logging.error(
            'get_chat_member failed channel=%s user=%s: %s',
            channel_id, user_id, e,
        )
        if 'chat not found' in err:
            return None, 'chat_not_found'
        return None, 'api_error'


def is_member_status(status):
    return status in ['member', 'administrator', 'creator']


@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    db.upsert_user(user_id, chat_id)
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

    if is_ignore_flag(user_id):
        delete_result_messages(user_id, chat_id)
        db.set_ignore_flag(user_id, chat_id, False)
    else:
        delete_result_messages(user_id, chat_id)

    if not check_subscription_call_checker(user_id, channel_id, chat_id):
        check_subscription_mess(user_id, channel_id, message, force_new=True)
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
    name_arr = []
    for file in files:
        file_id = file['id']
        file_name = file['name']
        file_link = f'https://docs.google.com/file/d/{file_id}'
        if book_name.lower() in file_name.lower():
            if file_link not in final_arr:
                final_arr.append(file_link)
                name_arr.append(file_name)

    if final_arr:
        result_ids = []
        for i, link in enumerate(final_arr):
            bot.send_chat_action(chat_id, action='typing')
            time.sleep(0.25)
            sent = bot.send_message(
                chat_id,
                f'Похожие на "{book_name}" книги 📖 : '
                f'<a href="{link}">{name_arr[i]}</a>',
                disable_web_page_preview=True,
                parse_mode='HTML',
            )
            result_ids.append(sent.message_id)
        finish = bot.send_message(chat_id, SEARCH_DONE_TEXT)
        result_ids.append(finish.message_id)
        db.set_result_message_ids(user_id, chat_id, result_ids)
        db.set_ignore_flag(user_id, chat_id, True)
        show_prompt(chat_id, user_id)
    else:
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
        delete_result_messages(user_id, chat_id)
        check_subscription_call(user_id, channel_id, call)
    else:
        delete_result_messages(user_id, chat_id)
        db.clear_ui_message_id(user_id, chat_id)
        show_prompt(chat_id, user_id, force_new=True)
        bot.answer_callback_query(call.id)


def _handle_subscription_check(user_id, chat_id):
    """
    Возвращает True если пользователь подписан (или проверка недоступна).
    False — нужно показать экран подписки.
    """
    chat_member, error = get_chat_member_safe(channel_id, user_id)

    if error == 'chat_not_found':
        # Бот не добавлен в канал — иначе падает весь /start
        db.set_subscribed(user_id, chat_id, True)
        return True

    if error:
        db.set_subscribed(user_id, chat_id, True)
        return True

    if is_member_status(chat_member.status):
        db.set_subscribed(user_id, chat_id, True)
        return True

    db.set_subscribed(user_id, chat_id, False)
    return False


def check_subscription_mess(user_id, channel_id, message, force_new=False):
    chat_id = message.chat.id
    if _handle_subscription_check(user_id, chat_id):
        return True
    show_subscribe(chat_id, user_id, force_new=force_new)
    return False


def check_subscription_call(user_id, channel_id, call):
    chat_id = call.message.chat.id
    if _handle_subscription_check(user_id, chat_id):
        show_prompt(chat_id, user_id, force_new=True)
        bot.answer_callback_query(call.id, 'Подписка подтверждена ✅')
        return True

    show_subscribe(chat_id, user_id, force_new=True)
    bot.answer_callback_query(call.id)
    return False


def check_subscription_call_checker(user_id, channel_id, chat_id=None):
    if chat_id is None:
        user = db.get_user(user_id)
        chat_id = user['chat_id'] if user else None
    if chat_id is None:
        return False

    return _handle_subscription_check(user_id, chat_id)


@bot.callback_query_handler(func=lambda call: call.data == 'short')
def short_book_name(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id

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

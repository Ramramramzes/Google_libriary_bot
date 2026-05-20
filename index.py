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
SUBSCRIBE_TEXT = 'Подпишитесь чтобы продолжить 🌐\nhttps://t.me/omfsrus'
SUBSCRIBE_MARKUP = telebot.types.InlineKeyboardMarkup()
SUBSCRIBE_MARKUP.add(
    telebot.types.InlineKeyboardButton('Подписался ✅', callback_data='main')
)
SEARCH_MARKUP = telebot.types.InlineKeyboardMarkup()
SEARCH_MARKUP.add(
    telebot.types.InlineKeyboardButton('Искать 🔎', callback_data='clear')
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
):
    """Редактирует одно UI-сообщение или создаёт новое, если старое недоступно."""
    user = db.get_user(user_id)
    message_id = user['ui_message_id'] if user else None
    kwargs = {}
    if reply_markup is not None:
        kwargs['reply_markup'] = reply_markup
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
            db.clear_ui_message_id(user_id, chat_id)

    msg = bot.send_message(chat_id, text, **kwargs)
    db.set_ui_message_id(user_id, chat_id, msg.message_id)
    return msg.message_id


def delete_user_message(chat_id, message_id):
    try:
        bot.delete_message(chat_id, message_id)
    except telebot.apihelper.ApiTelegramException:
        pass


def delete_result_messages(user_id, chat_id):
    for msg_id in db.get_result_message_ids(user_id):
        delete_user_message(chat_id, msg_id)
    db.clear_result_messages(user_id, chat_id)


def show_prompt(chat_id, user_id):
    db.set_ignore_flag(user_id, chat_id, False)
    text = PROMPT_TEXT
    if is_subscribed(user_id):
        text = f'Вы подписаны ✅\n\n{PROMPT_TEXT}'
    update_ui_message(chat_id, user_id, text)


def show_subscribe(chat_id, user_id):
    db.set_ignore_flag(user_id, chat_id, True)
    update_ui_message(
        chat_id, user_id, SUBSCRIBE_TEXT, reply_markup=SUBSCRIBE_MARKUP
    )


@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    chat_id = message.chat.id
    db.upsert_user(user_id, chat_id)

    delete_user_message(chat_id, message.message_id)

    if check_subscription_mess(user_id, channel_id, message):
        show_prompt(chat_id, user_id)


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

    bot.send_chat_action(chat_id, action='typing')

    if is_ignore_flag(user_id):
        delete_user_message(chat_id, message.message_id)
        return

    delete_result_messages(user_id, chat_id)

    if not check_subscription_call_checker(user_id, channel_id, chat_id):
        delete_user_message(chat_id, message.message_id)
        check_subscription_mess(user_id, channel_id, message)
        return

    book_name = message.text.strip()
    delete_user_message(chat_id, message.message_id)

    if len(book_name) <= 2:
        update_ui_message(
            chat_id,
            user_id,
            f'Слишком короткий запрос 🤏\n\n{PROMPT_TEXT}',
        )
        db.set_ignore_flag(user_id, chat_id, False)
        return

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
            time.sleep(0.25)
            sent = bot.send_message(
                chat_id,
                f'Похожие на "{book_name}" книги 📖 : '
                f'<a href="{link}">{name_arr[i]}</a>',
                disable_web_page_preview=True,
                parse_mode='HTML',
            )
            result_ids.append(sent.message_id)
        db.set_result_message_ids(user_id, chat_id, result_ids)
        db.set_ignore_flag(user_id, chat_id, True)
        update_ui_message(
            chat_id,
            user_id,
            'Поиск завершен ✅',
            reply_markup=SEARCH_MARKUP,
        )
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
        show_prompt(chat_id, user_id)
        bot.answer_callback_query(call.id)


def check_subscription_mess(user_id, channel_id, message):
    chat_id = message.chat.id
    chat_member = bot.get_chat_member(
        chat_id=int(channel_id), user_id=int(user_id)
    )
    if chat_member.status in ['member', 'administrator', 'creator']:
        db.set_subscribed(user_id, chat_id, True)
        return True

    db.set_subscribed(user_id, chat_id, False)
    show_subscribe(chat_id, user_id)
    return False


def check_subscription_call(user_id, channel_id, call):
    chat_id = call.message.chat.id
    chat_member = bot.get_chat_member(
        chat_id=int(channel_id), user_id=int(user_id)
    )
    if chat_member.status in ['member', 'administrator', 'creator']:
        db.set_subscribed(user_id, chat_id, True)
        show_prompt(chat_id, user_id)
        bot.answer_callback_query(call.id, 'Подписка подтверждена ✅')
        return True

    db.set_subscribed(user_id, chat_id, False)
    show_subscribe(chat_id, user_id)
    bot.answer_callback_query(call.id)
    return False


def check_subscription_call_checker(user_id, channel_id, chat_id=None):
    if chat_id is None:
        user = db.get_user(user_id)
        chat_id = user['chat_id'] if user else None
    if chat_id is None:
        return False

    chat_member = bot.get_chat_member(
        chat_id=int(channel_id), user_id=int(user_id)
    )
    if chat_member.status in ['member', 'administrator', 'creator']:
        db.set_subscribed(user_id, chat_id, True)
        return True

    db.set_subscribed(user_id, chat_id, False)
    return False


@bot.callback_query_handler(func=lambda call: call.data == 'short')
def short_book_name(call):
    user_id = call.from_user.id
    chat_id = call.message.chat.id

    if is_subscribed(user_id):
        show_prompt(chat_id, user_id)
    else:
        check_subscription_call(user_id, channel_id, call)


@bot.callback_query_handler(func=lambda call: call.data == 'clear')
def clear(call):
    bot.answer_callback_query(call.id, 'Чистим 🧹', show_alert=True)
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    delete_result_messages(user_id, chat_id)
    show_prompt(chat_id, user_id)


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

import telebot
import os
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
import time
import logging

load_dotenv()
myToken = os.getenv('myToken')
channel_id = os.getenv('channel_id')
bot = telebot.TeleBot(myToken)


class UserContext:
    def __init__(self):
        self.ignoreFlag = False
        self.descripsion_mode = False
        self.send_book_msg = None
        self.begin_msg = None
        self.book_name = ""
        self.again_msg = None
        self.finish_msg = None
        self.reg = None
        self.sentBooks = []
        self.last_button_click = {}

user_contexts = {}

def get_user_context(user_id):
    if user_id not in user_contexts:
        user_contexts[user_id] = UserContext()
    return user_contexts[user_id]

#  Путь к JSON-файлу с учетными данными клиента
credentials_file = 'myKey.json'

# Создание объекта авторизации
creds = None
if os.path.exists(credentials_file):
  creds = service_account.Credentials.from_service_account_file(
      credentials_file, scopes=['https://www.googleapis.com/auth/drive.readonly']
  )

# Создание объекта API
service = build('drive', 'v3', credentials=creds)

# ID папки, которую вы хотите просмотреть
folder_id = os.getenv('folder_id')
# !----------------------------------------------------------------------------START
@bot.message_handler(commands=['start'])
def start(message):
  user_id = message.from_user.id
  user_context = get_user_context(user_id)
  bot.send_message(message.chat.id,'Библиотека OMFS📚')
  try:
    bot.delete_message(message.chat.id, message.message_id)
  except:
    pass

  check_subscription_mess(user_id,channel_id,message)
  if user_context.descripsion_mode is False:
    try:
      bot.delete_message(message.chat.id, message.message_id)
    except:
      pass
  else:
    user_context.begin_msg = bot.send_message(message.chat.id,'Вы подписаны ✅')
    user_context.send_book_msg = bot.send_message(message.chat.id,'Отправьте слово из названия или имени автора 📕')
    user_context.ignoreFlag = False

# !----------------------------------------------------------------------------MESSAGE
@bot.message_handler(content_types=['text', 'audio', 'document', 'photo', 'sticker', 'video', 'video_note', 'voice', 'location', 'contact', 'new_chat_members', 'left_chat_member', 'new_chat_title', 'new_chat_photo', 'delete_chat_photo', 'group_chat_created', 'supergroup_chat_created', 'channel_chat_created', 'migrate_to_chat_id', 'migrate_from_chat_id', 'pinned_message', 'web_app_data'])
def send_book(message):
  user_id = message.from_user.id
  user_context = get_user_context(user_id)

  # Если это не текстовое сообщение то удаляем его
  if message.content_type != 'text':
    try:
      bot.delete_message(message.chat.id, message.id)
      return
    except:
      pass 

  bot.send_chat_action(message.chat.id, action="typing")
  try:
    bot.delete_message(user_context.begin_msg.chat.id, user_context.begin_msg.message_id)
  except:
    pass
  try:
    if user_context.ignoreFlag is not False:
      bot.delete_message(message.chat.id, message.id)
      return
  except:
    pass
  try:
    bot.delete_message(user_context.again_msg.chat.id, user_context.again_msg.message_id)
  except:
    pass
  try:
    bot.delete_message(user_context.finish_msg.chat.id, user_context.finish_msg.message_id)
  except:
    pass
  if check_subscription_call_checker(user_id, channel_id):
      
    user_context.book_name = message.text.strip()

    try:
      bot.delete_message(user_context.send_book_msg.chat.id, user_context.send_book_msg.message_id)
    except:
      pass

    
    if len(user_context.book_name) <= 2:
      try:
        bot.delete_message(message.chat.id, message.id)
      except:
        pass
      user_context.again_msg = bot.send_message(message.chat.id,'Слишком короткий запрос 🤏')
      user_context.send_book_msg = bot.send_message(message.chat.id,'Отправьте слово из названия или имени автора 📕')
      user_context.ignoreFlag = False
      return
    
    #! Выполнение запроса для списка файлов и папок в данной папке
    results = service.files().list(q=f"'{folder_id}' in parents", fields="files(id, name)",pageSize=1000).execute()
    files = results.get('files', [])

    finalArr = []
    nameArr = []
    for file in files:
      file_id = file['id']
      file_name = file['name']
      file_link = f"https://docs.google.com/file/d/{file_id}"
      # Создание массива с ссылками совпавшими с поиском
      if user_context.book_name.lower() in file_name.lower():
          if file_link not in finalArr:
            finalArr.append(file_link)
            nameArr.append(file_name)
    if len(finalArr) != 0:
      # Создание массива отправленных ссылок для дальнейшего удаления  
      user_context.ignoreFlag = True
      user_context.sentBooks = []
      inc = 0
      for link in finalArr:
        time.sleep(.25)
        user_context.sentBooks.append(bot.send_message(message.chat.id, f'Похожие на "{user_context.book_name}" книги 📖 : <a href="{link}">{nameArr[inc]}</a>',disable_web_page_preview=True,parse_mode='HTML'))
        inc+=1
        user_context.ignoreFlag = True
      # Создание кнопки и сохранения id для дальнейшего удаления
      # Удаляем сообщение пользователя
      bot.delete_message(message.chat.id, message.id)
      markup = telebot.types.InlineKeyboardMarkup()
      item = telebot.types.InlineKeyboardButton("Искать 🔎", callback_data='clear')
      markup.add(item)
      user_context.ignoreFlag = True
      user_context.finish_msg = bot.send_message(message.chat.id, 'Поиск завершен ✅', reply_markup=markup)

    else:
      bot.delete_message(message.chat.id, message.id)
      user_context.finish_msg = bot.send_message(message.chat.id, 'Ничего не найдено ❌')
      user_context.send_book_msg = bot.send_message(message.chat.id,'Отправьте слово из названия или имени автора 📕')
      user_context.ignoreFlag = False
  else:
    bot.delete_message(message.chat.id, message.id)
    check_subscription_mess(user_id, channel_id,message)
# !----------------------------------------------------------------------------CALL_MAIN
@bot.callback_query_handler(func=lambda call: call.data == 'main')
def main(call):
  user_id = call.from_user.id
  user_context = get_user_context(user_id)

  if user_id in user_context.last_button_click and time.time() - user_context.last_button_click[user_id] < 3 and user_context.descripsion_mode is not True:
    bot.answer_callback_query(call.id, 'Вы уже нажали кнопку 😡', show_alert=True)
  else:
    user_context.last_button_click[user_id] = time.time()
    if user_context.descripsion_mode is False:
  # !----------------------------------------------------------------------------ПОДПИСКИ_НЕТ
      bot.answer_callback_query(call.id, 'Проверяем ⌛', show_alert=True)
      try:
        bot.delete_message(user_context.reg.chat.id, user_context.reg.message_id)
      except:
        pass
      try:
        bot.delete_message(user_context.finish_msg.chat.id, user_context.finish_msg.message_id)
      except:
        pass
      check_subscription_call(user_id,channel_id,call)
    else:
  # !---------------------------------------------------------------------------ПОДПИСКА_ЕСТЬ
      try:
        bot.delete_message(user_context.again_msg.chat.id, user_context.again_msg.message_id)
      except:
        pass
      try:
        bot.delete_message(user_context.begin_msg.chat.id, user_context.begin_msg.message_id)
      except:
        pass
      try:
        bot.delete_message(user_context.finish_msg.chat.id, user_context.finish_msg.message_id)
      except:
        pass
      try:
        bot.delete_message(user_context.reg.chat.id, user_context.reg.message_id)
      except:
        pass
      user_context.send_book_msg = bot.send_message(call.message.chat.id,'Отправьте слово из названия или имени автора 📕')
      user_context.ignoreFlag = False

def check_subscription_mess(user_id, channel_id,message):
  user_id = message.from_user.id
  user_context = get_user_context(user_id)

  chat_member = bot.get_chat_member(chat_id=int(channel_id), user_id=int(user_id))
  if chat_member.status in ["member","administrator","creator"]:
    # Пользователь подписан на канал
    user_context.descripsion_mode = True
    return True  
  elif chat_member.status not in ["member"]:
    user_context.descripsion_mode = False
    markup = telebot.types.InlineKeyboardMarkup()
    item = telebot.types.InlineKeyboardButton("Подписался ✅", callback_data='main')
    markup.add(item)
    try:
      bot.delete_message(user_context.send_book_msg.chat.id, user_context.send_book_msg.message_id)
    except:
      pass
    user_context.reg = bot.send_message(message.chat.id,'Подпишитесь чтобы продолжить 🌐\nhttps://t.me/omfsrus',reply_markup=markup)
    user_context.ignoreFlag = True
    # Пользователь не подписан на канал
    return False

def check_subscription_call(user_id, channel_id,call):
  user_context = get_user_context(user_id)

  chat_member = bot.get_chat_member(chat_id=int(channel_id), user_id=int(user_id))
  if chat_member.status in ["member","administrator","creator"]:
    # Пользователь подписан на канал
    user_context.descripsion_mode = True
    main(call)
    return True  
  elif chat_member.status not in ["member"]:
    user_context.descripsion_mode = False
    try:
      bot.delete_message(user_context.send_book_msg.chat.id, user_context.send_book_msg.message_id)
    except:
      pass
    markup = telebot.types.InlineKeyboardMarkup()
    item = telebot.types.InlineKeyboardButton("Подписался ✅", callback_data='main')
    markup.add(item)
    user_context.reg = bot.send_message(call.message.chat.id,'Подпишитесь чтобы продолжить 🌐\nhttps://t.me/omfsrus',reply_markup=markup)
    user_context.ignoreFlag = True
    # Пользователь не подписан на канал
    return False    

def check_subscription_call_checker(user_id, channel_id):
  user_context = get_user_context(user_id)
  
  chat_member = bot.get_chat_member(chat_id=int(channel_id), user_id=int(user_id))
  if chat_member.status in ["member","administrator","creator"]:
    user_context.descripsion_mode = True
    return True  
  elif chat_member.status not in ["member"]:
    user_context.descripsion_mode = False
    return False  
# !----------------------------------------------------------------------------CALL_SHORT
@bot.callback_query_handler(func=lambda call: call.data == 'short')
def short_book_name(call):
  user_id = call.from_user.id
  user_context = get_user_context(user_id)
  
  if user_context.descripsion_mode is True:
    bot.delete_message(user_context.again_msg.chat.id, user_context.again_msg.message_id)
    user_context.send_book_msg = bot.send_message(call.message.chat.id,'Отправьте слово из названия или имени автора 📕')
    user_context.ignoreFlag = False
  else:
    check_subscription_call(user_id,channel_id,call)
    try:
      bot.delete_message(user_context.again_msg.chat.id, user_context.again_msg.message_id)
    except:
      pass
# !----------------------------------------------------------------------------CALL_CLEAR
@bot.callback_query_handler(func=lambda call: call.data == 'clear')
def clear(call):
  bot.answer_callback_query(call.id, 'Чистим 🧹', show_alert=True)
  user_id = call.from_user.id
  user_context = get_user_context(user_id)
  for message_obj in user_context.sentBooks:
    try:
      bot.delete_message(call.message.chat.id, message_obj.message_id)
    except:
      pass
  try:
    bot.delete_message(user_context.finish_msg.chat.id, user_context.finish_msg.message_id)
  except:
    pass
  user_context.noneFlag = False

  main(call)

# Настроим журнал логов
logging.basicConfig(filename='myapp.log', level=logging.ERROR)

# Создадим объекты для перенаправления stdout и stderr
stderr_logger = logging.getLogger('stderr_logger')

# Создадим обработчики для записи stdout и stderr в журнал
class StderrLogHandler(logging.Handler):
    def emit(self, record):
        log_message = self.format(record)
        stderr_logger.error(log_message)

# Добавим обработчики к объектам логирования
stderr_logger.addHandler(StderrLogHandler())

if __name__ == '__main__':
    while True:
        try:
            bot.polling(none_stop=True)
        except Exception as e:
            print(f"An error occurred: {e}")
            time.sleep(1)  # Добавьте задержку перед повторной попыткой опроса


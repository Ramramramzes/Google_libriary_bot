# -*- coding: utf-8 -*-
import telebot
import os
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
import time
import logging

load_dotenv()
myToken = os.getenv('myToken')
bot = telebot.TeleBot(myToken)

global channel_id,reg,warning_msg,descripsion_mode,ignoreFlag,send_book_msg,begin_msg,book_name,again_msg,finish_msg,sentBooks,message_obj,last_button_click

last_button_click = {}
book_name = ""

channel_id = os.getenv('channel_id')

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
  global channel_id,ignoreFlag,send_book_msg,begin_msg
  bot.send_message(message.chat.id,'Библиотека OMFS📚')
  try:
    bot.delete_message(message.chat.id, message.message_id)
  except:
    pass

  user_id = message.from_user.id
  check_subscription_mess(user_id,channel_id,message)
  ignoreFlag = True
  if descripsion_mode is False:
    bot.delete_message(message.chat.id, message.message_id)
  else:
    markup = telebot.types.InlineKeyboardMarkup()
    item = telebot.types.InlineKeyboardButton("Начать поиск", callback_data='main')
    markup.add(item)
    begin_msg = bot.send_message(message.chat.id,'Вы подписаны ✅',reply_markup=markup)
    ignoreFlag = True

# !----------------------------------------------------------------------------MESSAGE
@bot.message_handler()
def send_book(message):
  bot.send_chat_action(message.chat.id, action="typing")
  global ignoreFlag,book_name,again_msg,send_book_msg,finish_msg,sentBooks,message_obj
  user_id = message.from_user.id
  try:
    if ignoreFlag is not False:
      bot.delete_message(message.chat.id, message.id)
      return
  except:
    pass
  if check_subscription_call_checker(user_id, channel_id):
      
    book_name = message.text.strip()

    try:
      bot.delete_message(send_book_msg.chat.id, send_book_msg.message_id)
    except:
      pass


    if len(book_name) <= 2:
      markup = telebot.types.InlineKeyboardMarkup()
      item = telebot.types.InlineKeyboardButton("еще раз", callback_data='short')
      markup.add(item)
      bot.delete_message(message.chat.id, message.id)
      again_msg = bot.send_message(message.chat.id,'Слишком короткий запрос 🤏',reply_markup=markup)
      ignoreFlag = True
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
      if book_name.lower() in file_name.lower():
          if file_link not in finalArr:
            finalArr.append(file_link)
            nameArr.append(file_name)
    if len(finalArr) != 0:
      # Создание массива отправленных ссылок для дальнейшего удаления  
      ignoreFlag = True
      sentBooks = []
      inc = 0
      for link in finalArr:
        sentBooks.append(bot.send_message(message.chat.id, f'Похожие на "{book_name}" книги 📖 : <a href="{link}">{nameArr[inc]}</a>',disable_web_page_preview=True,parse_mode='HTML'))
        inc+=1
      
      # Создание кнопки и сохранения id для дальнейшего удаления
      # Удаляем сообщение пользователя
      bot.delete_message(message.chat.id, message.id)
      markup = telebot.types.InlineKeyboardMarkup()
      item = telebot.types.InlineKeyboardButton("Искать 🔎", callback_data='clear')
      markup.add(item)
      
      finish_msg = bot.send_message(message.chat.id, 'Поиск завершен ✅', reply_markup=markup)
    else:
      ignoreFlag = True
      markup = telebot.types.InlineKeyboardMarkup()
      item = telebot.types.InlineKeyboardButton("Искать 🔎", callback_data='main')
      markup.add(item)

      bot.delete_message(message.chat.id, message.id)
      finish_msg = bot.send_message(message.chat.id, 'Ничего не найдено ❌', reply_markup=markup)
      return
  else:
    bot.delete_message(message.chat.id, message.id)
    check_subscription_mess(user_id, channel_id,message)
# !----------------------------------------------------------------------------CALL_MAIN
@bot.callback_query_handler(func=lambda call: call.data == 'main')
def main(call):
  global channel_id,reg,descripsion_mode,ignoreFlag,begin_msg,again_msg,send_book_msg,book_name,finish_msg
  user_id = call.from_user.id
  if user_id in last_button_click and time.time() - last_button_click[user_id] < 3 and descripsion_mode is not True:
    bot.answer_callback_query(call.id, 'Вы уже нажали кнопку 😡', show_alert=True)
  else:
    last_button_click[user_id] = time.time()
    if descripsion_mode is False:
  # !----------------------------------------------------------------------------ПОДПИСКИ_НЕТ
      bot.answer_callback_query(call.id, 'Проверяем ⌛', show_alert=True)
      try:
        bot.delete_message(reg.chat.id, reg.message_id)
      except:
        pass
      try:
        bot.delete_message(finish_msg.chat.id, finish_msg.message_id)
      except:
        pass
      check_subscription_call(user_id,channel_id,call)
    else:
  # !---------------------------------------------------------------------------ПОДПИСКА_ЕСТЬ
      try:
        bot.delete_message(again_msg.chat.id, again_msg.message_id)
      except:
        pass
      try:
        bot.delete_message(begin_msg.chat.id, begin_msg.message_id)
      except:
        pass
      try:
        bot.delete_message(finish_msg.chat.id, finish_msg.message_id)
      except:
        pass

      send_book_msg = bot.send_message(call.message.chat.id,'Отправьте слово из названия или имени автора 📕')
      ignoreFlag = False

      try:
        bot.delete_message(reg.chat.id, reg.message_id)
      except:
        pass

def check_subscription_mess(user_id, channel_id,message):
  global reg,descripsion_mode,ignoreFlag
  chat_member = bot.get_chat_member(chat_id=int(channel_id), user_id=int(user_id))
  if chat_member.status in ["member","administrator","creator"]:
    # Пользователь подписан на канал
    descripsion_mode = True
    return True  
  elif chat_member.status not in ["member"]:
    descripsion_mode = False
    markup = telebot.types.InlineKeyboardMarkup()
    item = telebot.types.InlineKeyboardButton("Подписался ✅", callback_data='main')
    markup.add(item)
    try:
      bot.delete_message(send_book_msg.chat.id, send_book_msg.message_id)
    except:
      pass
    reg = bot.send_message(message.chat.id,'Подпишитесь чтобы продолжить 🌐\nhttps://t.me/omfsrus',reply_markup=markup)
    ignoreFlag = True
    # Пользователь не подписан на канал
    return False

def check_subscription_call(user_id, channel_id,call):
  global reg,descripsion_mode,ignoreFlag
  chat_member = bot.get_chat_member(chat_id=int(channel_id), user_id=int(user_id))
  if chat_member.status in ["member","administrator","creator"]:
    # Пользователь подписан на канал
    descripsion_mode = True
    main(call)
    return True  
  elif chat_member.status not in ["member"]:
    descripsion_mode = False
    try:
      bot.delete_message(send_book_msg.chat.id, send_book_msg.message_id)
    except:
      pass
    markup = telebot.types.InlineKeyboardMarkup()
    item = telebot.types.InlineKeyboardButton("Подписался ✅", callback_data='main')
    markup.add(item)
    reg = bot.send_message(call.message.chat.id,'Подпишитесь чтобы продолжить 🌐\nhttps://t.me/omfsrus',reply_markup=markup)
    ignoreFlag = True
    # Пользователь не подписан на канал
    return False    

def check_subscription_call_checker(user_id, channel_id):
  global reg,descripsion_mode,ignoreFlag
  chat_member = bot.get_chat_member(chat_id=int(channel_id), user_id=int(user_id))
  if chat_member.status in ["member","administrator","creator"]:
    descripsion_mode = True
    return True  
  elif chat_member.status not in ["member"]:
    descripsion_mode = False
    return False  
# !----------------------------------------------------------------------------CALL_SHORT
@bot.callback_query_handler(func=lambda call: call.data == 'short')
def short_book_name(call):
  global send_book_msg,ignoreFlag,user_id
  
  user_id = call.from_user.id
  if descripsion_mode is True:
    bot.delete_message(again_msg.chat.id, again_msg.message_id)
    send_book_msg = bot.send_message(call.message.chat.id,'Отправьте слово из названия или имени автора 📕')
    ignoreFlag = False
  else:
    check_subscription_call(user_id,channel_id,call)
    try:
      bot.delete_message(again_msg.chat.id, again_msg.message_id)
    except:
      pass
# !----------------------------------------------------------------------------CALL_CLEAR
@bot.callback_query_handler(func=lambda call: call.data == 'clear')
def clear(call):
  global message_obj,send_books,finish_msg,noneFlag
  for message_obj in sentBooks:
    bot.delete_message(call.message.chat.id, message_obj.message_id)
  bot.delete_message(finish_msg.chat.id, finish_msg.message_id)
  noneFlag = False

  main(call)

# Настроим журнал логов
logging.basicConfig(filename='myapp.log', level=logging.DEBUG)

# Создадим объекты для перенаправления stdout и stderr
stdout_logger = logging.getLogger('stdout_logger')
stderr_logger = logging.getLogger('stderr_logger')

# Создадим обработчики для записи stdout и stderr в журнал

class StderrLogHandler(logging.Handler):
    def emit(self, record):
        log_message = self.format(record)
        stderr_logger.error(log_message)

# Добавим обработчики к объектам логирования
stderr_logger.addHandler(StderrLogHandler())

if __name__ == '__main__':
    bot.polling(none_stop=True)


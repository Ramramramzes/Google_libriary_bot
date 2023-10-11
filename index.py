import telebot
import os
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build
import time

load_dotenv()
myToken = os.getenv('myToken')
bot = telebot.TeleBot(myToken)

global channel_id,reg,warning_msg,descripsion_mode,ignoreFlag,send_book_msg,begin_msg,book_name,again_msg

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
  bot.delete_message(message.chat.id, message.message_id)
  user_id = message.from_user.id
  check_subscription_mess(user_id,channel_id,message)
  ignoreFlag = True
  if descripsion_mode is False:
    bot.delete_message(message.chat.id, message.message_id)
  else:
    markup = telebot.types.InlineKeyboardMarkup()
    item = telebot.types.InlineKeyboardButton("Начать поиск", callback_data='main')
    markup.add(item)
    begin_msg = bot.send_message(message.chat.id,'Вы подписаны',reply_markup=markup)
    ignoreFlag = True




# !----------------------------------------------------------------------------MESSAGE
@bot.message_handler()
def send_book(message):
  global ignoreFlag,book_name,again_msg,send_book_msg
  user_id = message.from_user.id
  if ignoreFlag is not False:
      bot.delete_message(message.chat.id, message.id)
      return
  if check_subscription_call_checker(user_id, channel_id):
    print('messageHendler подписка - ',descripsion_mode)
      
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
        again_msg = bot.send_message(message.chat.id,'Слишком короткий запрос',reply_markup=markup)
        ignoreFlag = True
        return
  else:
    bot.delete_message(message.chat.id, message.id)
    check_subscription_mess(user_id, channel_id,message)



@bot.callback_query_handler(func=lambda call: call.data == 'main')
def main(call):
  global channel_id,reg,descripsion_mode,ignoreFlag,begin_msg,again_msg,send_book_msg,book_name
  user_id = call.from_user.id
  
  if descripsion_mode is False:
# !----------------------------------------------------------------------------ПОДПИСКИ_НЕТ
    bot.answer_callback_query(call.id, 'Проверяем⌛', show_alert=True)
    try:
      bot.delete_message(reg.chat.id, reg.message_id)
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

    send_book_msg = bot.send_message(call.message.chat.id,'Пришлите название книги')
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
    print('200')
    descripsion_mode = True
    return True  
  elif chat_member.status not in ["member"]:
    descripsion_mode = False
    markup = telebot.types.InlineKeyboardMarkup()
    item = telebot.types.InlineKeyboardButton("Подписался", callback_data='main')
    markup.add(item)
    try:
      bot.delete_message(send_book_msg.chat.id, send_book_msg.message_id)
    except:
      pass
    reg = bot.send_message(message.chat.id,'Подпишитесь чтобы продолжить\nhttps://t.me/omfsrus',reply_markup=markup)
    ignoreFlag = True
    print('400')
    # Пользователь не подписан на канал
    return False
  
def check_subscription_call(user_id, channel_id,call):
  global reg,descripsion_mode,ignoreFlag
  chat_member = bot.get_chat_member(chat_id=int(channel_id), user_id=int(user_id))
  if chat_member.status in ["member","administrator","creator"]:
    # Пользователь подписан на канал
    print('200')
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
    item = telebot.types.InlineKeyboardButton("Подписался", callback_data='main')
    markup.add(item)
    reg = bot.send_message(call.message.chat.id,'Подпишитесь чтобы продолжить\nhttps://t.me/omfsrus',reply_markup=markup)
    ignoreFlag = True
    print('400')
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

@bot.callback_query_handler(func=lambda call: call.data == 'short')
def short_book_name(call):
  global send_book_msg,ignoreFlag,user_id
  
  user_id = call.from_user.id
  if descripsion_mode is True:
    print('Short Подписка есть - ',descripsion_mode)
    bot.delete_message(again_msg.chat.id, again_msg.message_id)
    send_book_msg = bot.send_message(call.message.chat.id,'Пришлите название книги')
    ignoreFlag = False
  else:
    print('Short Подписки нет - ',descripsion_mode)
    check_subscription_call(user_id,channel_id,call)
    try:
      bot.delete_message(again_msg.chat.id, again_msg.message_id)
    except:
      pass


bot.polling(none_stop=True)
import telebot
import os
import time
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build

load_dotenv()
myToken = os.getenv('myToken')
bot = telebot.TeleBot(myToken)

global messageId,hello,ignoreFlag,started,message_obj,finish_msg,shortResp,goodResp,noneFlag,checkSub

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

shortResp,goodResp,noneFlag,checkSub = False,False,False,False

# !Работа бота ---------------------------------------------------------------------------------------------------------------->>>
@bot.message_handler(commands=['start'])
def start(message):
  global hello,ignoreFlag,started,helloFlag
  started = False
  if check_subscription(message.from_user.id, channel_id):
    ignoreFlag = True
    markup = telebot.types.InlineKeyboardMarkup()
    item = telebot.types.InlineKeyboardButton("Начать", callback_data='main')
    markup.add(item)
    hello = bot.send_message(message.chat.id,'Добро пожаловать в нашу библиотеку',reply_markup=markup)
    helloFlag = True

    bot.delete_message(message.chat.id, message.id)
  else:
    ignoreFlag = True
    markup = telebot.types.InlineKeyboardMarkup()
    item = telebot.types.InlineKeyboardButton("Подписался", callback_data='main')
    markup.add(item)
    hello = bot.send_message(message.chat.id,'Подпишитесь чтобы продолжить\nhttps://t.me/omfsrus',reply_markup=markup)
    bot.delete_message(message.chat.id, message.id)

@bot.callback_query_handler(func=lambda call: call.data == 'main')
def main(call):
  global messageId,hello,ignoreFlag,started,againMsgId,message_obj,finish_msg,finalArr,shortResp,goodResp,noneFlag,checkSub,helloFlag

  if check_subscription(call.message.chat.id, channel_id):
    messageId = bot.send_message(call.message.chat.id,'Пришлите название книги')
    if ignoreFlag == True and shortResp == True:
      ignoreFlag = False
      bot.delete_message(againMsgId.chat.id, againMsgId.message_id)
      if helloFlag == True:
        try:
          bot.delete_message(hello.chat.id,hello.id)
        except:
          pass
    if ignoreFlag == True and goodResp == True:
      ignoreFlag = False
      bot.delete_message(finish_msg.chat.id, finish_msg.message_id)
      if helloFlag == True:
        try:
          bot.delete_message(hello.chat.id,hello.id)
        except:
          pass
    if ignoreFlag == True and noneFlag == True:
      ignoreFlag = False
      bot.delete_message(finish_msg.chat.id, finish_msg.message_id)
      if helloFlag == True:
        try:
          bot.delete_message(hello.chat.id,hello.id)
        except:
          pass
    ignoreFlag = False

    if started == False:
      bot.delete_message(hello.chat.id,hello.id)
  else:
    ignoreFlag = True
    markup = telebot.types.InlineKeyboardMarkup()
    item = telebot.types.InlineKeyboardButton("Подписался", callback_data='main')
    markup.add(item)
    hello = bot.send_message(call.message.chat.id,'Подпишитесь чтобы продолжить\nhttps://t.me/omfsrus',reply_markup=markup)
    bot.delete_message(call.message.chat.id, call.message.id)
    helloFlag = True


@bot.message_handler()
def send_book(message):
  global messageId,book,message_obj,sentBooks,finish_msg,againMsgId,ignoreFlag,shortResp,goodResp,noneFlag,hello,helloFlag
  if check_subscription(message.from_user.id, channel_id):
    if ignoreFlag != False:
      bot.delete_message(message.chat.id, message.id)
      return
    
    book = message.text.strip()

    if len(book) <= 2:
      
      ignoreFlag = True
      markup = telebot.types.InlineKeyboardMarkup()
      item = telebot.types.InlineKeyboardButton("еще раз", callback_data='main')
      markup.add(item)

      noneFlag,goodResp,shortResp = False,False,True

      bot.delete_message(message.chat.id, message.message_id)
      againMsgId = bot.send_message(message.chat.id,'Слишком короткий запрос',reply_markup=markup)
      bot.delete_message(messageId.chat.id, messageId.message_id)
      return

    # Выполнение запроса для списка файлов и папок в данной папке
    results = service.files().list(q=f"'{folder_id}' in parents", fields="files(id, name)").execute()
    files = results.get('files', [])

    finalArr = []
    nameArr = []
    for file in files:
      file_id = file['id']
      file_name = file['name']
      file_link = f"https://docs.google.com/document/d/{file_id}"
      # Создание массива с ссылками совпавшими с поиском
      if book.lower() in file_name.lower():
          if file_link not in finalArr:
            finalArr.append(file_link)
            nameArr.append(file_name)
    if len(finalArr) != 0:
      # Создание массива отправленных ссылок для дальнейшего удаления  
      ignoreFlag = True
      sentBooks = []
      inc = 0
      for link in finalArr:
        sentBooks.append(bot.send_message(message.chat.id, f'Похожие на {book} ссылки : <a href="{link}">{nameArr[inc]}</a>',disable_web_page_preview=True,parse_mode='HTML'))
        inc+=1
      
      bot.delete_message(messageId.chat.id, messageId.message_id)
      bot.delete_message(message.chat.id, message.id)
      # Создание кнопки и сохранения id для дальнейшего удаления
      markup = telebot.types.InlineKeyboardMarkup()
      item = telebot.types.InlineKeyboardButton("искать еще", callback_data='clear')
      markup.add(item)
      
      noneFlag,goodResp,shortResp = False,True,False

      finish_msg = bot.send_message(message.chat.id, 'Поиск завершен', reply_markup=markup)
      
    else:
      ignoreFlag,noneFlag,goodResp,shortResp = True,True,False,False

      markup = telebot.types.InlineKeyboardMarkup()
      item = telebot.types.InlineKeyboardButton("искать еще", callback_data='main')
      markup.add(item)

      finish_msg = bot.send_message(message.chat.id, 'Ничего не найдено', reply_markup=markup)
      bot.delete_message(messageId.chat.id, messageId.message_id)
      bot.delete_message(message.chat.id, message.id)
      return
  else:
    ignoreFlag = True
    markup = telebot.types.InlineKeyboardMarkup()
    item = telebot.types.InlineKeyboardButton("Подписался", callback_data='main')
    markup.add(item)
    hello = bot.send_message(message.chat.id,'Подпишитесь чтобы продолжить\nhttps://t.me/omfsrus',reply_markup=markup)
    bot.delete_message(message.chat.id, message.id)
    helloFlag = True

@bot.callback_query_handler(func=lambda call: call.data == 'clear')
def clear(call):
  global message_obj,send_books,finish_msg,noneFlag
  for message_obj in sentBooks:
    bot.delete_message(call.message.chat.id, message_obj.message_id)
  
  noneFlag = False
  main(call)

def check_subscription(user_id, channel_id):
    global checkSub
    chat_member = bot.get_chat_member(chat_id=int(channel_id), user_id=int(user_id))
    if chat_member.status in ["member","administrator","creator"]:
      # Пользователь подписан на канал
      checkSub = True
      print('200')
      return True  
    elif chat_member.status not in ["member"]:
      checkSub = False
      print('400')
      # Пользователь не подписан на канал
      return False  

bot.polling(none_stop=True)
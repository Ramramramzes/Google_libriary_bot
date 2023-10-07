import telebot
import os
import time
from dotenv import load_dotenv
from google.oauth2 import service_account
from googleapiclient.discovery import build

load_dotenv()
myToken = os.getenv('myToken')
bot = telebot.TeleBot(myToken)

global messageId,book,sentBooks,finish_msg,againMsgId,ignoreFlag,startFlag,callFlag
ignoreFlag = False
againMsgId = None
messageId = None
callFlag = True

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

# !Работа бота ---------------------------------------------------------------------------------------------------------------->>>
@bot.message_handler(commands=['start'])
def start(message):
  global messageId,againMsgId,ignoreFlag,callFlag
  if check_subscription(message.from_user.id, channel_id):
    if callFlag is False:
      callFlag = True
      bot.delete_message(againMsgId.chat.id, againMsgId.message_id)  
    ignoreFlag = False
    messageId = bot.send_message(message.chat.id,'Пришлите название книги')
    bot.delete_message(message.chat.id, message.id)
  else:
    if check_subscription(message.from_user.id, channel_id):
      start(message)
    else:
      bot.send_message(message.chat.id, 'Reg')


@bot.message_handler()
def send_book(message):
  global messageId,book,sentBooks,finish_msg,againMsgId,ignoreFlag,callFlag

  if check_subscription(message.from_user.id, channel_id):
    if ignoreFlag:
      bot.delete_message(message.chat.id, message.id)
      return
    book = message.text.strip()

    if len(book) <= 2:
      againMsgId = bot.send_message(message.chat.id,'Слишком короткий запрос')
      callFlag = False
      bot.delete_message(messageId.chat.id, messageId.message_id)
      time.sleep(1.5)
      start(message)
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
      sentBooks = []
      inc = 0
      for link in finalArr:
        sentBooks.append(bot.send_message(message.chat.id, f'Похожие на {book} ссылки : <a href="{link}">{nameArr[inc]}</a>',disable_web_page_preview=True,parse_mode='HTML'))
        inc+=1
      
      bot.delete_message(messageId.chat.id, messageId.message_id)
      bot.delete_message(message.chat.id, message.id)
      # Создание кнопки и сохранения id для дальнейшего удаления
      markup = telebot.types.InlineKeyboardMarkup()
      item = telebot.types.InlineKeyboardButton("Искать еще", callback_data='start_search')
      markup.add(item)
      finish_msg = bot.send_message(message.chat.id, 'Поиск завершен', reply_markup=markup)
      ignoreFlag = True
    else:
      markup = telebot.types.InlineKeyboardMarkup()
      item = telebot.types.InlineKeyboardButton("Искать еще", callback_data='again')
      markup.add(item)
      finish_msg = bot.send_message(message.chat.id, 'Ничего не найдено', reply_markup=markup)
      bot.delete_message(messageId.chat.id, messageId.message_id)
      bot.delete_message(message.chat.id, message.id)
      ignoreFlag = True
  else:
    bot.send_message(message.chat.id, 'Reg')

# Коллбэк для удаления и запуска /старта
@bot.callback_query_handler(func=lambda call: call.data == 'start_search')
def callback_start_search(call):
  global sentBooks,finish_msg,ignoreFlag,callFlag
  callFlag = True
  if check_subscription(call.message.from_user.id, channel_id):
    for message_obj in sentBooks:
      bot.delete_message(call.message.chat.id, message_obj.message_id)
      
    start(call.message)
    bot.delete_message(finish_msg.chat.id, finish_msg.message_id)
  else:
    bot.send_message(call.message.chat.id, 'Reg')

@bot.callback_query_handler(func=lambda call: call.data == 'again')
def again(call):
  global ignoreFlag,finish_msg,callFlag
  callFlag = True
  start(call.message)

def check_subscription(user_id, channel_id):
    try:
        chat_member = bot.get_chat_member(chat_id=int(channel_id), user_id=int(user_id))
        if chat_member.status in ["member", "administrator", "creator"]:
          # Пользователь подписан на канал
          return True  
        else:
          # Пользователь не подписан на канал
          return False  
    except Exception as e:
        # Ошибка при проверке подписки
        return False  

bot.polling(none_stop=True)
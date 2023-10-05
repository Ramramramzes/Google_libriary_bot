import telebot
import requests
import json
from dotenv import load_dotenv
import os
from google.oauth2 import service_account
from googleapiclient.discovery import build
load_dotenv()
myToken = os.getenv('myToken')
bot = telebot.TeleBot(myToken)

global messageId,book,sentBooks,finish_msg

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

#todo ID папки, которую вы хотите просмотреть  // Закинуть в .env
folder_id = '1wbacSg6NrZBJlVVuELDQXngCpSSkWNO1'

# # Выполнение запроса для списка файлов и папок в данной папке
# results = service.files().list(q=f"'{folder_id}' in parents", fields="files(id, name)").execute()
# files = results.get('files', [])

# # if not files:
# #   print(f"В данной папке нет файлов и папок.")
# # else:
# #   print(f"Содержимое папки (ID: {folder_id}):")
# #   for file in files:
# #     file_id = file['id']
# #     file_name = file['name']
# #     file_link = f"https://docs.google.com/document/d/{file_id}"
# #     # print(f"Имя файла: {file_name}\nСсылка: {file_link}")

# !Работа бота ----------------------------------------------------------------------------------------------------------------
@bot.message_handler(commands=['start'])
def start(message):
  global messageId
  messageId = bot.send_message(message.chat.id,'Пришлите название книги')
  bot.delete_message(message.chat.id, message.id)

@bot.message_handler()
def send_book(message):
  global messageId,book,sentBooks,finish_msg
  book = message.text.strip()

  results = service.files().list(q=f"'{folder_id}' in parents", fields="files(id, name)").execute()
  files = results.get('files', [])

  finalArr = []
  for file in files:
    file_id = file['id']
    file_name = file['name']
    file_link = f"https://docs.google.com/document/d/{file_id}"

    if book in file_name:
        if file_link not in finalArr:
          finalArr.append(file_link)
        
  sentBooks = []
  for link in finalArr:
    sentBooks.append(bot.send_message(message.chat.id, f'Книга по запросу "{book}" : \n{file_name}\n {link}',disable_web_page_preview=True))
  
  bot.delete_message(messageId.chat.id, messageId.message_id)
  bot.delete_message(message.chat.id, message.id)

  markup = telebot.types.InlineKeyboardMarkup()
  item = telebot.types.InlineKeyboardButton("Искать еще", callback_data='start_search')
  markup.add(item)
  finish_msg = bot.send_message(message.chat.id, 'Поиск завершен', reply_markup=markup)  


@bot.callback_query_handler(func=lambda call: call.data == 'start_search')
def callback_start_search(call):
    global sentBooks,finish_msg
    for message_obj in sentBooks:
      bot.delete_message(call.message.chat.id, message_obj.message_id)
    
    start(call.message)
    bot.delete_message(finish_msg.chat.id, finish_msg.message_id)



bot.polling(none_stop=True)
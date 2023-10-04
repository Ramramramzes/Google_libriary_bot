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
folder_id = '1wbacSg6NrZBJlVVuELDQXngCpSSkWNO1'

# Выполнение запроса для списка файлов и папок в данной папке
results = service.files().list(q=f"'{folder_id}' in parents", fields="files(id, name)").execute()
files = results.get('files', [])

if not files:
    print(f"В данной папке нет файлов и папок.")
else:
    print(f"Содержимое папки (ID: {folder_id}):")
    for file in files:
        file_id = file['id']
        file_name = file['name']
        file_link = f"https://docs.google.com/document/d/{file_id}"
        print(f"Имя файла: {file_name}\nСсылка: {file_link}")
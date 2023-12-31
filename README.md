# Телеграм-бот для поиска литературы по челюстно-лицевой хирургии

## Описание
Этот бот предназначен для поиска литературы по челюстно-лицевой хирургии в библиотеке, данные которой хранятся на Google Диске. Пользователи могут отправлять запросы на поиск по словам из названия или имени автора, и бот возвращает ссылки на соответствующие книги.

## Используемые библиотеки и зависимости
- `telebot`: для работы с Telegram API.
- `os`: для работы с операционной системой.
- `dotenv`: для загрузки переменных окружения из файла `.env`.
- `google.oauth2` и `googleapiclient.discovery`: для работы с Google API и доступа к Google Диску.
- `time`: для управления временными задержками.
- `logging`: для ведения журнала логов.

## Настройка
1. Создайте бота в Telegram через [@BotFather](https://t.me/botfather) и получите токен.
2. Создайте канал в Telegram и получите его ID.
3. Создайте проект в [Google Cloud Console](https://console.cloud.google.com/) и включите API Google Drive.
4. Создайте файл `.env` и добавьте следующие переменные:
   - `myToken`: токен вашего бота.
   - `channel_id`: ID вашего канала.
   - `folder_id`: ID папки на Google Диске, содержащей литературу.
5. Создайте JSON-файл ключа службы Google API и сохраните его как `myKey.json`.
6. Установите необходимые зависимости, используя `pip install -r requirements.txt`.

## Запуск
1. Запустите бот, используя `python ваш_файл.py`.
2. Бот готов к использованию.

## Использование
1. Напишите `/start` для начала взаимодействия с ботом.
2. Если вы подписаны на канал, вам будет предоставлен доступ к поиску литературы.
3. Отправьте слово из названия или имени автора, чтобы получить соответствующие книги.

## Обработка ошибок
Ошибки логгируются в файл `myapp.log`. При возникновении ошибки бот будет пытаться продолжить свою работу с задержкой в 1 секунду.

## Недочеты
При длительной паузе бот забывает данные пользователей, что может привести к сбросу текущего чата при повторном взаимодействии.

## Доработки
Возможное улучшение, рассмотреть вариант изменения одного сообщения вместо удаления при долгих паузах. Это позволит сохранить эффект "чистого чата", но дата сообщения будет неизменна.

## Примечание
Бот реализован в бесконечном цикле, обеспечивая постоянное взаимодействие с Telegram API. В случае ошибки бот продолжит опрос снова после короткой задержки.


1. **Автор проекта:** [Ramramramzes](https://github.com/Ramramramzes) - создатель бота.
2. **Участники и Помощники:**
   - [SawGoD](https://github.com/SawGoD) - активное участие в обсуждении и оптимизации структуры проекта.
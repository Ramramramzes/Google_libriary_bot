# Развёртывание на сервере

## Требования

- Docker и Docker Compose
- Файлы `.env` и `myKey.json` в папке проекта
- Бот добавлен в канал из `channel_id` как **администратор** (иначе проверка подписки не работает)

## Запуск

```bash
unzip google_libriary_bot-deploy.zip
cd google_libriary_bot
docker compose up -d --build
docker compose logs -f
```

## Проверка

```bash
docker compose ps          # STATUS: Up
docker compose logs --tail 20
```

Остановка: `docker compose down`  
Перезапуск: `docker compose restart`

## Данные

База SQLite хранится в Docker volume `bot_data` (`/data/bot.db` в контейнере).

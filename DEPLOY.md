# Развёртывание на сервере

## Требования

- Docker и Docker Compose
- Файлы `.env` и `myKey.json` в папке проекта (см. `.env.example`)
- Бот добавлен в канал из `channel_id` как **администратор**
- В @BotFather включены **Telegram Stars** для оплаты Premium

## Premium

- Подписка на канал обязательна
- 5 книг (ссылок) в день бесплатно — `DAILY_FREE_LIMIT`
- Premium 350 ⭐ / 30 дней — `PREMIUM_STARS`, `PREMIUM_DAYS`
- Тест без оплаты: `ADMIN_USER_IDS` + команда `/test_premium`

Подробнее: [TESTING.md](TESTING.md)

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

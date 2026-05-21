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

## Уведомление пользователей после обновления

Если после деплоя нужно попросить пользователей удалить чат и написать `/start`:

1. В `.env` увеличьте `MAINTENANCE_REVISION` (например `1` → `2`).
2. Пересоберите и перезапустите: `docker compose up -d --build`.

Рассылка уйдёт **один раз** для каждого значения revision. Обычный `restart` без смены revision повторно не шлёт.

- По умолчанию — всем, кто есть в базе.
- `MAINTENANCE_NOTIFY_ALL=0` — только активным (сессия, Premium или активность за 30 дней).
- Ручная рассылка админом: `/broadcast_reset` (всем) или `/broadcast_reset active` (только активным).

Подробнее: [TESTING.md](TESTING.md)

## Данные

База SQLite хранится в Docker volume `bot_data` (`/data/bot.db` в контейнере).

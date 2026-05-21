# Тестирование Premium и лимита книг

## Настройка в @BotFather

1. Откройте @BotFather → ваш бот.
2. Включите **Monetization** / платежи **Telegram Stars** (если пункт есть).
3. Сохраните токен в `.env`.

## Переменные `.env`

```env
PREMIUM_STARS=350
PREMIUM_DAYS=30
DAILY_FREE_LIMIT=5
ADMIN_USER_IDS=ВАШ_TELEGRAM_ID
```

Узнать свой ID: [@userinfobot](https://t.me/userinfobot)

## Запуск

```bash
docker compose up -d --build
# или
./run.sh
```

## Сценарии проверки

### 1. Подписка на канал
- Отпишитесь от канала → бот просит подписаться.
- Подпишитесь → `/start` → «Вы подписаны ✅».

### 2. Лимит 5 книг/день
- `/status` — «Сегодня: 0/5 книг».
- Отправьте запрос с большой выдачей (например «а» или «м»).
- Повторяйте, пока не исчерпаете 5 **ссылок** за день.
- Следующий поиск → «Лимит на сегодня исчерпан».

### 3. Premium без оплаты (админ)
```
/test_premium
```
Только для `ADMIN_USER_IDS`. Даёт Premium на 30 дней.

- `/status` → «Premium активен… без лимита».
- Поиск книг снова работает без лимита.

### 4. Оплата Stars (реальный тест)
```
/premium
```
или кнопка **⭐ Premium 350 ⭐/мес**.

- Подтвердите оплату Stars в Telegram.
- После оплаты: «Premium активирован».

> Для теста можно временно поставить `PREMIUM_STARS=1` в `.env` и перезапустить бота.

### 5. Сброс лимита на день
Лимит сбрасывается в **полночь по дате сервера** (UTC даты в контейнере).

Для ручного сброса в тестах:
```bash
docker compose exec bot python -c "
import db; db.init_db()
db.upsert_user(USER_ID, CHAT_ID, daily_books_count=0, daily_reset_date='')
"
```

## Логи

```bash
docker compose logs -f
```

Успешная оплата: `Premium granted user=...`

## Частые проблемы

| Проблема | Решение |
|----------|---------|
| Нет кнопки Pay / invoice | Включить Stars в @BotFather |
| `/test_premium` не работает | Добавить свой ID в `ADMIN_USER_IDS` |
| Лимит не срабатывает | У пользователя уже Premium (`/status`) |

### 6. Рассылка «удалите чат» после обновления

**Автоматически при деплое:** в `.env` задайте или увеличьте `MAINTENANCE_REVISION=1`, пересоберите бота.

**Вручную (админ):** `/broadcast_reset` — всем из базы, `/broadcast_reset active` — только активным.

Можно передать свой текст:

- `/broadcast_reset Текст уведомления`
- `/broadcast_reset active Текст уведомления`

В логах: `Maintenance notify revision=... sent=...`

### 7. Подарок Premium по ID (админ)

Выдать Premium пользователю из базы:

- `/gift_premium USER_ID`
- `/gift_premium USER_ID DAYS`

Пример: `/gift_premium 123456789 30`

> Пользователь должен хотя бы один раз запустить бота (`/start`), чтобы его `chat_id` был в базе.

### 8. Видимость команд только для админа

- Обычным пользователям в меню команд показываются: `/start`, `/status`, `/premium`.
- Админам из `ADMIN_USER_IDS` дополнительно видны: `/test_premium`, `/broadcast_reset`, `/gift_premium`.
- Если изменили `ADMIN_USER_IDS`, перезапустите бота (`docker compose restart`), чтобы меню обновилось.

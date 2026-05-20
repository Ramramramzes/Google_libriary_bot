"""Оплата Premium через Telegram Stars (XTR)."""
import os
import time
import logging
import telebot
import db

PREMIUM_STARS = int(os.getenv('PREMIUM_STARS', '350'))
PREMIUM_DAYS = int(os.getenv('PREMIUM_DAYS', '30'))
CURRENCY = 'XTR'
INVOICE_PAYLOAD_PREFIX = 'premium_month_'


def premium_payload(user_id):
    return f'{INVOICE_PAYLOAD_PREFIX}{user_id}'


def is_premium_payload(payload, user_id):
    return payload == premium_payload(user_id)


def send_premium_invoice(bot, chat_id, user_id):
    prices = [telebot.types.LabeledPrice(
        label=f'Premium {PREMIUM_DAYS} дней',
        amount=PREMIUM_STARS,
    )]
    return bot.send_invoice(
        chat_id,
        title='Premium OMFS Library',
        description=(
            f'Безлимитный поиск книг на {PREMIUM_DAYS} дней.\n'
            f'Стоимость: {PREMIUM_STARS} ⭐'
        ),
        invoice_payload=premium_payload(user_id),
        provider_token=None,
        currency=CURRENCY,
        prices=prices,
    )


def handle_pre_checkout(bot, query):
    user_id = query.from_user.id
    if not is_premium_payload(query.invoice_payload, user_id):
        bot.answer_pre_checkout_query(
            query.id,
            ok=False,
            error_message='Неверный заказ. Попробуйте /premium снова.',
        )
        return
    if query.currency != CURRENCY:
        bot.answer_pre_checkout_query(
            query.id,
            ok=False,
            error_message='Оплата только в Telegram Stars.',
        )
        return
    bot.answer_pre_checkout_query(query.id, ok=True)


def handle_successful_payment(message):
    pay = message.successful_payment
    user_id = message.from_user.id
    chat_id = message.chat.id
    if not is_premium_payload(pay.invoice_payload, user_id):
        logging.warning('Unknown payment payload: %s', pay.invoice_payload)
        return False
    db.grant_premium(user_id, chat_id, PREMIUM_DAYS)
    db.log_payment(user_id, pay.total_amount, pay.invoice_payload)
    logging.info(
        'Premium granted user=%s stars=%s', user_id, pay.total_amount
    )
    return True

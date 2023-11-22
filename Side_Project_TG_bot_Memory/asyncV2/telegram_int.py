# -*- coding: utf-8 -*-

import json
import requests
from retrying_async import retry
from constants import MONTH_SUBSCRIPTION_PRICE, DAY_LIMIT_SUBSCRIPTION, PAY_TOKEN_TEST, PAY_TOKEN
from datetime import datetime, timedelta


def handle_telegram_errors(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (Exception, requests.exceptions.RequestException) as e:
            # Handle the database connection error here
            print(f"Telegram error: {e}")
            # You can log the error, retry the connection, or perform other actions as needed
            # You might want to raise an exception or return a specific value here
            return None  # For demonstration purposes, return None in case of an error
    return wrapper


class TelegramInt:
    def __init__(self, bot_token):
        self.bot_token = bot_token
        self.base_url = 'https://api.telegram.org/bot'

    @handle_telegram_errors
    @retry(attempts=3, delay=3)
    async def send_text(self, message, chat_id, msg_id=None, reply_markup=None):
        payload = {
            'chat_id': chat_id,
            'text': message,
            'reply_to_message_id': msg_id
        }
        # Convert the keyboard dictionary to JSON string and add to the payload
        if reply_markup:
            reply_markup = json.dumps(reply_markup)
            payload['reply_markup'] = reply_markup
        print("TG sending the text to", chat_id)
        response = requests.post(
            self.base_url + self.bot_token + '/sendMessage',
            json=payload, timeout=10
        )
        response.raise_for_status()  # Raises an exception for non-2xx status codes
        # print("TG sent the data", response)
        return response.json()

    @handle_telegram_errors
    @retry(attempts=3)
    async def send_photo(self, photo, message, chat_id, reply_markup=None):

        payload = {
            'chat_id': chat_id,
            'caption': message,
            'parse_mode': 'HTML',
            'photo': photo
        }
        # Convert the keyboard dictionary to JSON string and add to the payload
        if reply_markup:
            reply_markup = json.dumps(reply_markup)
            payload['reply_markup'] = reply_markup
        print("TG sending the photo to ", chat_id)
        response = requests.post(
            self.base_url + self.bot_token + '/sendPhoto',
            json=payload, timeout=10
        )
        response.raise_for_status()  # Raises an exception for non-2xx status codes
        # print("TG sent the photo", response)
        return response.json()

    @handle_telegram_errors
    @retry(attempts=3)
    async def delete_message(self, user_id, msg_id):
        api_url = self.base_url + self.bot_token + '/deleteMessage'

        payload = {
            'chat_id': user_id,
            'message_id': msg_id
        }
        response = requests.get(api_url, json=payload, timeout=20)
        response.raise_for_status()
        return response


    @handle_telegram_errors
    @retry(attempts=3)
    async def user_subscribed(self, user_id, channel_name):
        # Получаем информацию о подписке пользователя на канал
        api_url = self.base_url + self.bot_token + '/getChatMember'
        params = {'chat_id': '@' + channel_name, 'user_id': user_id}
        response = requests.get(api_url, params=params)
        response.raise_for_status()
        data = response.json()
        print('Subscription data: ', data)
        if response.status_code == 200 and data['ok']:
            # Check if the user is a member of the channel
            return data['result']['status'] in ['member', 'creator', 'admin']
        else:
            # Failed to fetch the chat member information
            return False

    @handle_telegram_errors
    @retry(attempts=3)
    async def set_typing_status(self, chat_id):
        url = self.base_url + self.bot_token + '/sendChatAction'
        payload = {
            'chat_id': chat_id,
            'action': 'typing'
        }
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return response.json()

    @handle_telegram_errors
    @retry(attempts=3, delay=3)
    async def edit_bot_message(self, text, chat_id, message_id):
        url = self.base_url + self.bot_token + '/editMessageText'
        payload = {
            'chat_id': chat_id,
            'message_id': message_id,
            'text': text
        }
        print('Editing', message_id)
        response = requests.post(url, json=payload, timeout=20)
        response.raise_for_status()
        print("Edited the message in TG")
        return response.json()

    @handle_telegram_errors
    @retry(attempts=3, delay=3)
    async def edit_bot_message_markup(self, chat_id, message_id, reply_markup):
        url = self.base_url + self.bot_token + '/editMessageReplyMarkup'
        payload = {
            'chat_id': chat_id,
            'message_id': message_id,
            'reply_markup': reply_markup
        }
        # print('Editing', payload)
        try:
            response = requests.post(url, json=payload, timeout=20)
        except Exception as e:
            print(f'Got the markup problem - {e}')
            response = None
            # response.raise_for_status()
        if response:
            print("Edited the markup in message in TG", response)
            return response.json()

    @handle_telegram_errors
    @retry(attempts=3, delay=3)
    async def get_updates(self, last_update):
        # Check for new messages in Telegram group
        # let's test if it works with offset +1
        last_update = str(int(last_update['last_update']) + 1)
        url = self.base_url + self.bot_token + f'/getUpdates?offset={last_update}'
        response = requests.get(url, timeout=20)
        response.raise_for_status()
        data = json.loads(response.content)
        # provide all messages instead of one in update
        # result = data['result'][len(data['result'])-1]
        result = data['result']
        if data['result']:
            print("The Update is:", data['result'])
            print(f"We have got {len(data['result'])} messages in the update")
        return result

    @handle_telegram_errors
    @retry(attempts=3)
    async def answer_pre_checkout(self, pre_checkout_query_id):
        url = self.base_url + self.bot_token + '/answerPreCheckoutQuery'
        payload = {
            "pre_checkout_query_id": pre_checkout_query_id,
            "ok": True
        }
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return response

    @handle_telegram_errors
    async def handle_payment(self, payload):
        url = self.base_url + self.bot_token + "/sendInvoice"
        # Send the payment request
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return response

    @handle_telegram_errors
    @retry(attempts=3)
    async def send_work(self, work, chat_id, reply_markup=None, reply_msg_id=None, type_w=None):

        work_name = work.work_name or work.work_name_orig
        work_year = work.work_year or "год н/д"
        work_desc = work.desc or "Описание недоступно"
        work_type = work.work_type
        if type_w == 'random':
            type_w = 'Случайная'
        elif type_w == 'recommend':
            type_w = "Рекомендация"
        else:
            type_w = ""

        message = f'<code>{type_w}</code>\n{work.work_type.capitalize()} "{work_name}", {work_year}\nАвтор - {work.author}\n' \
                  f'Рейтинг - {work.rating} ({work.voters})\n\n{work_desc}'
        if len(message) > 1012:
            message = message[:1008] + " ..."

        photo_url = work.image

        if photo_url:

            await self.send_photo(photo_url, message, chat_id, reply_markup)
            return

        payload = {
            'chat_id': chat_id,
            'parse_mode': 'HTML',
            'text': message,
        }
        # Convert the keyboard dictionary to JSON string and add to the payload

        if reply_markup:
            reply_markup = json.dumps(reply_markup)
            payload['reply_markup'] = reply_markup
        print("TG sending the text", payload)
        response = requests.post(
            self.base_url + self.bot_token + '/sendMessage',
            json=payload, timeout=10
        )
        response.raise_for_status()  # Raises an exception for non-2xx status codes
        print("TG sent the data", response)
        return response.json()

    @handle_telegram_errors
    async def handle_pre_checkout_query(self, update):
        pre_checkout_query_id = update['pre_checkout_query']['id']
        invoice_payload = update['pre_checkout_query']['invoice_payload']
        currency = update['pre_checkout_query']['currency']
        total_amount = int(update['pre_checkout_query']['total_amount']) / 100
        user_id = update['pre_checkout_query']['from']['id']
        # Confirm the payment
        await self.answer_pre_checkout(pre_checkout_query_id)
        print(f'The id {user_id} is going to pay {total_amount} in {currency} for {invoice_payload}')

    @handle_telegram_errors
    async def handle_pay_command(self, chat_id):
        # Set up the payment request
        # данные тестовой карты: 1111 1111 1111 1026, 12/22, CVC 000.
        # url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendInvoice"
        # prices = json.dumps([{"label": "Month subscription", "amount": MONTH_SUBSCRIPTION_PRICE * 100}])
        provider_data = json.dumps({
            "receipt": {
                "items": [
                    {
                        "description": "Месячная подписка на Biblionarium GPT Bot",
                        "quantity": "1",
                        "amount": {
                            "value": f"{MONTH_SUBSCRIPTION_PRICE}.00",
                            "currency": "RUB"
                        },
                        "vat_code": "1",
                    }
                ]
                # "customer": {
                #     "email": 'mitinvlad@mail.ru'
                # }
            }
        })
        # print(prices)
        description = f'Расширяет лимит сообщений в день до {DAY_LIMIT_SUBSCRIPTION}'
        amount = f"{MONTH_SUBSCRIPTION_PRICE * 100}"
        payload = {
            "chat_id": chat_id,
            "title": "Месячная подписка",
            "description": description,
            "payload": "Month_subscription",
            "need_email": True,
            "send_email_to_provider": True,
            "provider_token": PAY_TOKEN,  # CHANGE FOR PRIMARY
            "provider_data": provider_data,
            "start_parameter": "The-Payment",
            "currency": "RUB",
            "prices": [{"label": "Месячная подписка", "amount": amount}]
        }
        # # Send the payment request
        # # print(payload)
        # response = requests.post(url, json=payload)
        # # print(response)
        # response.raise_for_status()
        await self.handle_payment(payload)

    @handle_telegram_errors
    @retry(attempts=3)
    async def handle_successful_payment(self, conn, update, subs_ext):
        amount = str(int(update['successful_payment']['total_amount']) / 100)
        receipt_message = f"Спасибо за оплату!\n" \
                          f"Товар: {update['successful_payment']['invoice_payload']}\n" \
                          f"Сумма: {amount}\n" \
                          f"Валюта: {update['successful_payment']['currency']}\n"

        chat_id = update['chat']['id']
        await self.send_text(receipt_message, chat_id)

        # # get the current status of the user
        current_subscription_status, current_start_date, current_expiration_date = await subs_ext.get_subscription(
            conn, chat_id)

        # if the user doesn't have any subscription
        if current_subscription_status == 0:
            subscription_start_date = datetime.now()
            subscription_expiration_date = subscription_start_date + timedelta(days=31)
        else:
            # if the user already has a subscription we copy the start date
            subscription_start_date = datetime.strptime(current_start_date, '%Y-%m-%d')
            subscription_expiration_date = datetime.strptime(current_expiration_date, '%Y-%m-%d') + timedelta(days=31)

        await subs_ext.update_subscription_status(conn, chat_id, 1, subscription_start_date.strftime('%Y-%m-%d'),
                                                  subscription_expiration_date.strftime('%Y-%m-%d'))

import requests
import json
import os
import re
import random
import memory
import asyncio
import os
import research
import sqlite3
import time
from retrying_async import retry
from datetime import datetime, timedelta
import sys

if sys.stdout.encoding != 'utf-8':
    sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

# Set default encoding to UTF-8 for stderr
if sys.stderr.encoding != 'utf-8':
    sys.stderr = open(sys.stderr.fileno(), mode='w', encoding='utf-8', buffering=1)

# OpenAI secret Key
API_KEY = os.environ['API_KEY']
# Models: text-davinci-003,text-curie-001,text-babbage-001,text-ada-001
# MODEL = 'text-davinci-003'
MODEL = 'gpt-3.5-turbo'
# Telegram secret access bot token
BOT_TOKEN = os.environ['BOT_TOKEN']
# Specify all group ID the bot can respond too
ALLOWED_GROUP_ID = os.environ['ALLOWED_GROUP_ID']
# Specify your Chat Bot handle
CHATBOT_HANDLE = os.environ['CHATBOT_HANDLE']
# The token for the payment provider
PAY_TOKEN = os.environ['PAY_TOKEN']
# Retrieve last ID message : Create an empty text file named chatgpt.txt, write 1 on the first line of
# the text file and save it, write the full path of your file below
FILENAME = 'chatgpt.txt'  # the update number is stored

ASK_COMMAND = '/ask'
CLEAR_COMMAND = '/clear'
START_COMMAND = '/start'
INFO_COMMAND = '/info'
REFERRAL_COMMAND = '/refer'

SUBSCRIPTION_COMMAND = '/pay'
SUBSCRIPTION_DATABASE = 'subscriptions.db'
MESSAGES_DATABASE = 'messages.db'
BOT_NAME = os.environ['BOT_NAME']
PAY_TOKEN_TEST = os.environ['PAY_TOKEN_TEST']
# SBER_TOKEN_TEST = "401643678:TEST:266f8c81-0fc1-46ac-b57f-64a5fcc97616"
# Номер карты	2200 0000 0000 0053
# Дата истечения срока действия	2024/12
# Проверочный код на обратной стороне	123

CHANNEL_NAME = 'Biblionarium'
DAY_LIMIT_PRIVATE = 10  # base is 10
DAY_LIMIT_SUBSCRIPTION = 100
CONTEXT_DEPTH = 3 * 2  # twice the context, because we get the users and the bots messages, base would be 10 * 2
MAX_TOKENS = 500
REFERRAL_BONUS = 30  # free messages that are used after the limit is over, base is 30
MONTH_SUBSCRIPTION_PRICE = 150
file = 'ClockworkOrange.txt'  # the current book loaded file

conn = sqlite3.connect(MESSAGES_DATABASE)
cursor = conn.cursor()

conn_pay = sqlite3.connect(SUBSCRIPTION_DATABASE)
cursor_pay = conn_pay.cursor()

# Create a table to store messages
cursor.execute('''CREATE TABLE IF NOT EXISTS messages
                  (id INTEGER PRIMARY KEY, timestamp INTEGER, chat_id INTEGER, role TEXT, message TEXT, 
                  cleared INTEGER DEFAULT 0, subscription_status INTEGER, 
                  FOREIGN KEY (chat_id) REFERENCES subscriptions (chat_id))''')
conn.commit()

# Create the subscriptions table
cursor_pay.execute('''CREATE TABLE IF NOT EXISTS subscriptions
                 (chat_id INTEGER PRIMARY KEY, subscription_status INTEGER, revealed_date  TEXT, start_date TEXT, 
                 expiration_date TEXT, referral_link TEXT, referred_by TEXT, bonus_count INTEGER DEFAULT 0)''')
conn_pay.commit()


# Make the request to the OpenAI API
@retry(attempts=3, delay=3)
async def openAI(prompt, max_tokens, messages):
    # the example
    # messages = [
    #     {"role": "system", "content": "You are a helpful assistant."},
    #     {"role": "user", "content": "Who won the world series in 2020?"},
    #     {"role": "assistant", "content": "The Los Angeles Dodgers won the World Series in 2020."},
    #     {"role": "user", "content": "Where was it played?"}
    # ]
    # if we don't get the history for the chat, then we create the list which append with the prompt
    if messages is None:
        messages = []
    messages.append({"role": "user", "content": prompt})
    print("openAI sending request", prompt)
    response = requests.post(
        'https://api.openai.com/v1/chat/completions',
        headers={'Authorization': f'Bearer {API_KEY}'},
        json={'model': MODEL, 'messages': messages,
              'temperature': 0.8, 'max_tokens': max_tokens},
        timeout=30
    )
    response.raise_for_status()  # Raises an exception for non-2xx status codes
    result = response.json()
    final_result = ''
    for i in range(0, len(result['choices'])):
        final_result += result['choices'][i]['message']['content']
    return final_result


async def add_private_message_to_db(chat_id, text, role, subscription_status):
    # Here, we'll store the message in the SQLite database
    timestamp = int(time.time())
    subscription_status = 1 if subscription_status else 0
    cursor.execute("INSERT INTO messages (timestamp, chat_id, role, message, subscription_status) "
                   "VALUES (?, ?, ?, ?, ?)",
                   (timestamp, chat_id, role, text, subscription_status))
    conn.commit()


async def get_last_messages(chat_id, amount):
    # Retrieve the last messages from the database
    cursor.execute(f"SELECT chat_id, role, message FROM messages WHERE chat_id = ? AND CLEARED = 0 "
                   f"ORDER BY timestamp DESC LIMIT {amount}", (chat_id,))
    rows = cursor.fetchall()
    reversed_rows = reversed(rows)  # Reverse the order of the rows
    messages = []
    for row in reversed_rows:
        chat_id, role, message = row
        # print(f"Chat ID: {chat_id}, Role: {role}, Message: {message}")
        messages.append({'role': role, 'content': message})
    return messages


async def check_message_limit(chat_id, limit, subscription_status):
    subscription_status = 1 if subscription_status else 0
    # Get the timestamp for the start of the current calendar day
    start_of_day = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    start_of_day_timestamp = start_of_day.timestamp()
    # Retrieve the message count for the current chat_id from the database
    cursor.execute('SELECT COUNT(*) FROM messages WHERE chat_id = ? AND role = ? AND subscription_status = ? '
                   'AND timestamp > ?',
                   (chat_id, 'user', subscription_status, start_of_day_timestamp))
    message_count = cursor.fetchone()[0]
    if message_count > limit:
        message_count = limit
    # get the bonus free messages if exist
    cursor_pay.execute("SELECT bonus_count FROM subscriptions WHERE chat_id = ?", (chat_id,))
    free_message_count = cursor_pay.fetchone()[0]

    # print(f"Today {chat_id} had {message_count} messages")
    # Check if the message limit has been reached
    limit_messages_left = limit - message_count
    if limit_messages_left <= 0:
        limit_messages_left = 0

    if message_count >= limit:
        if free_message_count <= 0:
            return False, limit_messages_left, free_message_count  # Message limit reached, return False
        else:
            return True, limit_messages_left, free_message_count
    return True, limit_messages_left, free_message_count  # Message within limit, return True


async def handle_clear_command(chat_id):
    # Update the messages associated with the specified chat_id so they are "cleared"
    # cursor.execute('UPDATE messages SET message = "<Cleared>" WHERE chat_id = ?', (chat_id,))
    cursor.execute('UPDATE messages SET cleared = 1 WHERE chat_id = ?', (chat_id,))
    conn.commit()


@retry(attempts=3)
async def subcribe_channel(chat_id):
    message = f'''
Кажется, вы еще не подписались на наш книжный канал 'Библионариум'

Здесь мы делимся литературными мыслями и предлагаем качественную литературу 💻

📲 Чтобы продолжить использование бота, просто подпишитесь на канал! 👌🏼
'''
    # change to NOT after the test
    try:
        x = await telegram_send_text_with_button(message, chat_id, 'Библионариум', CHANNEL_NAME)
    except requests.exceptions.RequestException as e:
        print('Couldnt send the message with button', e)


async def handle_info_command(chat_id, validity, messages_left, free_messages_left):
    subscription_status = 'Активна' if validity else 'Не активна'
    # Get the current date and time
    current_datetime = datetime.now()
    # Increment the current date by 1 day to get the next day
    next_day = current_datetime + timedelta(days=1)
    # Set the time to 00:00:00 for the next day
    next_day_start = next_day.replace(hour=0, minute=0, second=0, microsecond=0)
    # Calculate the time difference between the current datetime and the next day's start
    time_left = next_day_start - current_datetime
    # Extract the number of hours and minutes from the time difference
    hours_left = time_left.seconds // 3600
    minutes_left = (time_left.seconds % 3600) // 60

    if messages_left < 0:
        messages_left = 0

    if validity:
        conn_pay = sqlite3.connect(SUBSCRIPTION_DATABASE)
        cursor_pay = conn_pay.cursor()
        # Retrieve the expiration date for the user
        cursor_pay.execute("SELECT expiration_date FROM subscriptions WHERE chat_id = ?", (chat_id,))
        result = cursor_pay.fetchone()[0]
        expiration_date = datetime.strptime(result, '%Y-%m-%d').strftime('%d-%m-%Y')
        message = f'''
⚡️Статус вашей подписки: {subscription_status} до {expiration_date}.

🔄 У вас осталось ежедневных сообщений: {messages_left}. Лимит обновится через : {hours_left} ч. {minutes_left} мин.

Также у вас есть бонусные сообщения: {free_messages_left}.                  
    '''
    else:
        message = f'''
⚡️Статус вашей подписки: {subscription_status}

🔄 У вас осталось ежедневных сообщений: {messages_left}. Лимит обновится через : {hours_left} ч. {minutes_left} мин.

Также у вас есть бонусные сообщения: {free_messages_left}.              

🚀 Нужно больше?      

Оформите подписку и откройте новые возможности чат-бота с увеличенными лимитами.

Также вы можете отправить другу ссылку на бота, используйте команду /refer. Когда друг начнёт пользоваться ботом, вы получите {REFERRAL_BONUS} бонусных сообщений! 

'''
    try:
        x = await telegram_bot_sendtext(message, chat_id, None)
    except requests.exceptions.RequestException as e:
        print('Coulndt send the info message', e)


async def handle_start_command(chat_id, name):
    message = f'''{name}, приветствую!

⚡️Я бот, работающий на ChatGPT 3.5.turbo

Я умею:

1. Писать и редактировать тексты
2. Писать и редактировать код
3. Переводить с и на разные языки
4. Обобщать информацию
5. Поддерживать беседу и запоминать контекст

Моя экспертность - в сфере литературы, этот функционал сейчас в разработке.

Просто напишитет мне, что вы хотите узнать, сделать или отредактировать.

В бесплатном режиме вам доступно {DAY_LIMIT_PRIVATE} сообщений в сутки. С подпиской лимит увеличивается до {DAY_LIMIT_SUBSCRIPTION}.

Если друг начнёт пользоваться ботом по реферальной ссылке, вы получите {REFERRAL_BONUS} бонусных сообщений.

Стоимость подписки - {MONTH_SUBSCRIPTION_PRICE}р в месяц.

🔄 Вы можете сбросить беседу, чтобы я не подтягивал из памяти ненужную информацию, для этого есть команда
/clear.

❕ Если я вам не отвечаю, перезапустите меня командой /start

Спасибо! '''
    try:
        x = await telegram_bot_sendtext(message, chat_id, None)
    except requests.exceptions.RequestException as e:
        print('Coulndt send the welcome message', e)


# @retry(attempts=3)
async def handle_pay_command(chat_id):
    # Set up the payment request
    # данные тестовой карты: 1111 1111 1111 1026, 12/22, CVC 000.
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendInvoice"
    prices = json.dumps([{"label": "Month subscription", "amount": MONTH_SUBSCRIPTION_PRICE * 100}])
    provider_data = json.dumps({
            "receipt": {
                "items": [
                    {
                        "description": "Месячная подписка на Biblionarium GPT Bot",
                        "quantity": "1",
                        "amount": {
                            "value": "100.00",
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
    payload = {
        "chat_id": chat_id,
        "title": "Месячная подписка",
        "description": description,
        "payload": "Month_subscription",
        "need_email": True,
        "send_email_to_provider": True,
        "provider_token": PAY_TOKEN_TEST,
        "provider_data": provider_data,
        "start_parameter": "The-Payment",
        "currency": "RUB",
        "prices": [{"label": "Month subscription", "amount": "10000"}]
    }
    # Send the payment request
    # print(payload)
    response = requests.post(url, json=payload)
    # print(response)
    response.raise_for_status()


# 2b. Function that gets an Image from OpenAI
# async def openAImage(prompt):
#     # Make the request to the OpenAI API
#     resp = requests.post(
#         'https://api.openai.com/v1/images/generations',
#         headers={'Authorization': f'Bearer {API_KEY}'},
#         json={'prompt': prompt, 'n': 1, 'size': '256x256'}
#     )
#     response_text = json.loads(resp.text)
#     # print(response_text['data'][0]['url'])
#     return response_text['data'][0]['url']


async def handle_refer_command(chat_id):
    # Get a referral link from the database
    conn_pay = sqlite3.connect(SUBSCRIPTION_DATABASE)
    cursor_pay = conn_pay.cursor()
    cursor_pay.execute("SELECT referral_link FROM subscriptions WHERE chat_id = ?", (chat_id,))
    result = cursor_pay.fetchone()[0]
    print('The referral link is', result)

    message = f'''
⚡ Ссылка на присоединение к боту: {result}.

🔄 Отправьте это сообщение другу.
        '''
    try:
        x = await telegram_bot_sendtext(message, chat_id, None)
    except requests.exceptions.RequestException as e:
        print('Coulndt send the info message', e)


@retry(attempts=3, delay=3)
async def edit_bot_message(text, chat_id, message_id ):
    url = f'https://api.telegram.org/bot{BOT_TOKEN}/editMessageText'
    payload = {
        'chat_id': chat_id,
        'message_id': message_id,
        'text': text
    }
    response = requests.post(url, json=payload, timeout=20)
    response.raise_for_status()
    print("Edited the message in TG", response)
    return response.json()


@retry(attempts=3)
async def set_typing_status(chat_id):
    url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendChatAction'
    payload = {
        'chat_id': chat_id,
        'action': 'typing'
    }
    response = requests.post(url, json=payload)
    response.raise_for_status()


@retry(attempts=3)
async def handle_pre_checkout_query(update):
    pre_checkout_query_id = update['pre_checkout_query']['id']
    invoice_payload = update['pre_checkout_query']['invoice_payload']
    currency = update['pre_checkout_query']['currency']
    total_amount = int(update['pre_checkout_query']['total_amount']) / 100
    user_id = update['pre_checkout_query']['from']['id']
    # Confirm the payment
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/answerPreCheckoutQuery"
    payload = {
        "pre_checkout_query_id": pre_checkout_query_id,
        "ok": True
    }
    response = requests.post(url, json=payload)
    response.raise_for_status()
    print(f'The id {user_id} is going to pay {total_amount} in {currency} for {invoice_payload}')


@retry(attempts=3)
async def handle_successful_payment(update):
    amount = str(int(update['successful_payment']['total_amount']) / 100)
    receipt_message = f"Спасибо за оплату!\n"\
                      f"Товар: {update['successful_payment']['invoice_payload']}\n"\
                      f"Сумма: {amount}\n"\
                      f"Валюта: {update['successful_payment']['currency']}\n"

    chat_id = update['chat']['id']
    try:
        x = await telegram_bot_sendtext(receipt_message, chat_id, None)
    except requests.exceptions.RequestException as e:
        print('Couldnt send the successfull payment message')

    # get the current status of the user
    conn_pay = sqlite3.connect(SUBSCRIPTION_DATABASE)
    cursor_pay = conn_pay.cursor()
    cursor_pay.execute("SELECT subscription_status, start_date, expiration_date FROM subscriptions WHERE chat_id = ?",
                       (chat_id,))
    result = cursor_pay.fetchone()
    current_subscription_status, current_start_date, current_expiration_date = result
    # if the user doesn't have any subscription
    if current_subscription_status == 0:
        subscription_start_date = datetime.now()
        subscription_expiration_date = subscription_start_date + timedelta(days=31)
    else:
        # if the user already has a subscription we copy the start date
        subscription_start_date = datetime.strptime(current_start_date, '%Y-%m-%d')
        subscription_expiration_date = datetime.strptime(current_expiration_date, '%Y-%m-%d') + timedelta(days=31)

    update_subscription_status(chat_id, 1, subscription_start_date.strftime('%Y-%m-%d'),
                               subscription_expiration_date.strftime('%Y-%m-%d'))


@retry(attempts=3, delay=3)
async def get_updates(last_update):
    # Check for new messages in Telegram group
    # let's test if it works with offset +1
    last_update = str(int(last_update)+1)
    url = f'https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={last_update}'
    response = requests.get(url, timeout=20)
    response.raise_for_status()
    data = json.loads(response.content)
    # provide all messages instead of one in update
    # result = data['result'][len(data['result'])-1]
    result = data['result']
    if data['result']:
        print(data['result'])
        print(len(data['result']), "messages")
    return result


async def parse_updates(result, last_update):
    if float(result['update_id']) > float(last_update):
        # handle the pre_check_out
        try:
            if result['pre_checkout_query']:
                try:
                    await handle_pre_checkout_query(result)
                    print('Successful checkout')
                    last_update = str(int(result['update_id']))
                except requests.exceptions.RequestException as e:
                    print('Couldnt handle the pre checkout')
                    last_update = str(int(result['update_id']))
                    try:
                        x = telegram_bot_sendtext('Не удалось провести оплату. Пожалуйста, попробуйте ещё раз!',
                                                  result['pre_checkout_query']['from']['id'])
                    except requests.exceptions.RequestException as e:
                        print('Couldnt send the Try pre_checkout again message', e)
                return last_update
        except Exception as e:
            pass

        try:
            if result['channel_post']:
                channel = result['channel_post']['sender_chat']['title']
                print(f'We have got a channel post in {channel}')
                last_update = str(int(result['update_id']))
                return last_update
        except Exception as e:
            pass

        # Checking for new messages that did not come from chatGPT
        if not result['message']['from']['is_bot']:
            # remember the last update number
            last_update = str(int(result['update_id']))
            chat_type = str(result['message']['chat']['type'])
            # check if it's a group
            if chat_type == 'supergroup':
                await handle_supergroup(result)
            # check if it's a private chat
            if chat_type == 'private':
                await handle_private(result)
            if chat_type == "channel":
                pass
    return last_update


async def handle_supergroup(result):
    print('SuperDooper')
    # Give your bot a personality using adjectives from the tone list
    bot_personality = ''
    tone_list = ['Friendly', 'Professional', 'Humorous', 'Sarcastic', 'Witty', 'Sassy', 'Charming', 'Cheeky', 'Quirky',
                 'Laid-back', 'Elegant', 'Playful', 'Soothing', 'Intense', 'Passionate']
    # Leave write_history BLANK
    write_history = ''
    chat_id = str(result['message']['chat']['id'])
    if chat_id in ALLOWED_GROUP_ID:
        msg_id = str(int(result['message']['message_id']))
        # print('In allowed group ID')
        try:
            # Greeting message for new participants
            if 'new_chat_participant' in result['message']:
                prompt = 'Напиши в дружелюбном тоне  ' + \
                         "Приветствую! Буду рад помочь вам, " + \
                         result['message']['new_chat_participant']['first_name']
                # random.choice(tone_list) + ' tone: ' + \

                bot_response = await openAI(prompt, 200, None)
                # Sending back response to telegram group
                try:
                    x = await telegram_bot_sendtext(bot_response, chat_id, msg_id)
                except requests.exceptions.RequestException as e:
                    print('Error in sending text to TG', e)
                name = result['message']['new_chat_participant']['first_name']
                try:
                    x = await telegram_bot_sendtext(f'Новый пользователь - {name}', '163905035', None)
                except requests.exceptions.RequestException as e:
                    print('Error in sending text to TG', e)
        except Exception as e:
            print("Error in greeting", e)

        # try:
        #     if '/img' in result['message']['text']:
        #         prompt = result['message']['text'].replace("/img", "")
        #         bot_response = await openAImage(prompt)
        #         x = await telegram_bot_sendimage(bot_response, chat_id, msg_id)
        # except Exception as e:
        #     print(e)

        boolean_active = False
        # Checking that user mentionned chatbot's username in message
        if CHATBOT_HANDLE in result['message']['text']:
            prompt = result['message']['text'].replace(CHATBOT_HANDLE, "")
            boolean_active = True
            print('Got the Message, master!')

        # Verifying that the user is responding to the ChatGPT bot
        if 'reply_to_message' in result['message']:
            if result['message']['reply_to_message']['from']['username'] == CHATBOT_HANDLE[1:]:
                prompt = result['message']['text']
                # Getting historical messages from user
                write_history = await memory.get_channel_messages(chat_id, msg_id)
                boolean_active = True

        if boolean_active:
            try:
                prompt1 = await checkTone(prompt)
                prompt = prompt1[0]
                bot_personality = prompt1[1]
                boolean_active = True
            except Exception as e:
                print("Error at await checkTone", e)
            try:
                if write_history != '':
                    prompt = write_history + "\n\nQ : " + prompt + "\n\n###\n\n"

                try:
                    bot_response = await openAI(f"{bot_personality}{prompt}", 400, None)
                except requests.exceptions.RequestException as e:
                    print("Error while waiting for the answer from OpenAI", e)
                #
                # if bot_response == '':
                #     bot_response = await openAI(f"{bot_personality}{vague_prompt}", 400, None)
                try:
                    x = await telegram_bot_sendtext(bot_response, chat_id, msg_id)
                except requests.exceptions.RequestException as e:
                    print('Error in sending text to TG', e)

                # x = await telegram_bot_sendtext('I just sent some message', '163905035', None)

            except Exception as e:
                print("Error while waiting for the answer from OpenAI", e)
                try:
                    x = await telegram_bot_sendtext("Ответ от центрального мозга потерялся в дороге",
                                                    chat_id, msg_id)
                except requests.exceptions.RequestException as e:
                    print('Error in sending text to TG', e)
                try:
                    x = await telegram_bot_sendtext(f"OpenAI не ответил вовремя - {e}", '163905035', None)
                except requests.exceptions.RequestException as e:
                    print('Error in sending text to TG', e)

        if ASK_COMMAND in result['message']['text']:
            prompt = result['message']['text'].replace(ASK_COMMAND, "")
            asked = True
            print('Got the /ask command, master!')
            try:
                answer = research.reply(file, prompt)
                try:
                    x = await telegram_bot_sendtext(answer, chat_id, msg_id)
                except requests.exceptions.RequestException as e:
                    print('Error in sending text to TG', e)
            except Exception as e:
                print("Error while waiting for the answer with from OpenAI for the /ask", e)
                try:
                    x = await telegram_bot_sendtext("Этот книжный вопрос поломал логику",
                                                    chat_id, msg_id)
                except requests.exceptions.RequestException as e:
                    print('Error in sending text to TG', e)
                try:
                    x = await telegram_bot_sendtext(f"OpenAI не ответил вовремя на /ask - {e}",
                                                    '163905035', None)
                except requests.exceptions.RequestException as e:
                    print('Error in sending text to TG', e)

            except Exception as e:
                print("Couldn't handle the /ask command", e)


async def handle_private(result):
    # handle the successful payment
    try:
        if result['message']['successful_payment']:
            try:
                await handle_successful_payment(result['message'])
                print('Successful payment')
                # last_update = str(int(result['update_id']))
            except requests.exceptions.RequestException as e:
                print('Couldnt handle the payment')
                # last_update = str(int(result['update_id']))
                try:
                    x = telegram_bot_sendtext('Не удалось завершить оплату. Пожалуйста, попробуйте ещё раз!',
                                              result['pre_checkout_query']['from']['id'])
                except requests.exceptions.RequestException as e:
                    print('Couldnt send the Try payment again message', e)
            return
    except Exception as e:
        pass

    chat_id = str(result['message']['chat']['id'])
    msg_id = str(int(result['message']['message_id']))
    msg = result['message']['text']

    if not user_exists(chat_id):
        add_new_user(chat_id)

    if START_COMMAND in msg:
        try:
            await handle_start_command(chat_id, result['message']['from']['first_name'])
            # check if the new user came with referral link and get the number of referree
            if msg.startswith('/start '):
                referree = msg.strip('/start ')
                print('We have got a referring user', referree)
                bonus_from_refer = await add_reffered_by(chat_id, referree)
                if bonus_from_refer:
                    add_referral_bonus(referree, REFERRAL_BONUS)
                return
            return
        except Exception as e:
            print("Couldn't handle the /start command", e)
            try:
                x = await telegram_bot_sendtext("Извините, не смог стартовать",
                                                chat_id, msg_id)
            except requests.exceptions.RequestException as e:
                print('Error in sending text to TG', e)
            try:
                x = await telegram_bot_sendtext(f"Не смог стартовать у {chat_id} - {e}",
                                                '163905035', None)
            except requests.exceptions.RequestException as e:
                print('Error in sending text to TG', e)
            return

    if CLEAR_COMMAND in msg:
        try:
            await handle_clear_command(chat_id)
            try:
                x = await telegram_bot_sendtext("Диалог сброшен",
                                                chat_id, msg_id)
            except requests.exceptions.RequestException as e:
                print('Error in sending text to TG', e)
            return
        except Exception as e:
            print("Couldn't handle the /clear command", e)
            try:
                x = await telegram_bot_sendtext("Извините, не смог очистить диалог",
                                                chat_id, msg_id)
            except requests.exceptions.RequestException as e:
                print('Error in sending text to TG', e)
            try:
                x = await telegram_bot_sendtext(f"Не смог очистить диалог у {chat_id} - {e}",
                                                '163905035', None)
            except requests.exceptions.RequestException as e:
                print('Error in sending text to TG', e)
            return

    if SUBSCRIPTION_COMMAND in msg:
        print('We have got a payment request')
        try:
            await handle_pay_command(chat_id)
        except Exception as e:
            print('Couldnt handle the pay command', e)
        return

    if REFERRAL_COMMAND in msg:
        await handle_refer_command(chat_id)
        return

    is_subscription_valid = check_subscription_validity(chat_id)
    if is_subscription_valid:
        limit = DAY_LIMIT_SUBSCRIPTION
    else:
        limit = DAY_LIMIT_PRIVATE

    validity, messages_left, free_messages_left = await check_message_limit(chat_id, limit, is_subscription_valid)
    print(f"Subscription for {chat_id} is valid: {is_subscription_valid}, messages left {messages_left}, "
          f"bonus messages left {free_messages_left}")

    if INFO_COMMAND in msg:
        try:
            await handle_info_command(chat_id, is_subscription_valid, messages_left, free_messages_left)
            return
        except Exception as e:
            print("Couldn't handle the /info command", e)
            try:
                x = await telegram_bot_sendtext("Извините, не смог выдать информацию",
                                                chat_id, msg_id)
            except requests.exceptions.RequestException as e1:
                print('Error in sending text to TG', e1)
            try:
                x = await telegram_bot_sendtext(f"Не смог проинформировать у {chat_id} - {e}",
                                                '163905035', None)
            except requests.exceptions.RequestException as e:
                print('Error in sending text to TG', e)
            return

    try:
        channel_subscribed = await user_subscribed(chat_id, CHANNEL_NAME)
    except requests.exceptions.RequestException as e:
        print('Couldnt check the channel subscription')

    if channel_subscribed:
        print(f'{chat_id} is subscribed on channel {CHANNEL_NAME}')
    else:
        print(f'{chat_id} is NOT subscribed on channel {CHANNEL_NAME}')

    if channel_subscribed or is_subscription_valid:
        if validity:
            if messages_left <= 0:
                print('Need to decrease the free messages')
                decrease_free_messages(chat_id)
            # get the last n messages from the db to feed them to the gpt
            messages = await get_last_messages(chat_id, CONTEXT_DEPTH)
            print(messages)
            # add the last received message to the db
            await add_private_message_to_db(chat_id, msg, 'user', is_subscription_valid)
            # send the last message and the previous historical messages from the db to the GPT
            prompt = msg

            # send the quick message to the user, which shows that we start thinking
            try:
                x = await telegram_bot_sendtext("⏳ Ожидайте ответа от бота...", chat_id, msg_id)
                # Extract the message_id from the response
                sent_msg_id = x['result']['message_id']
            except requests.exceptions.RequestException as e:
                print('Error in sending "Wait for the answer" text to TG', e)
            # set the typing status
            try:
                await set_typing_status(chat_id)
            except requests.exceptions.RequestException as e:
                print('Couldnt set the typing status', e)

            try:
                bot_response = await openAI(f"{prompt}", MAX_TOKENS, messages)
                await add_private_message_to_db(chat_id, bot_response, 'assistant', is_subscription_valid)
            except requests.exceptions.RequestException as e:
                print("Error while waiting for the answer from OpenAI", e)
                try:
                    x = await edit_bot_message("Кажется, что-то случилось... Пожалуйста, отправьте запрос повторно",
                                               chat_id, msg_id)
                    return
                except requests.exceptions.RequestException as e:
                    print('Couldnt send the message "smth happend, try later"')
            try:
                # x = await telegram_bot_sendtext(bot_response, chat_id, msg_id)
                # edit the previously sent message "Wait for the answer"
                x = await edit_bot_message(bot_response,chat_id, sent_msg_id)
            except requests.exceptions.RequestException as e:
                print('Error in editing message', e)
        else:
            print(f'For {chat_id} the day limit is reached')
            try:
                x = await telegram_bot_sendtext("У вас закончился лимит сообщений на день.\n"
                                                "Чтобы увеличить лимит, оплатите подписку или воспользуйтесь "
                                                "реферальной ссылкой", chat_id, msg_id)
            except requests.exceptions.RequestException as e:
                print('Error in sending "The limit is reached" text to TG', e)
    else:
        await subcribe_channel(chat_id)


# Sending a message to a specific telegram group
@retry(attempts=3, delay=3)
async def telegram_bot_sendtext(bot_message, chat_id, msg_id):
    data = {
        'chat_id': chat_id,
        'text': bot_message,
        'reply_to_message_id': msg_id
    }
    print("TG sending the text", data)
    response = None
    response = requests.post(
        'https://api.telegram.org/bot' + BOT_TOKEN + '/sendMessage',
        json=data, timeout=10
    )
    response.raise_for_status()  # Raises an exception for non-2xx status codes
    print("TG sent the data", response)
    return response.json()


@retry(attempts=3, delay=5)
async def telegram_send_text_with_button(message_text, chat_id, button_text, channel_username):
    api_url = f'https://api.telegram.org/bot{BOT_TOKEN}/sendMessage'
    # Create the inline keyboard button
    keyboard = {
        'inline_keyboard': [[
            {'text': button_text, 'url': f't.me/{channel_username}'}  # Button with link to the channel
        ]]
    }
    # Convert the keyboard dictionary to JSON string
    reply_markup = json.dumps(keyboard)
    # Set the parameters for the API request
    params = {
        'chat_id': chat_id,
        'text': message_text,
        'reply_markup': reply_markup
    }
    # Send the API request
    response = requests.post(api_url, params=params)
    response.raise_for_status()

# Sending a image to a specific telegram group
# async def telegram_bot_sendimage(image_url, group_id, msg_id):
#     data = {'chat_id': group_id, 'photo': image_url, 'reply_to_message_id': msg_id}
#     url = 'https://api.telegram.org/bot' + BOT_TOKEN + '/sendPhoto'
#
#     response = requests.post(url, data=data)
#     return response.json()


# Checking for specific tone for message
async def checkTone(user_message):
    bot_personality = ''
    match = re.search(r"/setTone\((.*?)\)", user_message, flags=re.IGNORECASE)
    if match:
        substring = match.group(1)
        bot_personality = 'Answer in a ' + substring + ' tone, '
        user_message=user_message.replace('/setTone('+substring+')', '')
    return [user_message, bot_personality]


def user_exists(chat_id):
    # Establish a connection to the SQLite database
    conn_pay = sqlite3.connect(SUBSCRIPTION_DATABASE)
    cursor_pay = conn_pay.cursor()
    # Execute a query to retrieve the user by chat_id
    cursor_pay.execute('SELECT * FROM subscriptions WHERE chat_id = ?', (chat_id,))
    result = cursor_pay.fetchone()
    # Close the database connection
    # Check if the query result contains any rows (user found)
    if result:
        return True
    else:
        return False


def add_new_user(user_id):
    conn_pay = sqlite3.connect(SUBSCRIPTION_DATABASE)
    cursor_pay = conn_pay.cursor()
    revealed_date = datetime.now().strftime('%Y-%m-%d')
    referral_link = f'https://t.me/{BOT_NAME}?start={user_id}'

    # Add a new user with default subscription status, start date, and expiration date
    cursor_pay.execute("INSERT INTO subscriptions (chat_id, subscription_status, revealed_date, referral_link) "
                       "VALUES (?, 0, ?, ?)", (user_id, revealed_date, referral_link))
    conn_pay.commit()


async def add_reffered_by(chat_id, referree):
    conn_pay = sqlite3.connect(SUBSCRIPTION_DATABASE)
    cursor_pay = conn_pay.cursor()

    cursor_pay.execute("SELECT referred_by FROM subscriptions WHERE chat_id = ?", (chat_id,))
    result = cursor_pay.fetchone()[0]
    refer_exist = True if result else False
    print('The previous referral link is', result)
    if not refer_exist:
        # Add to a newly added user the referree id
        cursor_pay.execute("UPDATE subscriptions SET referred_by = ? WHERE chat_id = ?", (referree, chat_id))
        conn_pay.commit()
        try:
            x = await telegram_bot_sendtext(f'Поздравляем! Пользователь {chat_id} присоединился к боту {BOT_NAME} по '
                                      f'вашей реферальной ссылке', referree, None)
        except requests.exceptions.RequestException as e:
            print('Couldnt send the message to referree', e)
        return True
    else:
        print(f'The {chat_id} was already joined by a referral link')
        return False


def add_referral_bonus(referree, referral_bonus):
    conn_pay = sqlite3.connect('subscriptions.db')
    cursor_pay = conn_pay.cursor()
    # Execute the SQL query to increment the bonus count by 1
    cursor_pay.execute(f"UPDATE subscriptions SET bonus_count = bonus_count + {referral_bonus} WHERE chat_id = ?", (referree,))
    conn_pay.commit()

# Decrement the free messages count for the specified chat_id


def decrease_free_messages(chat_id):
    conn_pay = sqlite3.connect('subscriptions.db')
    cursor_pay = conn_pay.cursor()
    # Execute the SQL query to decrement the free messages count by 1
    cursor_pay.execute("UPDATE subscriptions SET bonus_count = bonus_count - 1 WHERE chat_id = ?",
                       (chat_id,))
    # Commit the changes to the database
    conn_pay.commit()


@retry(attempts=3)
async def user_subscribed(user_id, channel_name):
    # Получаем информацию о подписке пользователя на канал
    api_url = f'https://api.telegram.org/bot{BOT_TOKEN}/getChatMember'
    params = {'chat_id': '@'+channel_name, 'user_id': user_id}
    response = requests.get(api_url, params=params)
    response.raise_for_status()
    data = response.json()
    print(data)
    if response.status_code == 200 and data['ok']:
        # Check if the user is a member of the channel
        return data['result']['status'] == 'member' or data['result']['status'] == 'creator'
    else:
        # Failed to fetch the chat member information
        return False


def update_subscription_status(chat_id, subscription_status, start_date, expiration_date):
    conn_pay = sqlite3.connect(SUBSCRIPTION_DATABASE)
    cursor_pay = conn_pay.cursor()
    # Update the subscription status for the user
    cursor_pay.execute("UPDATE subscriptions SET subscription_status = ? WHERE chat_id = ?",
                       (subscription_status, chat_id))
    # Set the start and expiration dates for the user's subscription
    cursor_pay.execute("UPDATE subscriptions SET start_date = ?, expiration_date = ? WHERE chat_id = ?",
                       (start_date, expiration_date, chat_id))
    conn_pay.commit()


def check_subscription_validity(chat_id):
    conn_pay = sqlite3.connect(SUBSCRIPTION_DATABASE)
    cursor_pay = conn_pay.cursor()
    # Get the subscription status, start date, and expiration date for the user
    cursor_pay.execute("SELECT subscription_status, start_date, expiration_date FROM subscriptions WHERE chat_id = ?",
                       (chat_id,))
    result = cursor_pay.fetchone()
    if result is not None:
        subscription_status, start_date_text, expiration_date_text = result
        if subscription_status == 1:
            # the date has not yet expired
            start_date = datetime.strptime(start_date_text, '%Y-%m-%d')
            expiration_date = datetime.strptime(expiration_date_text, '%Y-%m-%d')
            # check if the subccription has ended
            if start_date <= datetime.now() <= expiration_date:
                return True
            # the date is expired, fill in the old dates but change the status
            else:
                update_subscription_status(chat_id, 0, start_date_text, expiration_date_text)
                return False
    return False


async def ChatGPTbot():
    with open(FILENAME) as f:
        last_update = f.read()
    f.close()

    # get updates for the bot
    try:
        result = await get_updates(last_update)
    except requests.exceptions.RequestException as e:
        print("Didn't get the update from TG", e)
        try:
            x = await telegram_bot_sendtext(f"Не смог получить апдейт от телеграма - {e}", '163905035', None)
        except requests.exceptions.RequestException as e:
            print('Error in sending text to TG', e)

    try:
        # Checking for new message and processing them
        for res in result:
            last_update = await parse_updates(res, last_update)
    except Exception as e:
        print("General error in ChatGPTbot", e)
        try:
            x = await telegram_bot_sendtext(f"Случилась общая ошибка в коде - {e}", '163905035', None)
        except requests.exceptions.RequestException as e:
            print('Error in sending text to TG', e)

    # Updating file with last update ID
    with open(FILENAME, 'w') as f:
        f.write(last_update)
    return "done"


async def main():
    while True:
        await ChatGPTbot()
        await asyncio.sleep(5)

loop = asyncio.get_event_loop()
loop.run_until_complete(main())

cursor.close()
conn.close()
cursor_pay.close()
conn_pay.close()

# TODO add the /help command

# TODO Make bot send postponed messages

# TODO Make GPT wrap what is supposed to be sent to user, like "Tell him that he has two days left"..

# TODO If the update number gets deleted...

# TODO Add referral bonus for payment

# TODO Add the mode when each day the bot sends a literature question via the ChatGPT

# TODO Fix the errors when a nontext message is received

# TODO Make several types of subscription

# TODO Add the system message as a role setting

# TODO Integration with fantlab - title, description and so on

# TODO Show the similars from Fantlab

# TODO Add recomendations and ask for like|dislike, then tune the model on the results

# TODO Integration with fantlab - title, description and so on

# TODO Show the similars from Fantlab

# TODO Add recomendations and ask for like|dislike, then tune the model on the results

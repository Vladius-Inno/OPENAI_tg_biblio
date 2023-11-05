# version 0.0.1, working on news

import requests, json, os, re, random, sys
import memory
import asyncio
import sqlite3
import time
from retrying_async import retry
from datetime import datetime, timedelta
import fantlab_nwe, database_work, handlers, research, telegram_int

if sys.stdout.encoding != 'utf-8':
    sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

# Set default encoding to UTF-8 for stderr
if sys.stderr.encoding != 'utf-8':
    sys.stderr = open(sys.stderr.fileno(), mode='w', encoding='utf-8', buffering=1)

# OpenAI secret Key
API_KEY = os.environ['API_KEY']
# Models: text-davinci-003,text-curie-001,text-babbage-001,text-ada-001
# MODEL = 'text-davinci-003'
# the news api key
API_NEWS_KEY = 'b4f73a45121643eb87fe1e1a2f39c3dd'
MODEL = 'gpt-3.5-turbo'
# Telegram secret access bot token
BOT_TOKEN = os.environ['BOT_TOKEN']
# Specify all group ID the bot can respond too
ALLOWED_GROUP_ID = os.environ['ALLOWED_GROUP_ID']
# Specify your Chat Bot handle
CHATBOT_HANDLE = os.environ['CHATBOT_HANDLE']
# The token for the payment provider
PAY_TOKEN = os.environ['PAY_TOKEN']
BOT_NAME = os.environ['BOT_NAME']
PAY_TOKEN_TEST = os.environ['PAY_TOKEN_TEST']

# Retrieve last ID message : Create an empty text file named chatgpt.txt, write 1 on the first line of
# the text file and save it, write the full path of your file below
FILENAME = 'chatgpt.txt'  # the update number is stored

ASK_COMMAND = '/ask'
CLEAR_COMMAND = '/clear'
START_COMMAND = '/start'
INFO_COMMAND = '/info'
REFERRAL_COMMAND = '/refer'
HELP_COMMAND = '/help'
RECOM_COMMAND = '/recom'
SUBSCRIPTION_COMMAND = '/pay'

SUBSCRIPTION_DATABASE = 'subscriptions.db'
MESSAGES_DATABASE = 'messages.db'
OPTIONS_DATABASE = 'options.db'

# SBER_TOKEN_TEST = "401643678:TEST:266f8c81-0fc1-46ac-b57f-64a5fcc97616"
# Номер карты	2200 0000 0000 0053
# Дата истечения срока действия	2024/12
# Проверочный код на обратной стороне	123

CHANNEL_NAME = 'Biblionarium'
CHANNEL_NAME_RUS = "Библионариум"

TEST = True

DAY_LIMIT_PRIVATE = 15  # base is 10
DAY_LIMIT_SUBSCRIPTION = 60
CONTEXT_DEPTH = 5 * 2  # twice the context, because we get the users and the bots messages, base would be 10 * 2
MAX_TOKENS = 800
REFERRAL_BONUS = 30  # free messages that are used after the limit is over, base is 30
MONTH_SUBSCRIPTION_PRICE = 170
file = 'ClockworkOrange.txt'  # the current book loaded file

CHECK_MARK = '✅ '
LITERATURE_EXPERT_ROLE = 'literature_expert'
LITERATURE_EXPERT_ROLE_RUS = 'Лит.эксперт 📖'
DEFAULT_ROLE = 'default_role'
DEFAULT_ROLE_RUS = 'Без роли ☝️'
ROLES = [DEFAULT_ROLE, LITERATURE_EXPERT_ROLE]
ROLES_RUS = [DEFAULT_ROLE_RUS, LITERATURE_EXPERT_ROLE_RUS]
ROLES_ZIP = {ROLES[i]: ROLES_RUS[i] for i in range(len(ROLES))}

# callbacks for Work actions
LIKE = 'LIKE'
DISLIKE = 'DISLIKE'
RATE = 'RATE'

CALLBACKS = [LIKE, DISLIKE, RATE]

LIT_PROMPT = '''
You are now in the Literature Expert mode. 
In this mode, you are expected to generate responses that demonstrate a deep understanding of literature, including its various genres, authors, literary techniques, and themes. 
Please provide detailed and insightful answers, drawing upon your knowledge of renowned literary works and their interpretations.
You are proficient in recommendations all literature. If you lack information from a user, you ask additional questions. 
Feel free to engage in discussions, offer analysis, provide book recommendations, or help clarify any literary queries. 

You obey the 4 rules:
1. Answer in Russian language only.
2. If you don't know the answer - you ask for more information from the user. If you still don't know - you say that you don't know the answer.
3. If you have to name the book title then you always provide the russian title and the english title of the book in parenthesis if it exists. 
4. if you are not sure about the recommendation - you don't provide it.
'''

# new connectors
connector = database_work.DatabaseConnector('fantlab')
cursor = connector.get_cursor()

# extractors for the database tables
mess_ext = database_work.MessagesInteractor(cursor, connector.connection, test=TEST)
opt_ext = database_work.OptionsInteractor(cursor, connector.connection, test=TEST)
subs_ext = database_work.SubscriptionsInteractor(cursor, connector.connection, test=TEST)

telegram = telegram_int.TelegramInt(BOT_TOKEN)
handler = handlers.Handler(mess_ext, opt_ext, subs_ext, telegram)

# Interactor with the fantlab database, main class for requests
fant_ext = database_work.FantInteractor(cursor, connector.connection)

# Initialize the Fantlab_api with the base URL
api_connect = fantlab_nwe.FantlabApi()
# Initialize DatabaseConnector with the Fantlabapiclient
service = fantlab_nwe.BookDatabase(api_connect)

RANDOM_BOOK_COMMAND = "*Случайная книга*"
RECOMMEND_COMMAND = "*Рекомендации*"
RECOMMENDATION_EXIT_COMMAND = "*Выйти*"
PREFERENCES_COMMAND = "*Предпочтения*"


async def handle_random_book(chat_id):
    work = service.get_random_work(image_on=True)
    await telegram.send_work(work, chat_id, set_keyboard_rate_work(work.id))
    await fant_ext.store_work(work)
    return work.id, chat_id


async def handle_recomendation(chat_id):
    pass


async def handle_recom_exit(chat_id):
    await telegram.send_text("Вышли из режима рекомендаций", chat_id, None, set_keyboard_roles(chat_id))


async def handle_preferences(chat_id):
    # print(f'Handling preferences for {chat_id}')
    pass


INLINE_COMMANDS = {RECOMMEND_COMMAND: handle_recomendation,
                   RECOMMENDATION_EXIT_COMMAND: handle_recom_exit,
                   PREFERENCES_COMMAND: handle_preferences,
                   RANDOM_BOOK_COMMAND: handle_random_book}


async def set_keyboard_roles(chat_id):
    # get the gpt_role
    gpt_role = await opt_ext.check_role(chat_id)
    role_position = ROLES.index(gpt_role)
    # print('role positions', role_position)
    role_array = [1 if x == role_position else 0 for x in range(len(ROLES))]
    # print('role array', role_array)
    keyboard_markup = {
        'keyboard':
            [
                [
                    {'text': CHECK_MARK * role_array[0] + DEFAULT_ROLE_RUS, 'callback_data': 'default_role'},
                    {'text': CHECK_MARK * role_array[1] + LITERATURE_EXPERT_ROLE_RUS,
                     'callback_data': 'literature_expert_role'}
                ]
            ],
        'resize_keyboard': True,  # Allow the keyboard to be resized
        'one_time_keyboard': True  # Requests clients to hide the keyboard as soon as it's been used
    }
    return keyboard_markup


def set_keyboard_rate_work(work_id):
    keyboard = {
        'inline_keyboard': [[
            {'text': "Like", 'callback_data': f'LIKE {work_id}'},  # Button with link to the channel
            {'text': "Dislike", 'callback_data': f'DISLIKE {work_id}'},
            {'text': "Rate", 'callback_data': f'RATE {work_id}'}
        ]]
    }
    return keyboard


# the markup for the button for the subscribe to channel
keyboard_subscribe = {
    'inline_keyboard': [[
        {'text': CHANNEL_NAME_RUS, 'url': f't.me/{CHANNEL_NAME}'}  # Button with link to the channel
    ]]
}

keyboard_recom_markup = {
    'keyboard': [
        [
            {'text': RANDOM_BOOK_COMMAND},
            {'text': RECOMMENDATION_EXIT_COMMAND},

            # {'text': RECOMMEND_COMMAND},
        ],
        [
            # {'text': RECOMMENDATION_EXIT_COMMAND},
            # {'text': PREFERENCES_COMMAND}
        ]
    ],
    'resize_keyboard': True,  # Allow the keyboard to be resized
    'one_time_keyboard': False  # Requests clients to hide the keyboard as soon as it's been used
}


async def setup_role(chat_id, role, silent=False):
    # Add a gpt_role into the database with options extractor
    await opt_ext.setup_role(chat_id, role)
    # cursor_opt.execute("UPDATE options SET gpt_role = ? WHERE chat_id = ?", (role, chat_id))
    # conn_opt.commit()
    print(f'Role {role} for {chat_id} is set')
    role_rus = ROLES_ZIP[role]
    if not silent:
        await telegram.send_text(f'Установлена роль: {role_rus}. \nИстория диалога очищена',
                                 chat_id, None, await set_keyboard_roles(chat_id))


# Make the request to the OpenAI API
@retry(attempts=3, delay=3)
async def openAI(prompt, max_tokens, messages, gpt_role):
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

    if gpt_role == LITERATURE_EXPERT_ROLE:
        messages.append({"role": "system", "content": LIT_PROMPT})

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
    # Here, we'll store the message in the database
    timestamp = int(time.time())
    subscription_status = 1 if subscription_status else 0
    await mess_ext.insert_message(chat_id, text, role, subscription_status, timestamp)


async def get_last_messages(chat_id, amount):
    # Retrieve the last messages from the database
    # cursor.execute(f"SELECT chat_id, role, message FROM messages WHERE chat_id = ? AND CLEARED = 0 "
    #                f"ORDER BY timestamp DESC LIMIT {amount}", (chat_id,))
    # rows = cursor.fetchall()
    rows = await mess_ext.get_last_messages(chat_id, amount)
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
    # cursor.execute('SELECT COUNT(*) FROM messages WHERE chat_id = ? AND role = ? AND subscription_status = ? '
    #                'AND timestamp > ?',
    #                (chat_id, 'user', subscription_status, start_of_day_timestamp))
    # message_count = cursor.fetchone()[0]
    message_count = await mess_ext.check_message_limit(chat_id, subscription_status, start_of_day_timestamp)
    if message_count > limit:
        message_count = limit
    # get the bonus free messages if exist
    # cursor_pay.execute("SELECT bonus_count FROM subscriptions WHERE chat_id = ?", (chat_id,))
    # free_message_count = cursor_pay.fetchone()[0]
    free_message_count = await subs_ext.get_free_messages(chat_id)

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


@retry(attempts=3)
async def subcribe_channel(chat_id):
    message = f'''
Кажется, вы еще не подписались на наш книжный канал 'Библионариум'

Здесь мы делимся литературными мыслями и предлагаем качественную литературу 💻

📲 Чтобы продолжить использование бота, просто подпишитесь на канал! 👌🏼
'''
    # change to NOT after the test
    # try:
    #     x = await telegram_bot_sendtext(message, chat_id, None, keyboard_subscribe)
    # except requests.exceptions.RequestException as e:
    #     print('Couldnt send the message with button', e)
    await telegram.send_text(message, chat_id, None, keyboard_subscribe)


# @retry(attempts=3)
async def handle_pay_command(chat_id):
    # Set up the payment request
    # данные тестовой карты: 1111 1111 1111 1026, 12/22, CVC 000.
    # url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendInvoice"
    prices = json.dumps([{"label": "Month subscription", "amount": MONTH_SUBSCRIPTION_PRICE * 100}])
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
        "provider_token": PAY_TOKEN_TEST,  # CHANGE FOR PRIMARY
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
    await telegram.handle_payment(payload)


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


async def handle_pre_checkout_query(update):
    pre_checkout_query_id = update['pre_checkout_query']['id']
    invoice_payload = update['pre_checkout_query']['invoice_payload']
    currency = update['pre_checkout_query']['currency']
    total_amount = int(update['pre_checkout_query']['total_amount']) / 100
    user_id = update['pre_checkout_query']['from']['id']
    # Confirm the payment
    # url = f"https://api.telegram.org/bot{BOT_TOKEN}/answerPreCheckoutQuery"
    # payload = {
    #     "pre_checkout_query_id": pre_checkout_query_id,
    #     "ok": True
    # }
    # response = requests.post(url, json=payload)
    # response.raise_for_status()
    await telegram.answer_pre_checkout(pre_checkout_query_id)
    print(f'The id {user_id} is going to pay {total_amount} in {currency} for {invoice_payload}')


@retry(attempts=3)
async def handle_successful_payment(update):
    amount = str(int(update['successful_payment']['total_amount']) / 100)
    receipt_message = f"Спасибо за оплату!\n" \
                      f"Товар: {update['successful_payment']['invoice_payload']}\n" \
                      f"Сумма: {amount}\n" \
                      f"Валюта: {update['successful_payment']['currency']}\n"

    chat_id = update['chat']['id']
    # try:
    #     x = await telegram_bot_sendtext(receipt_message, chat_id, None)
    # except requests.exceptions.RequestException as e:
    #     print('Couldnt send the successfull payment message')
    await telegram.send_text(receipt_message, chat_id)

    # # get the current status of the user
    # conn_pay = sqlite3.connect(SUBSCRIPTION_DATABASE)
    # cursor_pay = conn_pay.cursor()
    # cursor_pay.execute("SELECT subscription_status, start_date, expiration_date FROM subscriptions WHERE chat_id = ?",
    #                    (chat_id,))
    # result = cursor_pay.fetchone()
    # current_subscription_status, current_start_date, current_expiration_date = result
    current_subscription_status, current_start_date, current_expiration_date = await subs_ext.get_subscription(chat_id)

    # if the user doesn't have any subscription
    if current_subscription_status == 0:
        subscription_start_date = datetime.now()
        subscription_expiration_date = subscription_start_date + timedelta(days=31)
    else:
        # if the user already has a subscription we copy the start date
        subscription_start_date = datetime.strptime(current_start_date, '%Y-%m-%d')
        subscription_expiration_date = datetime.strptime(current_expiration_date, '%Y-%m-%d') + timedelta(days=31)

    await subs_ext.update_subscription_status(chat_id, 1, subscription_start_date.strftime('%Y-%m-%d'),
                                              subscription_expiration_date.strftime('%Y-%m-%d'))


async def parse_updates(result, last_update):
    if float(result['update_id']) > float(last_update):
        # handle the pre_check_out
        # TODO Drag to the payment lib
        try:
            if result['pre_checkout_query']:
                try:
                    await handle_pre_checkout_query(result)
                    print('Successful checkout')
                    last_update = str(int(result['update_id']))
                except requests.exceptions.RequestException as e:
                    print('Couldnt handle the pre checkout')
                    last_update = str(int(result['update_id']))
                    await telegram.send_text('Не удалось провести оплату. Пожалуйста, попробуйте ещё раз!',
                                             result['pre_checkout_query']['from']['id'])
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

        try:
            if result['edited_channel_post']:
                channel = result['edited_channel_post']['sender_chat']['title']
                print(f'We have got a update to a channel post in {channel}')
                last_update = str(int(result['update_id']))
                return last_update
        except Exception as e:
            pass

        try:
            if result['callback_query']:
                # print("HERE IN UPDATES")
                await handle_callback_query(result['callback_query'])
                last_update = str(int(result['update_id']))
                return last_update
        except Exception as e:
            print(e)

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
    prompt = ""
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
                # try:
                #     x = await telegram_bot_sendtext(bot_response, chat_id, msg_id)
                # except requests.exceptions.RequestException as e:
                #     print('Error in sending text to TG', e)
                await telegram.send_text(bot_response, chat_id, msg_id)
                name = result['message']['new_chat_participant']['first_name']
                # try:
                #     x = await telegram_bot_sendtext(f'Новый пользователь - {name}', '163905035', None)
                # except requests.exceptions.RequestException as e:
                #     print('Error in sending text to TG', e)
                await telegram.send_text(f'Новый пользователь - {name}', '163905035')
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
                    bot_response = "Empty"
                #
                # if bot_response == '':
                #     bot_response = await openAI(f"{bot_personality}{vague_prompt}", 400, None)
                # try:
                #     x = await telegram_bot_sendtext(bot_response, chat_id, msg_id)
                # except requests.exceptions.RequestException as e:
                #     print('Error in sending text to TG', e)
                await telegram.send_text(bot_response, chat_id, msg_id)

                # x = await telegram_bot_sendtext('I just sent some message', '163905035', None)

            except Exception as e:
                print("Error while waiting for the answer from OpenAI", e)
                # try:
                #     x = await telegram_bot_sendtext("Ответ от центрального мозга потерялся в дороге",
                #                                     chat_id, msg_id)
                # except requests.exceptions.RequestException as e:
                #     print('Error in sending text to TG', e)
                await telegram.send_text("Ответ от центрального мозга потерялся в дороге",
                                         chat_id, msg_id)
                # try:
                #     x = await telegram_bot_sendtext(f"OpenAI не ответил вовремя - {e}", '163905035', None)
                # except requests.exceptions.RequestException as e:
                #     print('Error in sending text to TG', e)
                await telegram.send_text(f"OpenAI не ответил вовремя - {e}", '163905035', None)

        if ASK_COMMAND in result['message']['text']:
            prompt = result['message']['text'].replace(ASK_COMMAND, "")
            asked = True
            print('Got the /ask command, master!')
            try:
                answer = research.reply(file, prompt)
                # try:
                #     x = await telegram_bot_sendtext(answer, chat_id, msg_id)
                # except requests.exceptions.RequestException as e:
                #     print('Error in sending text to TG', e)
                await telegram.send_text(answer, chat_id, msg_id)
            except Exception as e:
                print("Error while waiting for the answer with from OpenAI for the /ask", e)
                # try:
                #     x = await telegram_bot_sendtext("Этот книжный вопрос поломал логику",
                #                                     chat_id, msg_id)
                # except requests.exceptions.RequestException as e:
                #     print('Error in sending text to TG', e)
                await telegram.send_text("Этот книжный вопрос поломал логику",
                                         chat_id, msg_id)
                # try:
                #     x = await telegram_bot_sendtext(f"OpenAI не ответил вовремя на /ask - {e}",
                #                                     '163905035', None)
                # except requests.exceptions.RequestException as e:
                #     print('Error in sending text to TG', e)
                await telegram.send_text(f"OpenAI не ответил вовремя на /ask - {e}",
                                         '163905035', None)
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
                # try:
                #     x = telegram_bot_sendtext('Не удалось завершить оплату. Пожалуйста, попробуйте ещё раз!',
                #                               result['pre_checkout_query']['from']['id'])
                # except requests.exceptions.RequestException as e:
                #     print('Couldnt send the Try payment again message', e)
                await telegram.send_text('Не удалось завершить оплату. Пожалуйста, попробуйте ещё раз!',
                                         result['pre_checkout_query']['from']['id'])
            return
    except Exception as e:
        pass

    # try:
    #     if result['callback_query']:
    #         print('Got a callback')
    #         handle_callback_query(result['callback_query'])
    # except Exception as e:
    #     print(e)

    chat_id = str(result['message']['chat']['id'])
    msg_id = str(int(result['message']['message_id']))

    # check if we got the text, else skip
    if not 'text' in result.get('message'):
        print('Got the non-text message')
        # try:
        #     x = await telegram_bot_sendtext("Извините, пока что я умею обрабатывать только текст",
        #                                     chat_id, msg_id)
        # except requests.exceptions.RequestException as e:
        #     print('Error in sending text to TG', e)
        await telegram.send_text("Извините, пока что я умею обрабатывать только текст",
                                 chat_id, msg_id)
        return

    msg = result['message']['text']

    # a new user
    if not await subs_ext.user_exists(chat_id):
        await add_new_user(chat_id)

    # set options for a new user or in case of options failure
    if not await opt_ext.options_exist(chat_id):
        await opt_ext.set_user_option(chat_id)

    # Command detection starts
    if START_COMMAND in msg:
        try:
            # await handle_start_command(chat_id, result['message']['from']['first_name'])
            await setup_role(chat_id, DEFAULT_ROLE, silent=True)

            await handler.start_command(chat_id, result['message']['from']['first_name'], DAY_LIMIT_PRIVATE,
                                        DAY_LIMIT_SUBSCRIPTION, REFERRAL_BONUS, MONTH_SUBSCRIPTION_PRICE,
                                        await set_keyboard_roles(chat_id))

            # check if the new user came with referral link and get the number of referree
            if msg.startswith('/start '):
                referree = msg.strip('/start ')
                print('We have got a referring user', referree)
                bonus_from_refer = await add_reffered_by(chat_id, referree)
                if bonus_from_refer:
                    await subs_ext.add_referral_bonus(referree, REFERRAL_BONUS)
                return
            return
        except Exception as e:
            print("Couldn't handle the /start command", e)
            await telegram.send_text("Извините, не смог стартовать",
                                     chat_id, msg_id)
            await telegram.send_text(f"Не смог стартовать у {chat_id} - {e}",
                                     '163905035')
            return

    if CLEAR_COMMAND in msg:
        try:
            # await handle_clear_command(chat_id)
            await handler.handle_clear_command(chat_id)
            # try:
            #     x = await telegram_bot_sendtext("Диалог сброшен",
            #                                     chat_id, msg_id, set_keyboard(chat_id))
            # except requests.exceptions.RequestException as e:
            #     print('Error in sending text to TG', e)
            await telegram.send_text("Диалог сброшен",
                                     chat_id, msg_id, await set_keyboard_roles(chat_id))
            return
        except Exception as e:
            print("Couldn't handle the /clear command", e)
            await telegram.send_text("Извините, не смог очистить диалог",
                                     chat_id, msg_id)

    if SUBSCRIPTION_COMMAND in msg:
        print('We have got a payment request')
        try:
            await handle_pay_command(chat_id)
        except Exception as e:
            print('Couldnt handle the pay command', e)
        return

    if REFERRAL_COMMAND in msg:
        # await handle_refer_command(chat_id)
        await handler.refer_command(chat_id)
        return

    if HELP_COMMAND in msg:
        await handler.help_command(chat_id)
        return

    if RECOM_COMMAND in msg:
        await handler.handle_recom_command(chat_id, keyboard_recom_markup)
        return

    if LITERATURE_EXPERT_ROLE_RUS in msg:
        await setup_role(chat_id, LITERATURE_EXPERT_ROLE)
        # await handle_clear_command(chat_id)
        await handler.handle_clear_command(chat_id)
        return

    if DEFAULT_ROLE_RUS in msg:
        await setup_role(chat_id, DEFAULT_ROLE)
        # await handle_clear_command(chat_id)
        await handler.handle_clear_command(chat_id)
        return
    # Command detection ends for most commands

    # get the validity
    is_subscription_valid = await check_subscription_validity(chat_id)
    if is_subscription_valid:
        limit = DAY_LIMIT_SUBSCRIPTION
    else:
        limit = DAY_LIMIT_PRIVATE

    validity, messages_left, free_messages_left = await check_message_limit(chat_id, limit, is_subscription_valid)
    print(f"Subscription for {chat_id} is valid: {is_subscription_valid}, messages left {messages_left}, "
          f"bonus messages left {free_messages_left}")

    if INFO_COMMAND in msg:
        try:
            await handler.handle_info_command(chat_id, is_subscription_valid, messages_left, free_messages_left,
                                              REFERRAL_BONUS)
            return
        except Exception as e:
            print("Couldn't handle the /info command", e)
            await telegram.send_text("Извините, не смог выдать информацию",
                                     chat_id, msg_id)
            await telegram.send_text(f"Не смог проинформировать у {chat_id} - {e}",
                                     '163905035')
            return

    try:
        channel_subscribed = await telegram.user_subscribed(chat_id, CHANNEL_NAME)
    except requests.exceptions.RequestException as e:
        print('Couldnt check the channel subscription')
        channel_subscribed = False

    if channel_subscribed:
        print(f'{chat_id} is subscribed on channel {CHANNEL_NAME}')
    else:
        print(f'{chat_id} is NOT subscribed on channel {CHANNEL_NAME}')

    # from now on handle the message without the commands
    if channel_subscribed or is_subscription_valid:
        if validity:
            # handle inline commands
            inline_command = None
            # check if inline command in message
            for command in INLINE_COMMANDS.keys():
                if command == msg:
                    inline_command = command
            # run the correspomdent function handler
            if inline_command:
                # call the corresponding func
                await INLINE_COMMANDS[inline_command](chat_id)
                return

            if messages_left <= 0:
                print('Need to decrease the free messages')
                await subs_ext.decrease_free_messages(chat_id, 1)
            # get the last n messages from the db to feed them to the gpt
            messages = await get_last_messages(chat_id, CONTEXT_DEPTH)
            # print(messages)
            # add the last received message to the db
            await add_private_message_to_db(chat_id, msg, 'user', is_subscription_valid)
            # send the last message and the previous historical messages from the db to the GPT
            prompt = msg
            # send the quick message to the user, which shows that we start thinking
            x = await telegram.send_text("⏳ Ожидайте ответа от бота...", chat_id, msg_id)
            sent_msg_id = x['result']['message_id']

            # set the typing status
            try:
                await telegram.set_typing_status(chat_id)
            except requests.exceptions.RequestException as e:
                print('Couldnt set the typing status', e)
            gpt_role = await opt_ext.check_role(chat_id)
            try:
                bot_response = await openAI(f"{prompt}", MAX_TOKENS, messages, gpt_role)
                await add_private_message_to_db(chat_id, bot_response, 'assistant', is_subscription_valid)
            except requests.exceptions.RequestException as e:
                print("Error while waiting for the answer from OpenAI", e)
                bot_response = None
                await telegram.send_text("Кажется, что-то случилось... Пожалуйста, отправьте запрос повторно",
                                         chat_id, msg_id)
            try:
                # x = await telegram_bot_sendtext(bot_response, chat_id, msg_id)
                # edit the previously sent message "Wait for the answer"
                x = await telegram.edit_bot_message(bot_response, chat_id, sent_msg_id)
            except requests.exceptions.RequestException as e:
                print('Error in editing message', e)
        else:
            print(f'For {chat_id} the day limit is reached')
            await telegram.send_text("У вас закончился лимит сообщений на день.\n"
                                     "Чтобы увеличить лимит, оплатите подписку или воспользуйтесь "
                                     "реферальной ссылкой", chat_id, msg_id)
    else:
        await subcribe_channel(chat_id)


# Function to handle the callback query from recomednations
async def handle_callback_query(callback_query):
    callback_data = callback_query['data']
    # print('Callback is ', callback_data)
    chat_id = callback_query['message']['chat']['id']
    msg_id = callback_query['message']['message_id']

    if callback_data.split()[0] in CALLBACKS:
        print('Here comes the callback', callback_data)
        if callback_data.split()[0] == LIKE:
            await like(chat_id, callback_data.split()[1], msg_id)
        if callback_data.split()[0] == DISLIKE:
            dislike(chat_id, callback_data.split()[1])
        if callback_data.split()[0] == RATE:
            rate(chat_id, callback_data.split()[1])
        return True


async def like(chat_id, work_id, msg_id):
    print(chat_id, 'Likes', work_id)
    keyboard = {
        'inline_keyboard': [[
            {'text': "Unlike", 'callback_data': f'UNLIKE {work_id}'},
            {'text': "smth else", 'callback_data': f'SMTH {work_id}'}
        ]]
    }
    await telegram.edit_bot_message_markup(chat_id, msg_id, keyboard)


def dislike(chat_id, work_id):
    pass


def rate(chat_id, work_id):
    pass


# Checking for specific tone for message
async def checkTone(user_message):
    bot_personality = ''
    match = re.search(r"/setTone\((.*?)\)", user_message, flags=re.IGNORECASE)
    if match:
        substring = match.group(1)
        bot_personality = 'Answer in a ' + substring + ' tone, '
        user_message = user_message.replace('/setTone(' + substring + ')', '')
    return [user_message, bot_personality]


async def add_new_user(user_id):
    # conn_pay = sqlite3.connect(SUBSCRIPTION_DATABASE)
    # cursor_pay = conn_pay.cursor()
    revealed_date = datetime.now().strftime('%Y-%m-%d')
    referral_link = f'https://t.me/{BOT_NAME}?start={user_id}'

    # # Add a new user with default subscription status, start date, and expiration date
    # cursor_pay.execute("INSERT INTO subscriptions (chat_id, subscription_status, revealed_date, referral_link) "
    #                    "VALUES (?, 0, ?, ?)", (user_id, revealed_date, referral_link))
    # conn_pay.commit()
    await subs_ext.add_new_user(user_id, revealed_date, referral_link)

    # conn_opt = sqlite3.connect(OPTIONS_DATABASE)
    # cursor_opt = conn_opt.cursor()
    # role = DEFAULT_ROLE
    # # Add a new user default role
    # cursor_opt.execute("INSERT INTO options (chat_id, gpt_role) "
    #                    "VALUES (?, ?)", (user_id, role))
    # conn_opt.commit()


async def add_reffered_by(chat_id, referree):
    # conn_pay = sqlite3.connect(SUBSCRIPTION_DATABASE)
    # cursor_pay = conn_pay.cursor()
    #
    # cursor_pay.execute("SELECT referred_by FROM subscriptions WHERE chat_id = ?", (chat_id,))
    # result = cursor_pay.fetchone()[0]
    result = await subs_ext.referred_by(chat_id)
    refer_exist = True if result else False
    print('The previous referral link is', result)
    if not refer_exist:
        # Add to a newly added user the referree id
        # cursor_pay.execute("UPDATE subscriptions SET referred_by = ? WHERE chat_id = ?", (referree, chat_id))
        # conn_pay.commit()
        await subs_ext.add_referree(referree, chat_id)
        # try:
        #     x = await telegram_bot_sendtext(f'Поздравляем! Пользователь {chat_id} присоединился к боту {BOT_NAME} по '
        #                               f'вашей реферальной ссылке', referree, None)
        # except requests.exceptions.RequestException as e:
        #     print('Couldnt send the message to referree', e)
        await telegram.send_text(f'Поздравляем! Пользователь {chat_id} присоединился к боту {BOT_NAME} по '
                                 f'вашей реферальной ссылке', referree)
        return True
    else:
        print(f'The {chat_id} was already joined by a referral link')
        return False


async def check_subscription_validity(chat_id):
    # conn_pay = sqlite3.connect(SUBSCRIPTION_DATABASE)
    # cursor_pay = conn_pay.cursor()
    # # Get the subscription status, start date, and expiration date for the user
    # cursor_pay.execute("SELECT subscription_status, start_date, expiration_date FROM subscriptions WHERE chat_id = ?",
    #                    (chat_id,))
    # result = cursor_pay.fetchone()
    result = await subs_ext.get_subscription(chat_id)
    if result is not None:
        subscription_status, start_date_text, expiration_date_text = result
        if subscription_status == 1:
            # the date has not yet expired
            start_date = datetime.strptime(start_date_text, '%Y-%m-%d')
            expiration_date = datetime.strptime(expiration_date_text, '%Y-%m-%d')
            # check if the subscription has ended
            if start_date <= datetime.now() <= expiration_date:
                return True
            # the date is expired, fill in the old dates but change the status
            else:
                await subs_ext.update_subscription_status(chat_id, 0, start_date_text, expiration_date_text)
                return False
    return False


async def ChatGPTbot():
    with open(FILENAME) as f:
        last_update = f.read()
    f.close()
    # get updates for the bot
    try:
        result = await telegram.get_updates(last_update)
    except requests.exceptions.RequestException as e:
        print("Didn't get the update from TG", e)
        result = []
        await telegram.send_text(f"Не смог получить апдейт от телеграма - {e}", '163905035')
    try:
        # Checking for new message and processing them
        for res in result:
            last_update = await parse_updates(res, last_update)
    except Exception as e:
        print("General error in ChatGPTbot", e)
        await telegram.send_text(f"Случилась общая ошибка в коде - {e}", '163905035')
    # Updating file with last update ID
    with open(FILENAME, 'w') as f:
        f.write(last_update)
    return "done"


async def main():
    while True:
        try:
            await ChatGPTbot()
        except TypeError as e:
            print('Typeerror', e)
        try:
            await asyncio.sleep(5)
        except TypeError as e:
            print('The problem in sleep', e)


if __name__ == '__main__':
    # loop = asyncio.new_event_loop()
    # asyncio.set_event_loop(loop)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # cursor.close()
        # conn.close()
        # cursor_pay.close()
        # conn_pay.close()
        connector.close_connection()
        print('Finished')

# loop = asyncio.get_event_loop()
# loop.run_until_complete(main())

# cursor.close()
# conn.close()
# cursor_pay.close()
# conn_pay.close()

# TODO Make bot send postponed messages

# TODO Make GPT wrap what is supposed to be sent to user, like "Tell him that he has two days left"..

# TODO If the update number gets deleted...

# TODO Add referral bonus for payment

# TODO Add the mode when each day the bot sends a literature question via the ChatGPT

# TODO Make several types of subscription

# TODO Add the system message as a role setting

# TODO Integration with fantlab - title, description and so on

# TODO Show the similars from Fantlab

# TODO Add recomendations and ask for like|dislike, then tune the model on the results

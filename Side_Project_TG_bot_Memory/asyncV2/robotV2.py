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
import datetime


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
# Retrieve last ID message : Create an empty text file named chatgpt.txt, write 1 on the first line of
# the text file and save it, write the full path of your file below
FILENAME = 'chatgpt.txt'
ASK_COMMAND = '/ask'
CLEAR_COMMAND = '/clear'
DAY_LIMIT_PRIVATE = 5
file = '1ClockworkOrange.txt'

conn = sqlite3.connect('messages.db')
cursor = conn.cursor()

# Create a table to store messages
cursor.execute('''CREATE TABLE IF NOT EXISTS messages
                  (timestamp INTEGER, chat_id INTEGER, role TEXT, message TEXT, cleared INTEGER DEFAULT 0)''')
conn.commit()


# Make the request to
# the OpenAI API
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

    # TODO Add the system message as a role setting

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


async def add_private_message_to_db(chat_id, text, role):
    # Here, we'll store the message in the SQLite database
    timestamp = int(time.time())
    cursor.execute("INSERT INTO messages (timestamp, chat_id, role, message) VALUES (?, ?, ?, ?)",
                   (timestamp, chat_id, role, text))
    conn.commit()


async def get_last_messages(chat_id, amount):
    # Retrieve the last 5 messages from the database
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


async def check_message_limit(chat_id):
    # Get the current timestamp
    # current_time = time.time()

    # Get the timestamp for the start of the current calendar day
    start_of_day = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    start_of_day_timestamp = start_of_day.timestamp()

    # Retrieve the message count for the current chat_id from the database
    cursor.execute('SELECT COUNT(*) FROM messages WHERE chat_id = ? AND role = ? AND timestamp > ?',
                   (chat_id, 'user', start_of_day_timestamp))
    message_count = cursor.fetchone()[0]
    print(f"Today {chat_id} had {message_count} messages")
    # Check if the message limit has been reached
    if message_count >= DAY_LIMIT_PRIVATE:
        return False  # Message limit reached, return False

    return True  # Message within limit, return True


async def handle_clear_command(chat_id):
    # # Clear the message history for the specific user with the given chat_id
    # cursor.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
    # conn.commit()

    # Update the messages associated with the specified chat_id so they are "cleared"
    # cursor.execute('UPDATE messages SET message = "<Cleared>" WHERE chat_id = ?', (chat_id,))
    cursor.execute('UPDATE messages SET cleared = 1 WHERE chat_id = ?', (chat_id,))
    conn.commit()

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


@retry(attempts=3, delay=3)
async def edit_bot_message(text, chat_id, message_id ):
    url = f'https://api.telegram.org/bot{BOT_TOKEN}/editMessageText'
    payload = {
        'chat_id': chat_id,
        'message_id': message_id,
        'text': text
    }
    response = requests.post(url, json=payload)
    response.raise_for_status()
    print("Edited the message in TG", response)
    return response.json()


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
    print(data['result'])
    print(len(data['result']), "messages")
    return result


async def parse_updates(result, last_update):
    if float(result['update_id']) > float(last_update):
        # Checking for new messages that did not come from chatGPT
        print('got here')
        if not result['message']['from']['is_bot']:
            last_update = str(int(result['update_id']))
            chat_type = str(result['message']['chat']['type'])

            if chat_type == 'supergroup':
                await handle_supergroup(result)

            # check if it's a private chat and answer the same text
            if chat_type == 'private':
                await handle_private(result)
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
    chat_id = str(result['message']['chat']['id'])
    msg_id = str(int(result['message']['message_id']))
    msg = result['message']['text']

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

    if await check_message_limit(chat_id):
        # get the last n messages from the db to feed them to the gpt
        messages = await get_last_messages(chat_id, 6)
        print(messages)
        # add the last received message to the db
        await add_private_message_to_db(chat_id, msg, 'user')
        # send the last message and the previous historical messages from the db to the GPT
        prompt = msg

        # send the quick message to the user, which shows that we start thinking
        try:
            x = await telegram_bot_sendtext("Ожидайте ответа от бота...", chat_id, msg_id)
            # Extract the message_id from the response
            sent_msg_id = x['result']['message_id']
        except requests.exceptions.RequestException as e:
            print('Error in sending "Wait for the answer" text to TG', e)

        try:
            bot_response = await openAI(f"{prompt}", 400, messages)
            await add_private_message_to_db(chat_id, bot_response, 'assistant')
        except requests.exceptions.RequestException as e:
            print("Error while waiting for the answer from OpenAI", e)
            bot_response = "Случилось некоторое дерьмо"
            # TODO Добавить "Я всё ещё думаю" и попросить отправить запрос повторно
        try:
            # x = await telegram_bot_sendtext(bot_response, chat_id, msg_id)
            # edit the previously sent message "Wait for the answer"
            x = await edit_bot_message(bot_response,chat_id, sent_msg_id)
        except requests.exceptions.RequestException as e:
            print('Error in editing message', e)
        try:
            x = await telegram_bot_sendtext('I just sent some private message', '163905035', None)
        except requests.exceptions.RequestException as e:
            print('Error in sending text to TG', e)
    else:
        print(f'For {chat_id} the day limit is reached')
        try:
            x = await telegram_bot_sendtext("У вас закончился лимит сообщения на день", chat_id, msg_id)
        except requests.exceptions.RequestException as e:
            print('Error in sending "The limit is reached" text to TG', e)


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


# TODO add the /help command

# TODO Make bot send postponed messages

# TODO Make GPT wrap what is supposed to be sent to user, like "Tell him that he has two days left"..



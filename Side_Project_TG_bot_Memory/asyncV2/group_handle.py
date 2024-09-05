# -*- coding: utf-8 -*-

from constants import ALLOWED_GROUP_ID, CHATBOT_HANDLE, ASK_COMMAND, file
from OpenAI import openAI
import research
import requests
import memory
import re
import os
from dotenv import load_dotenv

load_dotenv()


# Checking for specific tone for message
async def checkTone(user_message):
    bot_personality = ''
    match = re.search(r"/setTone\((.*?)\)", user_message, flags=re.IGNORECASE)
    if match:
        substring = match.group(1)
        bot_personality = 'Answer in a ' + substring + ' tone, '
        user_message = user_message.replace('/setTone(' + substring + ')', '')
    return [user_message, bot_personality]


async def handle_supergroup(result, telegram):
    print('SuperDooper')
    # Give your bot a personality using adjectives from the tone list
    bot_personality = ''
    tone_list = ['Friendly', 'Professional', 'Humorous', 'Sarcastic', 'Witty', 'Sassy', 'Charming', 'Cheeky', 'Quirky',
                 'Laid-back', 'Elegant', 'Playful', 'Soothing', 'Intense', 'Passionate']
    # Leave write_history BLANK
    write_history = ''
    chat_id = str(result['message']['chat']['id'])
    prompt = ""
    # Retrieve and parse the ALLOWED_GROUP_ID environment variable
    allowed_group_ids = os.getenv('ALLOWED_GROUP_ID', '')
    allowed_group_ids_list = allowed_group_ids.split(',')
    if chat_id in allowed_group_ids_list:
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

                await telegram.send_text(bot_response, chat_id, msg_id)
                name = result['message']['new_chat_participant']['first_name']

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

                await telegram.send_text(bot_response, chat_id, msg_id)

                # x = await telegram_bot_sendtext('I just sent some message', '163905035', None)

            except Exception as e:
                print("Error while waiting for the answer from OpenAI", e)

                await telegram.send_text("Ответ от центрального мозга потерялся в дороге",
                                         chat_id, msg_id)

                await telegram.send_text(f"OpenAI не ответил вовремя - {e}", '163905035', None)

        if ASK_COMMAND in result['message']['text']:
            prompt = result['message']['text'].replace(ASK_COMMAND, "")
            asked = True
            print('Got the /ask command, master!')
            try:
                answer = research.reply(file, prompt)

                await telegram.send_text(answer, chat_id, msg_id)
            except Exception as e:
                print("Error while waiting for the answer with from OpenAI for the /ask", e)

                await telegram.send_text("Этот книжный вопрос поломал логику",
                                         chat_id, msg_id)

                await telegram.send_text(f"OpenAI не ответил вовремя на /ask - {e}",
                                         '163905035', None)
                print("Couldn't handle the /ask command", e)

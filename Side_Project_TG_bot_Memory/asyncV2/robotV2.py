import requests
import json
import os
import re
import random
import memory
import asyncio
import os

# OpenAI secret Key
API_KEY = os.environ['API_KEY']
# Models: text-davinci-003,text-curie-001,text-babbage-001,text-ada-001
MODEL = 'text-davinci-003'
# Telegram secret access bot token
BOT_TOKEN = os.environ['BOT_TOKEN']
# Specify all group ID the bot can respond too
ALLOWED_GROUP_ID = os.environ['ALLOWED_GROUP_ID']
# Specify your Chat Bot handle
CHATBOT_HANDLE = os.environ['CHATBOT_HANDLE']
# Retrieve last ID message : Create an empty text file named chatgpt.txt, write 1 on the first line of
# the text file and save it, write the full path of your file below
FILENAME = 'chatgpt.txt'

print(BOT_TOKEN)

# 2a. Function that gets the response from OpenAI's chatbot
async def openAI(prompt, max_tokens):
    # Make the request to the OpenAI API
    print("openAI sending request", prompt)
    response = requests.post(
        'https://api.openai.com/v1/completions',
        headers={'Authorization': f'Bearer {API_KEY}'},
        json={'model': MODEL, 'prompt': prompt, 'temperature': 0.8, 'max_tokens': max_tokens},
        timeout=30
    )
    print("openAI got the result", response)

    result = response.json()
    final_result = ''
    for i in range(0, len(result['choices'])):
        final_result += result['choices'][i]['text']

    return final_result


# 2b. Function that gets an Image from OpenAI
async def openAImage(prompt):
    # Make the request to the OpenAI API
    resp = requests.post(
        'https://api.openai.com/v1/images/generations',
        headers={'Authorization': f'Bearer {API_KEY}'},
        json={'prompt': prompt, 'n': 1, 'size': '256x256'}
    )

    response_text = json.loads(resp.text)
    # print(response_text['data'][0]['url'])
      
    return response_text['data'][0]['url']


# Sending a message to a specific telegram group
async def telegram_bot_sendtext(bot_message, chat_id, msg_id):
    
    data = {
        'chat_id': chat_id,
        'text': bot_message,
        'reply_to_message_id': msg_id
    }
    print("TG sending the text", data)
    response = requests.post(
        'https://api.telegram.org/bot' + BOT_TOKEN + '/sendMessage',
        json=data, timeout=10
    )
    print("TG sent the data", response)
    return response.json()


# Sending a image to a specific telegram group
async def telegram_bot_sendimage(image_url, group_id, msg_id):
    data = {'chat_id': group_id, 'photo': image_url, 'reply_to_message_id': msg_id}
    url = 'https://api.telegram.org/bot' + BOT_TOKEN + '/sendPhoto'
    
    response = requests.post(url, data=data)
    return response.json()


# Checking for specific tone for message
async def checkTone(user_message):
    bot_personality=''
    match = re.search(r"/setTone\((.*?)\)", user_message, flags=re.IGNORECASE)
    if match:
        substring = match.group(1)
        bot_personality = 'Answer in a ' + substring + ' tone, '
        user_message=user_message.replace('/setTone('+substring+')', '')
    return [user_message, bot_personality]


async def ChatGPTbot():
    # Give your bot a personality using adjectives from the tone list
    bot_personality = ''
    # Leave write_history BLANK
    write_history = ''
    
    tone_list = ['Friendly', 'Professional', 'Humorous', 'Sarcastic', 'Witty', 'Sassy', 'Charming', 'Cheeky', 'Quirky',
                 'Laid-back', 'Elegant', 'Playful', 'Soothing', 'Intense', 'Passionate']
          
    with open(FILENAME) as f:
        last_update = f.read()
    # Check for new messages in Telegram group
    url = f'https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={last_update}'
    # print('ChatGPTbot sending request')
    try:
        response = requests.get(url, timeout=10)
    except Exception as e:
        print("Error in get updates", e)
    # print("ChatGPTbot got the response", response)
    data = json.loads(response.content)
    # print("Printing the data", data)
    
    result = data['result'][len(data['result'])-1]

    try:
        # Checking for new message
        if float(result['update_id']) > float(last_update):
            # Checking for new messages that did not come from chatGPT
            if not result['message']['from']['is_bot']:
                last_update = str(int(result['update_id']))
                # Retrieving the chat ID of the sender of the request
                chat_id = str(result['message']['chat']['id'])

                if chat_id in ALLOWED_GROUP_ID:
                    msg_id = str(int(result['message']['message_id']))
                    # print('In allowed group ID')
                    try:
                        # Greeting message for new participants
                        if 'new_chat_participant' in result['message']:
                            prompt = 'Write in a ' + random.choice(tone_list) + ' tone: ' + \
                                     "I am here to assist you. Nice to meet you, " + \
                                     result['message']['new_chat_participant']['first_name']

                            bot_response = await openAI(prompt, 200)
                            # Sending back response to telegram group
                            x = await telegram_bot_sendtext(bot_response, chat_id, msg_id)

                    except Exception as e: 
                        print(e)
                    try:
                        if '/img' in result['message']['text']:
                            prompt = result['message']['text'].replace("/img", "")
                            bot_response = await openAImage(prompt)
                            x = await telegram_bot_sendimage(bot_response, chat_id, msg_id)
                    except Exception as e: 
                        print(e)
                        
                    boolean_active = False
                    # Checking that user mentionned chatbot's username in message
                    if CHATBOT_HANDLE in result['message']['text']:
                        prompt = result['message']['text'].replace(CHATBOT_HANDLE, "")
                        boolean_active = True
                        print('Got the Message, master!')
                        
                    # Verifying that the user is responding to the ChatGPT bot
                    if 'reply_to_message' in result['message']:
                        if result['message']['reply_to_message']['from']['is_bot']:
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
                                prompt = write_history+"\n\nQ : "+prompt+"\n\n###\n\n"
                            
                            bot_response = await openAI(f"{bot_personality}{prompt}", 300)
                            if bot_response == '':
                                bot_response = await openAI(f"{bot_personality}{vague_prompt}", 300)
                            
                            x = await telegram_bot_sendtext(bot_response, chat_id, msg_id)
                            
                        except Exception as e: 
                            print("Error while waiting for the answer from OpenAI", e)
                            #TODO Send the message to TG that the answer has failed

    except Exception as e: 
        print("General error in ChatGPTbot", e)

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

# TODO fix if simultaneously get to messages in diffenrent topics or inform that the answer fails


# -*- coding: utf-8 -*-

import requests
from retrying_async import retry
from constants import LITERATURE_EXPERT_ROLE, MODEL, LIT_PROMPT, API_KEY
from dotenv import load_dotenv

load_dotenv()


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
    try:
        response = requests.post(
            'https://api.openai.com/v1/chat/completions',
            headers={'Authorization': f'Bearer {API_KEY}'},
            json={'model': MODEL, 'messages': messages,
                  'temperature': 0.8, 'max_tokens': max_tokens},
            timeout=30
        )
    except Exception as e:
        print('OpenAi request failed', e)
    print("The response:", response)
    # response.raise_for_status()  # Raises an exception for non-2xx status codes
    result = response.json()
    final_result = ''
    print('First Final result:', final_result)
    for i in range(0, len(result['choices'])):
        final_result += result['choices'][i]['message']['content']
    print('Final result:', final_result)
    return final_result


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

# -*- coding: utf-8 -*-

import os
from datetime import timedelta

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

TIME_DELTA = timedelta(hours=12)
cache_dir = os.environ.get("CACHE_DIR", "default_cache_dir")



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
DONT_RATE = "DONT_RATE"
UNLIKE = 'UNLIKE'
UNDISLIKE = 'UNDISLIKE'
UNRATE = 'UNRATE'
RATE_1 = 'RATE_1'
RATE_2 = 'RATE_2'
RATE_3 = 'RATE_3'
RATE_4 = 'RATE_4'
RATE_5 = 'RATE_5'
RATE_6 = 'RATE_6'
RATE_7 = 'RATE_7'
RATE_8 = 'RATE_8'
RATE_9 = 'RATE_9'
RATE_10 = 'RATE_10'
RATES = [RATE_1, RATE_2, RATE_3, RATE_4, RATE_5, RATE_6, RATE_7, RATE_8, RATE_9, RATE_10]

CALLBACKS = [LIKE, DISLIKE, RATE, RATE_1, RATE_2, RATE_3, RATE_4, RATE_5, RATE_6, RATE_7, RATE_8, RATE_9, RATE_10,
             UNDISLIKE, UNLIKE, UNRATE]

RANDOM_BOOK_COMMAND = "*Случайная книга*"
RECOMMEND_COMMAND = "*Рекомендации*"
RECOMMENDATION_EXIT_COMMAND = "*Выйти*"
PREFERENCES_COMMAND = "*Предпочтения*"

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

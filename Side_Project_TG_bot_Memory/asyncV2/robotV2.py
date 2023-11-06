# version 0.0.1, working on news

import requests, re, sys
import memory
import asyncio
import time
from retrying_async import retry
from datetime import datetime
import fantlab_nwe, database_work, handlers, research, telegram_int
from OpenAI import openAI

from constants import BOT_TOKEN, ALLOWED_GROUP_ID, CHATBOT_HANDLE, BOT_NAME, FILENAME, \
    ASK_COMMAND, CLEAR_COMMAND, START_COMMAND, INFO_COMMAND, REFERRAL_COMMAND, HELP_COMMAND, RECOM_COMMAND, \
    SUBSCRIPTION_COMMAND, CHANNEL_NAME, CHANNEL_NAME_RUS, TEST, DAY_LIMIT_PRIVATE, DAY_LIMIT_SUBSCRIPTION, \
    CONTEXT_DEPTH, MAX_TOKENS, REFERRAL_BONUS, MONTH_SUBSCRIPTION_PRICE, file, CHECK_MARK, LITERATURE_EXPERT_ROLE, \
    LITERATURE_EXPERT_ROLE_RUS, DEFAULT_ROLE, DEFAULT_ROLE_RUS, ROLES, ROLES_ZIP, LIKE, DISLIKE, RATE, CALLBACKS, \
    RANDOM_BOOK_COMMAND, RECOMMEND_COMMAND, RECOMMENDATION_EXIT_COMMAND, PREFERENCES_COMMAND

if sys.stdout.encoding != 'utf-8':
    sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

# Set default encoding to UTF-8 for stderr
if sys.stderr.encoding != 'utf-8':
    sys.stderr = open(sys.stderr.fileno(), mode='w', encoding='utf-8', buffering=1)

# new connectors
connector = database_work.DatabaseConnector('fantlab')
# cursor = connector.get_cursor()

# extractors for the database tables
mess_ext = database_work.MessagesInteractor(connector, test=TEST)
opt_ext = database_work.OptionsInteractor(connector, test=TEST)
subs_ext = database_work.SubscriptionsInteractor(connector, test=TEST)

telegram = telegram_int.TelegramInt(BOT_TOKEN)
handler = handlers.Handler(mess_ext, opt_ext, subs_ext, telegram)

# Interactor with the fantlab database, main class for requests
fant_ext = database_work.FantInteractor(connector)

# Initialize the Fantlab_api with the base URL
api_connect = fantlab_nwe.FantlabApi()
# Initialize DatabaseConnector with the Fantlabapiclient
service = fantlab_nwe.BookDatabase(api_connect)


async def handle_random_book(chat_id):
    work = await service.get_random_work(image_on=True)
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
    print(f'Role {role} for {chat_id} is set')
    role_rus = ROLES_ZIP[role]
    if not silent:
        await telegram.send_text(f'Установлена роль: {role_rus}. \nИстория диалога очищена',
                                 chat_id, None, await set_keyboard_roles(chat_id))


async def add_private_message_to_db(chat_id, text, role, subscription_status):
    # Here, we'll store the message in the database
    timestamp = int(time.time())
    subscription_status = 1 if subscription_status else 0
    await mess_ext.insert_message(chat_id, text, role, subscription_status, timestamp)


async def get_last_messages(chat_id, amount):
    # Retrieve the last messages from the database

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
    message_count = await mess_ext.check_message_limit(chat_id, subscription_status, start_of_day_timestamp)
    if message_count > limit:
        message_count = limit
    # get the bonus free messages if exist
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
    await telegram.send_text(message, chat_id, None, keyboard_subscribe)


async def parse_updates(result, last_update):
    if float(result['update_id']) > float(last_update):
        # handle the pre_check_out
        # TODO Drag to the payment lib
        try:
            if result['pre_checkout_query']:
                try:
                    await telegram.handle_pre_checkout_query(result)
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
                print("HERE IN UPDATES")
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


async def handle_private(result):
    # handle the successful payment
    try:
        if result['message']['successful_payment']:
            try:
                await telegram.handle_successful_payment(result['message'], subs_ext)
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

    chat_id = result['message']['chat']['id']
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
            await telegram.handle_pay_command(chat_id)
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
    revealed_date = datetime.now().strftime('%Y-%m-%d')
    referral_link = f'https://t.me/{BOT_NAME}?start={user_id}'
    # # Add a new user with default subscription status, start date, and expiration date
    await subs_ext.add_new_user(user_id, revealed_date, referral_link)

    # TODO check if new users are ok with roles
    # conn_opt = sqlite3.connect(OPTIONS_DATABASE)
    # cursor_opt = conn_opt.cursor()
    # role = DEFAULT_ROLE
    # # Add a new user default role
    # cursor_opt.execute("INSERT INTO options (chat_id, gpt_role) "
    #                    "VALUES (?, ?)", (user_id, role))
    # conn_opt.commit()


async def add_reffered_by(chat_id, referree):
    result = await subs_ext.referred_by(chat_id)
    refer_exist = True if result else False
    print('The previous referral link is', result)
    if not refer_exist:
        # Add to a newly added user the referree id
        await subs_ext.add_referree(referree, chat_id)
        await telegram.send_text(f'Поздравляем! Пользователь {chat_id} присоединился к боту {BOT_NAME} по '
                                 f'вашей реферальной ссылке', referree)
        return True
    else:
        print(f'The {chat_id} was already joined by a referral link')
        return False


async def check_subscription_validity(chat_id):
    # # Get the subscription status, start date, and expiration date for the user
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

    # # previous version of parsing updates
    # try:
    #     # Checking for new message and processing them
    #     for res in result:
    #         last_update = await parse_updates(res, last_update)
    # except Exception as e:
    #     print("General error in ChatGPTbot", e)
    #     await telegram.send_text(f"Случилась общая ошибка в коде - {e}", '163905035')

    # new version of parsing updates with async.gather
    parsers = [parse_updates(res, last_update) for res in result]
    parallel_result = await asyncio.gather(*parsers)
    if parallel_result:
        last_update = str(max([int(element) for element in parallel_result]))
    print('UPDATES:', parallel_result, '\n', last_update)

    # Updating file with last update ID
    with open(FILENAME, 'w') as f:
        f.write(last_update)
    return "done"


# async def main():
#     connector.db_pool = await connector._create_db_pool()
#     while True:
#         try:
#             await ChatGPTbot()
#         except TypeError as e:
#             print('Typeerror', e)
#         try:
#             await asyncio.sleep(5)
#         except TypeError as e:
#             print('The problem in sleep', e)


async def client_interactions_with_delay(client_interactions, delay=1):
    for interaction in client_interactions:
        await interaction
        await asyncio.sleep(delay)


async def main():
    connector.db_pool = await connector._create_db_pool()
    while True:
        client_interactions = [ChatGPTbot() for _ in range(5)]
        try:
            await client_interactions_with_delay(client_interactions, delay=5)
            # await asyncio.gather(*client_interactions_with_delay)
        except TypeError as e:
            print('Typeerror', e)
        # try:
        #     await asyncio.sleep(5)
        # except TypeError as e:
        #     print('The problem in sleep', e)


if __name__ == '__main__':
    # loop = asyncio.new_event_loop()
    # asyncio.set_event_loop(loop)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # connector.close_connection()
        print('Finished')

# loop = asyncio.get_event_loop()
# loop.run_until_complete(main())


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

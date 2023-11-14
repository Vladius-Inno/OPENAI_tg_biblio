# version 0.0.1, working on news
import json
import requests
import sys
import asyncio
import time
from retrying_async import retry
from datetime import datetime
import fantlab, database_work, handlers, telegram_int
from OpenAI import openAI
from group_handle import handle_supergroup
from fant_random_simple import random_parsed
import cached_funcs
from cached_funcs import cache
from constants import BOT_TOKEN, BOT_NAME, FILENAME, RATE_1, RATE_2, RATE_3, RATE_4, RATE_5, RATE_6, RATE_7, RATE_8, \
    RATE_9, RATE_10, DONT_RATE,  RATES, UNLIKE, UNDISLIKE, UNRATE, \
    CLEAR_COMMAND, START_COMMAND, INFO_COMMAND, REFERRAL_COMMAND, HELP_COMMAND, RECOM_COMMAND, \
    SUBSCRIPTION_COMMAND, CHANNEL_NAME, CHANNEL_NAME_RUS, TEST, DAY_LIMIT_PRIVATE, DAY_LIMIT_SUBSCRIPTION, \
    CONTEXT_DEPTH, MAX_TOKENS, REFERRAL_BONUS, MONTH_SUBSCRIPTION_PRICE, CHECK_MARK, LITERATURE_EXPERT_ROLE, \
    LITERATURE_EXPERT_ROLE_RUS, DEFAULT_ROLE, DEFAULT_ROLE_RUS, ROLES, ROLES_ZIP, LIKE, DISLIKE, RATE, CALLBACKS, \
    RANDOM_BOOK_COMMAND, RECOMMEND_COMMAND, RECOMMENDATION_EXIT_COMMAND, PREFERENCES_COMMAND, RECOMMEND_BOOK

if sys.stdout.encoding != 'utf-8':
    sys.stdout = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

# Set default encoding to UTF-8 for stderr
if sys.stderr.encoding != 'utf-8':
    sys.stderr = open(sys.stderr.fileno(), mode='w', encoding='utf-8', buffering=1)

# new connectors
connector = database_work.DatabaseConnector('fantlab', test=TEST)

# interactor for the database tables

db_int = database_work.DatabaseInteractor(connector)
# mess_ext = database_work.MessagesInteractor(connector, test=TEST)
# opt_ext = database_work.OptionsInteractor(connector, test=TEST)
# subs_ext = database_work.SubscriptionsInteractor(connector, test=TEST)

telegram = telegram_int.TelegramInt(BOT_TOKEN)
handler = handlers.Handler(db_int, telegram)

# Interactor with the fantlab database, main class for requests
fant_ext = database_work.FantInteractor(connector)

# Initialize the Fantlab_api with the base URL
api_connect = fantlab.FantlabApi()
# Initialize DatabaseConnector with the Fantlabapiclient
service = fantlab.BookDatabase(api_connect)


async def store_book(conn, work, chat_id):

    # async with await connector._get_user_connection(chat_id) as conn:
    stored = await fant_ext.store_work(conn, work)

    if stored:
        # get the extended data to extract characteristics
        ext_work = await service.get_extended_work(work.id)
        print(f'Got the extended data for book {ext_work.id}')
        genres = ext_work.get_characteristics()
        if genres:
            await fant_ext.update_work_genres(conn, work.id, genres)
            print(f'Genres for book {ext_work.id} updated')
        else:
            print(f"Book {ext_work.id} isn't classified")
        # get the similar books
        similar_books = await service.get_similars(work.id)
        if similar_books:
            await fant_ext.update_similars(conn, work.id, similar_books)
            print(f"Updated the similars for {work.id}")
        else:
            print(f'No similars for {work.id}')

    # update initial user prefs
    await fant_ext.update_user_prefs(conn, chat_id, work.id, 'no_pref')


async def handle_random_book(chat_id):
    async with await connector._get_user_connection(chat_id) as conn:

        # use simple parse fantlab page to get a work id
        random_work_id = await random_parsed()
        # get the work by this id
        if random_work_id:
            work = await service.get_work(random_work_id)
        else:
            # get the book from Fantlab the hard way via retrying the api (though here we filter as we want)
            work = await service.get_random_work(image_on=False)

        # send the book to TG
        await telegram.send_work(work, chat_id, set_keyboard_rate_work(work.id))

        # store in cache the id if the last shown work
        last_work_cache = str(chat_id) + '_last_work'
        cache[last_work_cache] = work.id

        # store the book in the DB
        # asyncio.create_task(store_book(work, chat_id))
        await store_book(conn, work, chat_id)

    return work.id, chat_id


async def handle_recommend_book(chat_id):
    async with await connector._get_user_connection(chat_id) as conn:

        # get a recommendation
        recommend_work_id = await db_int.get_recommendation(conn, chat_id)

        to_store = False

        # get the work by this id
        if recommend_work_id:
            work = await db_int.get_work_db(conn, recommend_work_id)
            if not work:
                work = await service.get_work(recommend_work_id)
                to_store = True
            else:
                print(f"Got the {recommend_work_id} from the DB")
        else:
            print('The recommended books list is EMPTY')

        # send the book to TG
        await telegram.send_work(work, chat_id, set_keyboard_rate_work(work.id))

        # store in cache the id if the last shown work
        last_work_cache = str(chat_id) + '_last_work'
        cache[last_work_cache] = work.id

        # store the book in the DB
        if to_store:
            await store_book(conn, work, chat_id)

    return work.id, chat_id

async def handle_recomendation(chat_id):
    pass


async def handle_recom_exit(conn, chat_id):
    await telegram.send_text("Вышли из режима рекомендаций", chat_id, None, set_keyboard_roles(conn, chat_id))


async def handle_preferences(conn, chat_id):
    # print(f'Handling preferences for {chat_id}')
    pass


INLINE_COMMANDS = {RECOMMEND_COMMAND: handle_recomendation,
                   RECOMMENDATION_EXIT_COMMAND: handle_recom_exit,
                   PREFERENCES_COMMAND: handle_preferences,
                   RANDOM_BOOK_COMMAND: handle_random_book,
                   RECOMMEND_BOOK: handle_recommend_book}


async def set_keyboard_roles(conn, chat_id):
    # get the gpt_role
    gpt_role = await db_int.check_role(conn, chat_id)
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
            {'text': RECOMMEND_BOOK},
            {'text': RECOMMENDATION_EXIT_COMMAND},
        ],
        [
            # {'text': RECOMMENDATION_EXIT_COMMAND},
            # {'text': PREFERENCES_COMMAND}
        ]
    ],
    'resize_keyboard': True,  # Allow the keyboard to be resized
    'one_time_keyboard': False  # Requests clients to hide the keyboard as soon as it's been used
}


async def setup_role(conn, chat_id, role, silent=False):
    # Add a gpt_role into the database with options extractor
    await db_int.setup_role(conn, chat_id, role)
    print(f'Role {role} for {chat_id} is set')
    role_rus = ROLES_ZIP[role]
    if not silent:
        await telegram.send_text(f'Установлена роль: {role_rus}. \nИстория диалога очищена',
                                 chat_id, None, await set_keyboard_roles(conn, chat_id))


async def handle_start(conn, chat_id, msg, msg_id, result):
    try:
        await setup_role(conn, chat_id, DEFAULT_ROLE, silent=True)

        await handler.start_command(chat_id, result['message']['from']['first_name'], DAY_LIMIT_PRIVATE,
                                    DAY_LIMIT_SUBSCRIPTION, REFERRAL_BONUS, MONTH_SUBSCRIPTION_PRICE,
                                    await set_keyboard_roles(conn, chat_id))

        # check if the new user came with referral link and get the number of referree
        if msg.startswith('/start '):
            referree = int(msg.strip('/start '))
            print('We have got a referring user', referree)
            bonus_from_refer = await add_reffered_by(conn, chat_id, referree)
            if bonus_from_refer:
                await db_int.add_referral_bonus(conn, referree, REFERRAL_BONUS)
            return
        return
    except Exception as e:
        print("Couldn't handle the /start command", e)
        await telegram.send_text("Извините, не смог стартовать", chat_id, msg_id)
        await telegram.send_text(f"Не смог стартовать у {chat_id} - {e}", '163905035')
        return


async def add_private_message_to_db(conn, chat_id, text, role, subscription_status):
    # Here, we'll store the message in the database
    timestamp = int(time.time())
    subscription_status = 1 if subscription_status else 0
    await db_int.insert_message(conn, chat_id, text, role, subscription_status, timestamp)


async def get_last_messages(conn, chat_id, amount):
    # Retrieve the last messages from the database

    rows = await db_int.get_last_messages(conn, chat_id, amount)
    reversed_rows = reversed(rows)  # Reverse the order of the rows
    messages = []
    for row in reversed_rows:
        chat_id, role, message = row
        # print(f"Chat ID: {chat_id}, Role: {role}, Message: {message}")
        messages.append({'role': role, 'content': message})
    return messages


async def check_message_limit(conn, chat_id, limit, subscription_status):
    subscription_status = 1 if subscription_status else 0
    # Get the timestamp for the start of the current calendar day
    start_of_day = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    start_of_day_timestamp = start_of_day.timestamp()
    # Retrieve the message count for the current chat_id from the database

    # TODO - merge to a single query
    # the amount of messages a user had today
    message_count = await db_int.check_message_limit(conn, chat_id, subscription_status, start_of_day_timestamp)
    if message_count > limit:
        message_count = limit
    # get the bonus free messages if exist
    free_message_count = await db_int.get_free_messages(conn, chat_id)

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


async def parse_updates(result, last_update_json):

    last_update = last_update_json['last_update']
    last_update_new = last_update_json

    # if the next book must be loaded
    # run_next = False

    if float(result['update_id']) > float(last_update):
        print('Start parsing', result['update_id'])
        print('Start parsing', result['update_id'])
        # handle the pre_check_out
        # TODO Drag to the payment lib
        try:
            if result['pre_checkout_query']:
                try:
                    last_update = str(int(result['update_id']))
                    last_update_new['last_update'] = last_update
                    write_update(last_update_new)
                    await telegram.handle_pre_checkout_query(result)
                    print('Successful checkout')
                except requests.exceptions.RequestException as e:
                    print('Couldnt handle the pre checkout')
                    last_update = str(int(result['update_id']))
                    last_update_new['last_update'] = last_update
                    write_update(last_update_new)
                    await telegram.send_text('Не удалось провести оплату. Пожалуйста, попробуйте ещё раз!',
                                             result['pre_checkout_query']['from']['id'])
                return
        except Exception as e:
            pass

        try:
            if result['channel_post']:
                channel = result['channel_post']['sender_chat']['title']
                print(f'We have got a channel post in {channel}')
                last_update = str(int(result['update_id']))
                last_update_new['last_update'] = last_update
                write_update(last_update_new)

                return
        except Exception as e:
            pass

        try:
            if result['edited_channel_post']:
                channel = result['edited_channel_post']['sender_chat']['title']
                print(f'We have got a update to a channel post in {channel}')
                last_update = str(int(result['update_id']))
                last_update_new['last_update'] = last_update
                write_update(last_update_new)

                return
        except Exception as e:
            pass

        try:
            if result['callback_query']:
                print("HERE IN UPDATES")
                # handle like, rates
                run_next = await handle_callback_query(result['callback_query'])
                last_update = str(int(result['update_id']))
                last_update_new['extras'].update(run_next)
                last_update_new['last_update'] = last_update
                write_update(last_update_new)
                return run_next
        except Exception as e:
            print(e)

        try:
            # Checking for new messages that did not come from chatGPT
            if not result['message']['from']['is_bot']:
                print('Correct message for', result['message']['chat']['type'])
                # remember the last update number
                last_update = str(int(result['update_id']))
                last_update_new['last_update'] = last_update
                write_update(last_update_new)

                chat_type = str(result['message']['chat']['type'])
                # check if it's a group
                if chat_type == 'supergroup':
                    await handle_supergroup(result, telegram)
                # check if it's a private chat
                if chat_type == 'private':
                    await handle_private(result)
                if chat_type == "channel":
                    pass
        except Exception as e:
            print(e)

    return


async def handle_private(result):

    chat_id = result['message']['chat']['id']
    msg_id = str(int(result['message']['message_id']))

    async with await connector._get_user_connection(chat_id) as conn:

        # handle the successful payment
        if await handler.successful_payment_in_message(conn, result):
            return

        # TODO if photo is sent, use only caption
        # check if we got the text, else skip
        if not await handler.text_in_message(result, chat_id, msg_id):
            return

        msg = result['message']['text']
        print(chat_id, msg_id, msg)

        # cached
        # a new user
        if not await cached_funcs.user_exists(db_int, conn, chat_id, 'user_exists'):
            await add_new_user(chat_id)

        # cached
        # set options for a new user or in case of options failure
        if not await cached_funcs.options_exist(db_int, conn, chat_id, 'options_exist'):
            await db_int.set_user_option(conn, chat_id)

        # Command detection starts
        if START_COMMAND in msg:
            await handle_start(conn, chat_id, msg, msg_id, result)
            return

        if CLEAR_COMMAND in msg:
            try:
                await handler.handle_clear_command(conn, chat_id)
                await telegram.send_text("Диалог сброшен", chat_id, msg_id, await set_keyboard_roles(conn, chat_id))
                return
            except Exception as e:
                print("Couldn't handle the /clear command", e)
                await telegram.send_text("Извините, не смог очистить диалог", chat_id, msg_id)

        if SUBSCRIPTION_COMMAND in msg:
            print('We have got a payment request')
            try:
                await telegram.handle_pay_command(chat_id)
            except Exception as e:
                print('Couldnt handle the pay command', e)
            return

        if REFERRAL_COMMAND in msg:
            await handler.refer_command(conn, chat_id)
            return

        if HELP_COMMAND in msg:
            await handler.help_command(chat_id)
            return

        if RECOM_COMMAND in msg:
            await handler.handle_recom_command(chat_id, keyboard_recom_markup)
            return

        # TODO Rewrite roles handling
        if LITERATURE_EXPERT_ROLE_RUS in msg:
            await setup_role(conn, chat_id, LITERATURE_EXPERT_ROLE)
            await handler.handle_clear_command(conn, chat_id)
            return

        if DEFAULT_ROLE_RUS in msg:
            await setup_role(conn, chat_id, DEFAULT_ROLE)
            await handler.handle_clear_command(conn, chat_id)
            return
        # Command detection ends for most commands

        # cached
        # get the validity, get_subscription = subscription_status, start_date_text, expiration_date_text, then update
        is_subscription_valid = await check_subscription_validity(conn, chat_id)
        if is_subscription_valid:
            limit = DAY_LIMIT_SUBSCRIPTION
        else:
            limit = DAY_LIMIT_PRIVATE

        # TODO - in check_message_limit merge the queries
        # get_free_messages = free_messages, check_message_count = message_count
        validity, messages_left, free_messages_left = await check_message_limit(conn, chat_id, limit, is_subscription_valid)
        print(f"Subscription for {chat_id} is valid: {is_subscription_valid}, messages left {messages_left}, "
              f"bonus messages left {free_messages_left}")

        if INFO_COMMAND in msg:
            try:
                await handler.handle_info_command(conn, chat_id, is_subscription_valid, messages_left, free_messages_left,
                                                  REFERRAL_BONUS)
                return
            except Exception as e:
                print("Couldn't handle the /info command", e)
                await telegram.send_text("Извините, не смог выдать информацию",
                                         chat_id, msg_id)
                await telegram.send_text(f"Не смог проинформировать у {chat_id} - {e}",
                                         '163905035')
                return

        # cached
        try:
            channel_subscribed = await cached_funcs.user_subscribed(telegram, chat_id, CHANNEL_NAME, 'user_subscribed')
        except requests.exceptions.RequestException as e:
            print("Couldn't check the channel subscription")
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
                # run the correspondent function handler
                if inline_command:
                    # call the corresponding func
                    await INLINE_COMMANDS[inline_command](chat_id)
                    return

                if messages_left <= 0:
                    print('Need to decrease the free messages')
                    await db_int.decrease_free_messages(conn, chat_id, 1)

                # get the last n messages from the db to feed them to the gpt
                messages = await get_last_messages(conn, chat_id, CONTEXT_DEPTH)
                # add the last received message to the db
                await add_private_message_to_db(conn, chat_id, msg, 'user', is_subscription_valid)
                # send the last message and the previous historical messages from the db to the GPT
                prompt = msg
                # send the quick message to the user, which shows that we start thinking, get the sent message id
                x = await telegram.send_text("⏳ Ожидайте ответа от бота...", chat_id, msg_id)
                sent_msg_id = x['result']['message_id']

                # set the typing status
                try:
                    await telegram.set_typing_status(chat_id)
                except requests.exceptions.RequestException as e:
                    print('Couldnt set the typing status', e)

                # TODO - 5 to cache dynamically
                gpt_role = await db_int.check_role(conn, chat_id)
                try:
                    bot_response = await openAI(f"{prompt}", MAX_TOKENS, messages, gpt_role)
                    await add_private_message_to_db(conn, chat_id, bot_response, 'assistant', is_subscription_valid)
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


# Function to handle the callback query from recommendations
async def handle_callback_query(callback_query):
    callback_data = callback_query['data']
    # print('Callback is ', callback_data)
    chat_id = callback_query['message']['chat']['id']
    msg_id = callback_query['message']['message_id']

    async with await connector._get_user_connection(chat_id) as conn:

        # the flag to load the next book
        run_next = {}

        call_action = callback_data.split()[0]
        work_to_handle = callback_data.split()[1]
        data_to_get = str(chat_id) + '_last_work'

        if call_action in CALLBACKS:
            print('Here comes the callback', callback_data)
            # transfer the chat_id, the work_id which is extracted from the callback, and the msg_id
            if call_action == LIKE:
                await like(conn, chat_id, int(work_to_handle), msg_id)
                # check if the interaction is with the last card in the chat
                if cache[data_to_get] == int(work_to_handle):
                    run_next = {str(chat_id): 'run_next'}
            if call_action == DISLIKE:
                await dislike(conn, chat_id, int(work_to_handle), msg_id)
                # check if the interaction is with the last card in the chat
                if cache[data_to_get] == int(work_to_handle):
                    run_next = {str(chat_id): 'run_next'}
            if call_action == RATE:
                await rate(conn, chat_id, work_to_handle, msg_id)
            if call_action in RATES:
                await rate_digit(conn, chat_id, int(work_to_handle), msg_id, call_action)
                # check if the interaction is with the last card in the chat
                if cache[data_to_get] == int(work_to_handle):
                    run_next = {str(chat_id): 'run_next'}
            if call_action == UNLIKE:
                await unlike(conn, chat_id, int(work_to_handle), msg_id)
            if call_action == UNDISLIKE:
                await undislike(conn, chat_id, int(work_to_handle), msg_id)
            if call_action == UNRATE:
                await unrate(conn, chat_id, int(work_to_handle), msg_id)
            if call_action == DONT_RATE:
                await dont_rate(conn, chat_id, int(work_to_handle), msg_id)

        return run_next

async def update_user_prefs(chat_id, work_id, pref, rate_digit=None):
    async with await connector._get_user_connection(chat_id) as conn:
        await fant_ext.update_user_prefs(conn, chat_id, work_id, pref, rate_digit)
        # if pref in ['like', 'rate', 'dislike', ]:
        await fant_ext.update_recommendations(conn, chat_id, work_id, pref, rate_digit)


async def like(conn, chat_id, work_id, msg_id):

    print(chat_id, 'Likes', work_id)

    # change the inline-keyboard
    keyboard = {
        'inline_keyboard': [[
            {'text': "Unlike", 'callback_data': f'UNLIKE {work_id}'},
            {'text': "Rate", 'callback_data': f'{RATE} {work_id}'}
        ]]
    }
    await telegram.edit_bot_message_markup(chat_id, msg_id, keyboard)

    asyncio.create_task(update_user_prefs(chat_id, work_id, 'like'))


async def unlike(conn, chat_id, work_id, msg_id):

    print(chat_id, 'UnLikes', work_id)

    asyncio.create_task(update_user_prefs(chat_id, work_id, 'unlike'))

    # change the inline-keyboard
    keyboard = set_keyboard_rate_work(work_id)
    await telegram.edit_bot_message_markup(chat_id, msg_id, keyboard)



async def unrate(conn, chat_id, work_id, msg_id):

    print(chat_id, 'UnRates', work_id)

    asyncio.create_task(update_user_prefs(chat_id, work_id, 'unrate'))

    # change the inline-keyboard
    keyboard = set_keyboard_rate_work(work_id)
    await telegram.edit_bot_message_markup(chat_id, msg_id, keyboard)



async def undislike(conn, chat_id, work_id, msg_id):

    print(chat_id, 'UnDisikes', work_id)

    asyncio.create_task(update_user_prefs(chat_id, work_id, 'undislike'))


    # change the inline-keyboard
    keyboard = set_keyboard_rate_work(work_id)
    await telegram.edit_bot_message_markup(chat_id, msg_id, keyboard)



async def dislike(conn, chat_id, work_id, msg_id):

    print(chat_id, 'Dislikes', work_id)

    asyncio.create_task(update_user_prefs(chat_id, work_id, 'dislike'))


    # change the inline-keyboard
    keyboard = {
        'inline_keyboard': [[
            {'text': "Undislike", 'callback_data': f'UNDISLIKE {work_id}'},
            {'text': "Rate", 'callback_data': f'{RATE} {work_id}'}
        ]]
    }
    await telegram.edit_bot_message_markup(chat_id, msg_id, keyboard)



async def rate(conn, chat_id, work_id, msg_id):
    print(chat_id, 'is going to rate', work_id)

    # change the inline-keyboard
    keyboard = {
        'inline_keyboard': [[
            {'text': "1", 'callback_data': f'{RATE_1} {work_id}'},
            {'text': "2", 'callback_data': f'{RATE_2} {work_id}'},
            {'text': "3", 'callback_data': f'{RATE_3} {work_id}'},
            {'text': "4", 'callback_data': f'{RATE_4} {work_id}'},
            {'text': "5", 'callback_data': f'{RATE_5} {work_id}'}
        ], [
            {'text': "6", 'callback_data': f'{RATE_6} {work_id}'},
            {'text': "7", 'callback_data': f'{RATE_7} {work_id}'},
            {'text': "8", 'callback_data': f'{RATE_8} {work_id}'},
            {'text': "9", 'callback_data': f'{RATE_9} {work_id}'},
            {'text': "10", 'callback_data': f'{RATE_10} {work_id}'}
        ],
            [{'text': "Don't rate", 'callback_data': f'{DONT_RATE} {work_id}'}]

        ]
    }
    await telegram.edit_bot_message_markup(chat_id, msg_id, keyboard)


async def dont_rate(conn, chat_id, work_id, msg_id):
    print(chat_id, 'is NOT going to rate', work_id)

    keyboard = set_keyboard_rate_work(work_id)
    await telegram.edit_bot_message_markup(chat_id, msg_id, keyboard)


async def rate_digit(conn, chat_id, work_id, msg_id, rate_string):

    if rate_string not in RATES:
        return
    rate_digit = RATES.index(rate_string) + 1
    print(f'{chat_id} rates {work_id} as {rate_digit}')
    asyncio.create_task(update_user_prefs(chat_id, work_id, 'rate', rate_digit))

    text = f"Rated {rate_digit}. Change?"

    # change the inline-keyboard
    keyboard = {
        'inline_keyboard': [[
            {'text': text, 'callback_data': f'{UNRATE} {work_id}'},
            {'text': "Smth else", 'callback_data': f'SMTH {work_id}'}
        ]]
    }
    await telegram.edit_bot_message_markup(chat_id, msg_id, keyboard)



async def add_new_user(user_id):
    revealed_date = datetime.now().strftime('%Y-%m-%d')
    referral_link = f'https://t.me/{BOT_NAME}?start={user_id}'
    # # Add a new user with default subscription status, start date, and expiration date
    await db_int.add_new_user(user_id, revealed_date, referral_link)

    # TODO check if new users are ok with roles
    # conn_opt = sqlite3.connect(OPTIONS_DATABASE)
    # cursor_opt = conn_opt.cursor()
    # role = DEFAULT_ROLE
    # # Add a new user default role
    # cursor_opt.execute("INSERT INTO options (chat_id, gpt_role) "
    #                    "VALUES (?, ?)", (user_id, role))
    # conn_opt.commit()


async def add_reffered_by(conn, chat_id, referree):
    result = await db_int.referred_by(conn, chat_id)
    refer_exist = True if result else False
    print('The previous referral link is', result)
    if not refer_exist:
        # Add to a newly added user the referree id
        await db_int.add_referree(conn, referree, chat_id)
        await telegram.send_text(f'Поздравляем! Пользователь {chat_id} присоединился к боту {BOT_NAME} по '
                                 f'вашей реферальной ссылке', referree)
        return True
    else:
        print(f'The {chat_id} was already joined by a referral link')
        return False


# TODO combine with other requests
async def check_subscription_validity(conn, chat_id):
    # # Get the subscription status, start date, and expiration date for the user

    # cached
    result = await cached_funcs.get_subscription(db_int, conn, chat_id, 'get_subscription')
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
                await db_int.update_subscription_status(conn, chat_id, 0, start_date_text, expiration_date_text)
                return False
    return False


def write_update(last_update):
    # Updating file with last update ID
    with open(FILENAME, 'w') as f:
        json.dump(last_update, f)
        # f.write(last_update)
    return "done"


def read_update():
    with open(FILENAME, 'r') as f:
        data = json.load(f)

    return data


# new main with async create tasks
async def main():
    await connector._create_db_pool()
    while True:
        try:
            # read the last update id parsed from the file
            last_update = read_update()
            print('The last update in the file:', last_update)

            # get updates for the bot from telegram
            try:
                result = await telegram.get_updates(last_update)
            except requests.exceptions.RequestException as e:
                print("Didn't get the update from TG", e)
                result = []
                await telegram.send_text(f"Не смог получить апдейт от телеграма - {e}", '163905035')

            # parse extras, if exists, there might be run_next code to run the next random book
            if last_update['extras']:
                extras = last_update['extras']
                keys = list(extras.keys())
                for key in keys:
                    if extras[key] == 'run_next':
                        print(f'{key} wants to run next')
                        last_update['extras'].pop(key)
                        write_update(last_update)
                        chat_id = int(key)
                        asyncio.create_task(handle_random_book(chat_id))

            # iterate on the list of updates
            for res in result:
                asyncio.create_task(parse_updates(res, last_update))

            await asyncio.sleep(5)

        except TypeError as e:
            print('Typeerror', e)

    # finally:
    #     # connector.close_connection()
    #     await connector._close_db_pool()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print('Finished')

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

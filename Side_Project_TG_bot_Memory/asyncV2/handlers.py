# -*- coding: utf-8 -*-

from datetime import datetime, timedelta
import fantlab
import random
import requests
from constants import DAY_LIMIT_SUBSCRIPTION


class Handler:
    def __init__(self, db_int=None, telegram_ext=None):
        self.db_int = db_int
        # self.opt_ext = opt_ext
        # self.subs_ext = subs_ext
        self.telegram_ext = telegram_ext

    async def handle_clear_command(self, conn, chat_id):
        # Update the messages associated with the specified chat_id, so they are "cleared"
        await self.db_int.clear_messages(conn, chat_id)

    async def handle_info_command(self, conn, chat_id, validity, messages_left, free_messages_left, referral_bonus):
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
            # conn_pay = sqlite3.connect(SUBSCRIPTION_DATABASE)
            # cursor_pay = conn_pay.cursor()
            # # Retrieve the expiration date for the user
            # cursor_pay.execute("SELECT expiration_date FROM subscriptions WHERE chat_id = ?", (chat_id,))
            # result = cursor_pay.fetchone()[0]
            result = await self.db_int.get_expiration_date(conn, chat_id)

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

    Оформите подписку и получите {DAY_LIMIT_SUBSCRIPTION} сообщений в день. Это поможет развивать бота и оплачивать сервер.

    Также вы можете отправить другу ссылку на бота, используйте команду /refer. Когда друг начнёт пользоваться ботом, вы получите {referral_bonus} бонусных сообщений. 

    '''
        await self.telegram_ext.send_text(message, chat_id)
        # try:
        #     x = await telegram_bot_sendtext(message, chat_id)
        # except requests.exceptions.RequestException as e:
        #     print('Coulndt send the info message', e)

    async def start_command(self, chat_id, name, day_limit_private, day_limit_subscription, referral_bonus,
                            month_subscription_price, set_keyboard):
        message = f'''{name}, приветствую!

⚡️Я бот, рекомендующий книги и поддерживающий ChatGPT

Я умею:
    
1. Рекомендовать книги на основе ваших предпочтений - зайдите в Рекомендации через синюю кнопку меню слева
2. Искать книги  - отправьте сообщение "Найди + ваш запрос", например "Найди Гарри Поттер"
3. Делать всё то, что умеет ChatGPT:
    - Писать тексты
    - Обобщать информацию
    - Поддерживать беседу и запоминать контекст - просто напишите мне сообщение.

В бесплатном режиме вам доступно {day_limit_private} сообщений в сутки. С подпиской лимит увеличивается до {day_limit_subscription}.

Подписка поможет развивать бота и оплачивать сервер. Стоимость подписки - {month_subscription_price}р в месяц.

🔄 Вы можете сбросить беседу, чтобы я не подтягивал из памяти ненужную информацию, для этого есть команда /clear.

❕ Если я вам не отвечаю, перезапустите меня командой /start

Спасибо! '''
        # try:
        #     x = await telegram_bot_sendtext(message, chat_id, None, set_keyboard(chat_id))
        # except requests.exceptions.RequestException as e:
        #     print('Coulndt send the welcome message', e)
        await self.telegram_ext.send_text(message, chat_id, None, set_keyboard)

    async def refer_command(self, conn, chat_id):
        # Get a referral link from the database
        result = await self.db_int.get_referral(conn, chat_id)
        print('The referral link is', result)

        message = f'''
⚡ Ссылка на присоединение к боту: {result}.

🔄 Отправьте это сообщение другу.
            '''
        # try:
        #     x = await telegram_bot_sendtext(message, chat_id, None)
        # except requests.exceptions.RequestException as e:
        #     print('Coulndt send the info message', e)
        await self.telegram_ext.send_text(message, chat_id)

    async def handle_recom_command(self, chat_id, markup):
        # TODO Is the commented section required?
        # # Initialize the Fantlab_api with the base URL
        # api_connect = fantlab.FantlabApi()
        # # Initialize Service A with the ServiceBClient
        # service = fantlab.BookDatabase(api_connect)
        message = f"Поставьте оценки нескольким случайным книгам, и мы сможем начать подбирать для вас персональные рекомендации. Найти нужную книгу можно, отправив сообшение, начинающееся с 'найди'"
        await self.telegram_ext.send_text(message, chat_id, None, markup)

    async def help_command(self, chat_id):
        message = f'''
Напишите ваш запрос и получите ответ от ChatGPT. Бот генерирует текст в формате диалога. Он запоминает и понимает контекст в рамках 5 предыдущих сообщений.

Бот может быть экспертом, ассистентом - нужно только сообщить ему об этом. 

Очистить контекст можно при помощи команды /clear.
    
В режиме Рекомендаций бот подберёт для вас книги.

По всем вопросам - @v_smetanin
            '''
        # try:
        #     x = await telegram_bot_sendtext(message, chat_id, None)
        # except requests.exceptions.RequestException as e:
        #     print('Coulndt send the help message', e)
        await self.telegram_ext.send_text(message, chat_id)

    async def successful_payment_in_message(self, conn, result):
        try:
            if result['message']['successful_payment']:
                try:
                    await self.telegram_ext.handle_successful_payment(conn, result['message'], self.db_int)
                    print('Successful payment')
                    # last_update = str(int(result['update_id']))
                except requests.exceptions.RequestException as e:
                    print('Couldnt handle the payment')
                    # last_update = str(int(result['update_id']))
                    await self.telegram_ext.send_text('Не удалось завершить оплату. Пожалуйста, попробуйте ещё раз!',
                                                      result['pre_checkout_query']['from']['id'])
                return True
        except Exception as e:
            return False
        return False

    async def text_in_message(self, result, chat_id, msg_id):
        if not ('text' in result.get('message')):
            print('Got the non-text message')
            await self.telegram_ext.send_text("Извините, пока что я умею обрабатывать только текст",
                                              chat_id, msg_id)
            return False
        return True

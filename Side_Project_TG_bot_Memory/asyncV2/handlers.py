# -*- coding: utf-8 -*-

from datetime import datetime, timedelta
import fantlab_nwe
import random


class Handler:
    def __init__(self, mess_ext=None, opt_ext=None, subs_ext=None, telegram_ext=None):
        self.mess_ext = mess_ext
        self.opt_ext = opt_ext
        self.subs_ext = subs_ext
        self.telegram_ext = telegram_ext

    async def handle_clear_command(self, chat_id):
        # Update the messages associated with the specified chat_id, so they are "cleared"
        await self.mess_ext.clear_messages(chat_id)

    async def handle_info_command(self, chat_id, validity, messages_left, free_messages_left, referral_bonus):
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
            result = await self.subs_ext.get_expiration_date(chat_id)

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

    Также вы можете отправить другу ссылку на бота, используйте команду /refer. Когда друг начнёт пользоваться ботом, вы получите {referral_bonus} бонусных сообщений! 

    '''
        await self.telegram_ext.send_text(message, chat_id)
        # try:
        #     x = await telegram_bot_sendtext(message, chat_id)
        # except requests.exceptions.RequestException as e:
        #     print('Coulndt send the info message', e)

    async def start_command(self, chat_id, name, day_limit_private, day_limit_subscription, referral_bonus,
                                   month_subscription_price, set_keyboard):
        message = f'''{name}, приветствую!

    ⚡️Я бот, работающий на ChatGPT 3.5.turbo

    Я умею:

    1. Писать и редактировать тексты
    2. Писать и редактировать код
    3. Переводить с и на разные языки
    4. Обобщать информацию
    5. Поддерживать беседу и запоминать контекст

    Моя экспертность - в сфере литературы, этот функционал в разработке, но уже сейчас можно выбрать режим Литературного эксперта.

    Просто напишитет мне, что вы хотите узнать, сделать или отредактировать.

    В бесплатном режиме вам доступно {day_limit_private} сообщений в сутки. С подпиской лимит увеличивается до {day_limit_subscription}.

    Если друг начнёт пользоваться ботом по реферальной ссылке, вы получите {referral_bonus} бонусных сообщений.

    Стоимость подписки - {month_subscription_price}р в месяц.

    🔄 Вы можете сбросить беседу, чтобы я не подтягивал из памяти ненужную информацию, для этого есть команда
    /clear.

    ❕ Если я вам не отвечаю, перезапустите меня командой /start

    Спасибо! '''
        # try:
        #     x = await telegram_bot_sendtext(message, chat_id, None, set_keyboard(chat_id))
        # except requests.exceptions.RequestException as e:
        #     print('Coulndt send the welcome message', e)
        await self.telegram_ext.send_text(message, chat_id, None, set_keyboard)

    async def refer_command(self, chat_id):
        # Get a referral link from the database
        # conn_pay = sqlite3.connect(SUBSCRIPTION_DATABASE)
        # cursor_pay = conn_pay.cursor()
        # cursor_pay.execute("SELECT referral_link FROM subscriptions WHERE chat_id = ?", (chat_id,))
        # result = cursor_pay.fetchone()[0]
        result = await self.subs_ext.get_referral(chat_id)
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
        # Initialize the Fantlab_api with the base URL
        api_connect = fantlab_nwe.FantlabApi()
        # Initialize Service A with the ServiceBClient
        service = fantlab_nwe.BookDatabase(api_connect)
        message = f"Для точного подбора нужно знать о ваших предпочтениях"
        await self.telegram_ext.send_text(message, chat_id, None, markup)

    async def help_command(self, chat_id):
        message = f'''
    Напишите ваш запрос и получите ответ от ChatGPT. Бот генерирует текст в формате диалога, он запоминает и понимает контекст в рамках 5 предыдущих сообщений.

    Бот может быть экспертом, ассистентом - нужно только сообщить ему об этом. 

    Очистить контекст можно при помощи команды /clear.

    По всем вопросам - @v_smetanin
            '''
        # try:
        #     x = await telegram_bot_sendtext(message, chat_id, None)
        # except requests.exceptions.RequestException as e:
        #     print('Coulndt send the help message', e)
        await self.telegram_ext.send_text(message, chat_id)

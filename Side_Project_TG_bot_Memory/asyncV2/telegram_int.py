import json
import requests
from retrying_async import retry


def handle_telegram_errors(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (Exception, requests.exceptions.RequestException) as e:
            # Handle the database connection error here
            print(f"Telegram error: {e}")
            # You can log the error, retry the connection, or perform other actions as needed
            # You might want to raise an exception or return a specific value here
            return None  # For demonstration purposes, return None in case of an error
    return wrapper


class TelegramInt:
    def __init__(self, bot_token):
        self.bot_token = bot_token
        self.base_url = 'https://api.telegram.org/bot'

    @handle_telegram_errors
    @retry(attempts=3, delay=3)
    async def send_text(self, message, chat_id, msg_id=None, reply_markup=None):
        payload = {
            'chat_id': chat_id,
            'text': message,
            'reply_to_message_id': msg_id
        }
        # Convert the keyboard dictionary to JSON string and add to the payload
        if reply_markup:
            reply_markup = json.dumps(reply_markup)
            payload['reply_markup'] = reply_markup
        print("TG sending the text", payload)
        response = requests.post(
            self.base_url + self.bot_token + '/sendMessage',
            json=payload, timeout=10
        )
        response.raise_for_status()  # Raises an exception for non-2xx status codes
        print("TG sent the data", response)
        return response.json()

    @handle_telegram_errors
    @retry(attempts=3)
    async def user_subscribed(self, user_id, channel_name):
        # �������� ���������� � �������� ������������ �� �����
        api_url = self.base_url + self.bot_token + '/getChatMember'
        params = {'chat_id': '@' + channel_name, 'user_id': user_id}
        response = requests.get(api_url, params=params)
        response.raise_for_status()
        data = response.json()
        print(data)
        if response.status_code == 200 and data['ok']:
            # Check if the user is a member of the channel
            return data['result']['status'] in ['member', 'creator', 'admin']
        else:
            # Failed to fetch the chat member information
            return False

    @handle_telegram_errors
    @retry(attempts=3)
    async def set_typing_status(self, chat_id):
        url = self.base_url + self.bot_token + '/sendChatAction'
        payload = {
            'chat_id': chat_id,
            'action': 'typing'
        }
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return response.json()

    @handle_telegram_errors
    @retry(attempts=3, delay=3)
    async def edit_bot_message(self, text, chat_id, message_id):
        url = self.base_url + self.bot_token + '/editMessageText'
        payload = {
            'chat_id': chat_id,
            'message_id': message_id,
            'text': text
        }
        print('Editing', payload)
        response = requests.post(url, json=payload, timeout=20)
        response.raise_for_status()
        print("Edited the message in TG", response)
        return response.json()

    @handle_telegram_errors
    @retry(attempts=3, delay=3)
    async def get_updates(self, last_update):
        # Check for new messages in Telegram group
        # let's test if it works with offset +1
        last_update = str(int(last_update) + 1)
        url = self.base_url + self.bot_token + f'/getUpdates?offset={last_update}'
        response = requests.get(url, timeout=20)
        response.raise_for_status()
        data = json.loads(response.content)
        # provide all messages instead of one in update
        # result = data['result'][len(data['result'])-1]
        result = data['result']
        if data['result']:
            print(data['result'])
            print(len(data['result']), "messages")
        return result

    @handle_telegram_errors
    @retry(attempts=3)
    async def answer_pre_checkout(self, pre_checkout_query_id):
        url = self.base_url + self.bot_token + '/answerPreCheckoutQuery'
        payload = {
            "pre_checkout_query_id": pre_checkout_query_id,
            "ok": True
        }
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return response

    @handle_telegram_errors
    async def handle_payment(self, payload):
        url = self.base_url + self.bot_token + "/sendInvoice"
        # Send the payment request
        response = requests.post(url, json=payload)
        response.raise_for_status()
        return response


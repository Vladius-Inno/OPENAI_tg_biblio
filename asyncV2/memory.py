import asyncio
from telethon import TelegramClient, sync
from telethon.tl.functions.messages import GetHistoryRequest
from telethon.tl.types import InputPeerChannel
from telethon.sessions import StringSession
from telethon.tl.types import PeerUser, PeerChat, PeerChannel
import json


async def get_channel_messages(chat_id, msg_id):
    # Telegram API ID and Hash (you can get it from my.telegram.org)
    api_id = '25616791'
    api_hash = '565dc0ac75361b1141610ddff56c5a16'
    session_hash='1ApWapzMBu8Dc3NAzbOvbFyK4j3p0IUSpxzwpl9rb7C32carKJyE3AOwm7ens5vv6UKNoMug1sX9OICQza_UtJxMrHAWmcjBDDAZhQciYyr6bO9XZt7JYPBWF2H5wljO5Hol-_wia69wXlz7MmhMHEGikzOn36REFo64wzNJS70Mob6ERmS8o5f7n8UY7UB-NLek7Y_sWmrBmasH7IbplsKp10z470uLAUVWKdfCnyHboZ-PDbFNIOVc4zPEXyq29LohoAyNVTgoAnnCHlEcqsha2gOKA7BI9Jzh_jAUZ-iWZVr8j4ztTXDRj0jtP-MGRPwnDW7SaWd-2ZxA_-0yRS2WkSrsZb6s='
    # Identify your bot with his ID number, can be found using this link
    my_bot_id = '6041036556'
    # Storing max 3 past messages
    max_memory_message = 3

    chat_id = int(chat_id)
    data = {}
    # Create a Telegram client with the given session string
    async with TelegramClient(StringSession(session_hash), api_id, api_hash) as client:
        # Connect to Telegram
        await client.connect()

        # Get the channel by its username
        channel = await client.get_entity(PeerChannel(chat_id))
        messages = await client.get_messages(channel, limit=100, offset_id=0)

        for x in messages:
            try:
                if x.text != "":
                    if x.text is not None:
                        try:
                            replied = x.reply_to.reply_to_msg_id
                        except:
                            replied = x.reply_to
                        # The code stores the following information for each message in a dictionary: message id, date, user id of the sender, the message content, id of the message it was replied to, and if the message was pinned.    
                        data[str(x.id)] = [x.id, int(x.date.timestamp()), x.from_id.user_id, x.text, replied, x.pinned]
            except:
                print(x.text)

        reply_number = data[msg_id][4]
        my_dict = []
        write_history = ''
        try:
            #Checking for past replies given msg id
            while reply_number is not None:
                my_dict.append([reply_number, data[str(reply_number)][2]])
                reply_number = data[str(reply_number)][4]
                #Storing max 3 past messages
                if len(my_dict) > max_memory_message + 1:
                    break
        except Exception as e:
            print(e)
            
        #Checking for history    
        if len(my_dict) > 1:
            #Building message history/memory
            for i in range(len(my_dict) - 1, -1, -1):
                if str(my_dict[i][1]) == my_bot_id:
                    #If message comes from bot -> message is treated as response from person A
                    write_history += "A: " + data[str(my_dict[i][0])][3] + "\n"
                else:
                    #Else-> message is treated as response from telegram user
                    write_history += "Q: " + data[str(my_dict[i][0])][3] + "\n"

        
        return write_history


# -*- coding: utf-8 -*-

import diskcache
import os
from datetime import datetime, timedelta

cache_dir = os.environ.get("CACHE_DIR", "default_cache_dir")
# Create a disk cache
cache = diskcache.Cache(cache_dir)


TIME_DELTA = timedelta(hours=12)


async def user_exists(ext, conn, chat_id, func: str):
    data_to_get = str(chat_id) + '_' + func
    if data_to_get in cache:
        last_update_time = cache[data_to_get + "_timestamp"]
        if (datetime.now() - last_update_time) < TIME_DELTA:
            print('Get the user_exists from cache', cache[data_to_get])
            return cache[data_to_get]
    # If not in the cache or TTL expired, query the database
    result = await ext.user_exists(conn, int(chat_id))
    # Store the result in the cache
    cache[data_to_get] = result
    cache[data_to_get + "_timestamp"] = datetime.now()
    return result


async def options_exist(ext, conn, chat_id, func: str):
    data_to_get = str(chat_id) + '_' + func
    if data_to_get in cache:
        last_update_time = cache[data_to_get + "_timestamp"]
        if (datetime.now() - last_update_time) < TIME_DELTA:
            print('Get the options_exist from cache', cache[data_to_get])
            return cache[data_to_get]
    # If not in the cache or TTL expired, query the database
    result = await ext.options_exist(conn, int(chat_id))
    # Store the result in the cache
    cache[data_to_get] = result
    cache[data_to_get + "_timestamp"] = datetime.now()
    return result


async def get_subscription(ext, conn, chat_id, func: str):
    data_to_get = str(chat_id) + '_' + func
    if data_to_get in cache:
        last_update_time = cache[data_to_get + "_timestamp"]
        if (datetime.now() - last_update_time) < TIME_DELTA:
            print('Get the subscription from cache', cache[data_to_get])
            return cache[data_to_get]
    # If not in the cache or TTL expired, query the database
    result = await ext.get_subscription(conn, int(chat_id))
    # Store the result in the cache
    cache[data_to_get] = result
    cache[data_to_get + "_timestamp"] = datetime.now()
    return result


async def user_subscribed(ext, chat_id, channel, func: str):
    data_to_get = str(chat_id) + '_' + func
    if data_to_get in cache:
        last_update_time = cache[data_to_get + "_timestamp"]
        if (datetime.now() - last_update_time) < TIME_DELTA:
            print('Get the channel subscription from cache', cache[data_to_get])
            return cache[data_to_get]
    # If not in the cache or TTL expired, query the database
    result = await ext.user_subscribed(int(chat_id), channel)
    # Store the result in the cache
    cache[data_to_get] = result
    cache[data_to_get + "_timestamp"] = datetime.now()
    return result


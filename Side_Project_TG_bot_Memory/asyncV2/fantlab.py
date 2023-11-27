# -*- coding: utf-8 -*-
import asyncio

import requests
import pprint
import random
import database_work
from retrying_async import retry
import datetime

FANTLAB_API_ADDRESS = 'https://api.fantlab.ru/'
FANTLAB_ADDRESS = 'https://fantlab.ru'


def handle_errors(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (Exception, requests.exceptions.RequestException) as e:
            # Handle the database connection error here
            print(f"Api error: {e}")
            # You can log the error, retry the connection, or perform other actions as needed
            # You might want to raise an exception or return a specific value here
            return None  # For demonstration purposes, return None in case of an error
            # return Exception("Error occured with Fantlab")

    return wrapper


def print_books(books):
    if books:
        for i, book in enumerate(books, start=1):
            print(f"Book {i}:")
            print(f"Author: {book.author}")
            print(f"Title: {book.work_name}")
            print(book.image if book.image else "No image")
            print(f"Rating: {book.rating}\n")
    else:
        print("No books found.")


class Work:
    """
    Is used with the direct request for the Work from the api only.
    Can't be used with the results from the global search.
    """

    dummy = {
        "work_type": "Empty",
        "work_name": "Empty",
    }

    def __init__(self, data):
        self.data = data or Work.dummy
        self.title = self.data.get('title')
        self.author = self.data.get("authors")[0].get("name") if self.data.get("authors") else None
        self.id = self.data.get("work_id")
        self.image = FANTLAB_ADDRESS + self.data.get("image") if self.data.get("image") else None
        self.desc = self.data.get('work_description')
        self.work_type = self.data.get("work_type")
        self.work_name = self.data.get("work_name")
        self.work_name_orig = self.data.get("work_name_orig")
        self.rating = self.data.get("rating").get("rating") if isinstance(self.data.get("rating"), dict) \
            else self.data.get('rating')[0] if self.data.get('rating') else None
        try:
            self.voters = self.data.get("rating").get("voters") if isinstance(self.data.get("rating"), dict) \
                else self.data.get('rating')[1] if self.data.get('rating') else None
        except Exception:
            self.voters = None
        self.work_year = self.data.get('work_year')

    def show(self):
        """
        Used for console printing
        """
        print(f'{self.work_type} {self.work_name}, автор {self.author}')
        pprint.pprint(self.desc)
        print(f'Рейтинг - {self.rating}')
        print(self.image or "Изображение отсутствует")

    def raw(self):
        return self.data


class SearchedWork(Work):
    def __init__(self, data):
        super().__init__(data)
        self.title = None
        self.author = data["autor_rusname"]
        self.image = None
        self.desc = None
        self.work_type = data["name_show_im"]
        self.work_name = data["rusname"]
        self.rating = data["rating"][0]

    def show(self):
        """
        Used for console printing
        """
        print(f'{self.work_type} {self.work_name}, автор {self.author}')
        print('Рейтинг - {:.2f}'.format(self.rating))


class ExtendedWork(Work):
    def __init__(self, data):
        super().__init__(data)

    def print_characteristics(self):
        if self.data.get('classificatory'):
            chars = self.data['classificatory']['genre_group']
            tuples = []
            for char in chars:
                print(char['label'])
                if char.get('genre'):
                    for genre in char['genre']:
                        print(" ", genre['label'], genre['genre_id'])
                        tuples.append((genre['genre_id'], genre['percent'], genre['votes']))
                        if genre.get('genre'):
                            for subgenre in genre['genre']:
                                print("     ", subgenre['label'], subgenre['genre_id'])
                                tuples.append((subgenre['genre_id'], subgenre['percent'], subgenre['votes']))
                                if subgenre.get('genre'):
                                    for subsubgenre in subgenre['genre']:
                                        print("         ", subsubgenre['label'], subsubgenre['genre_id'])
                                        tuples.append(
                                            (subsubgenre['genre_id'], subsubgenre['percent'], subsubgenre['votes']))
            # pprint.pp(tuples)

        return

    def get_characteristics(self):
        if self.data.get('classificatory'):
            chars = self.data['classificatory']['genre_group']
            tuples = []
            for char in chars:
                if char.get('genre'):
                    for genre in char['genre']:
                        tuples.append((self.id, 'wg' + str(genre['genre_id']), genre['percent'], genre['votes']))
                        if genre.get('genre'):
                            for subgenre in genre['genre']:
                                tuples.append(
                                    (self.id, 'wg' + str(subgenre['genre_id']), subgenre['percent'], subgenre['votes']))
                                if subgenre.get('genre'):
                                    for subsubgenre in subgenre['genre']:
                                        tuples.append((self.id, 'wg' + str(subsubgenre['genre_id']),
                                                       subsubgenre['percent'], subsubgenre['votes']))
            return tuples  # work.id, genre_id, genre_weight, genre_voters
        return None

    async def get_parents(self):
        if self.data.get('parents'):
            res = {'cycles': None, 'digests': None}
            cycle_list = []
            digest_list = []
            parents = self.data['parents']
            if parents.get('cycles'):
                cycles = parents['cycles']
                for subcycle in cycles:
                    temp = []
                    for el in subcycle:
                        if el.get('work_id'):
                            voters = None
                            author = el.get('authors')
                            if author:
                                author = author[0]['name']
                            rating = el.get('rating')
                            if rating:
                                rating = rating.get('rating')
                                voters = rating.get('voters')
                            work_id = el.get('work_id')
                            work_name = el.get('work_name') or el.get('work_name_orig')
                            work_type = el.get('work_type')
                            work_year = el.get('work_year')
                            cycles_dict = {'work_id': work_id,
                                           'work_type': work_type,
                                           'work_name': work_name,
                                           'author': author,
                                           'rating': rating,
                                           'voters': voters,
                                           'work_year': work_year
                                           }
                            temp.append(cycles_dict)  # list of dicts
                    cycle_list.append(temp)
            if parents.get('digest'):
                digests = parents['digest']
                for subdigest in digests:
                    for el in subdigest:
                        if el.get('work_id'):
                            work_id = el.get('work_id')
                            work_name = el.get('work_name')
                            work_type = el.get('work_type')
                            work_year = el.get('work_year')
                            digest_dict = {'work_id': work_id,
                                           'work_type': work_type,
                                           'work_name': work_name,
                                           'work_year': work_year
                                           }
                            digest_list.append(digest_dict)
            res['cycles'] = cycle_list
            res['digests'] = digest_list
            return res  # dict of parents {'cycles': [[6663, 5835]], 'digests': [530492]}, 6662 is a high cycle,
            # 5835 is a subcycle
        return None

    async def get_children(self):
        res = []

        if self.data.get('children'):
            children = self.data.get('children')
            for child in children:
                if child:
                    voters = None
                    author = child.get('authors')
                    if author:
                        author = author[0]['name']
                    rating = child.get('rating')
                    if rating:
                        voters = rating.get('voters')
                        rating = rating.get('rating')
                    work_id = child.get('work_id')
                    work_name = child.get('work_name') or child.get('work_name_orig')
                    work_type = child.get('work_type')
                    work_year = child.get('work_year')
                    child_dict = {'work_id': work_id,
                                  'work_type': work_type,
                                  'work_name': work_name,
                                  'author': author,
                                  'rating': rating,
                                  'voters': voters,
                                  'work_year': work_year
                                  }
                    res.append(child_dict)  # list of dicts
        return res


class FantlabApi:
    def __init__(self, address=FANTLAB_API_ADDRESS):
        self.address = address or FANTLAB_API_ADDRESS

    @handle_errors
    async def get_work(self, work_id):
        if not work_id:
            return None
        response = requests.get(f"{self.address}/work/{work_id}")
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to get work from Fantlab. Status code: {response.status_code}")

    @handle_errors
    async def work_exists(self, work_id):
        if not work_id:
            return None
        response = requests.get(f"{self.address}/work/{work_id}")
        if response.status_code == 200:
            return True
        else:
            return False

    @handle_errors
    def get_extended_work(self, work_id):
        if not work_id:
            return None
        response = requests.get(f"{self.address}/work/{work_id}/extended")
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to get extended work from Fantlab. Status code: {response.status_code}")

    @handle_errors
    def search_main(self, query):
        if not query:
            return None
        response = requests.get(f"{self.address}/searchmain?q={query}")
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to get work from Fantlab. Status code: {response.status_code}")

    @handle_errors
    async def get_random_work(self, image_on=False):
        while True:
            idx = random.randint(1, 1800000)
            try:
                data = await self.get_work(idx)
                work = Work(data)
                if image_on and not work.image:
                    continue
                if work.desc and work.rating and work.title and \
                        (work.work_type.lower() in ['роман', 'повесть', 'рассказ', 'новелла']):
                    return work
            except Exception as e:
                print('404 in getting a work from Fantlab')
            continue

    @retry(attempts=3)
    async def get_similars(self, work_id):
        if not work_id:
            return None
        response = requests.get(f"{self.address}/work/{work_id}/similars")
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to get extended work from Fantlab. Status code: {response.status_code}")


class BookDatabase:
    """
    General database connector in case we implement other than Fantlab connector
    """

    def __init__(self, database_client):
        self.database_client = database_client
        self.data = None

    async def get_work(self, work_id):
        data = await self.database_client.get_work(work_id)
        if data:
            return Work(data)
        return Work(data)

    async def work_exists(self, work_id):
        return await self.database_client.work_exists(work_id)

    async def get_extended_work(self, work_id):
        data = self.database_client.get_extended_work(work_id)
        # print(data)
        if data:
            return ExtendedWork(data)
        return ExtendedWork(data)

    def search_main(self, query):
        self.data = self.database_client.search_main(query)
        return Search(query, self.data)

    async def get_random_work(self, image_on=False):
        work = await self.database_client.get_random_work(image_on)
        return work

    @retry(attempts=3)
    async def get_similars(self, work_id):
        books = await self.database_client.get_similars(work_id)
        similars_to_add = []
        if books:
            for book in books:
                similar = book['id']
                similars_to_add.append(similar)
        return similars_to_add


class Search:
    def __init__(self, query, search_result):
        self.query = query
        self.search_result = search_result

    def book_list(self):
        """
        Returns the list of book dicts in own format
        """
        if self.search_result:
            return [SearchedWork(book) for book in self.search_result[1]['matches']]
        return []


async def book_list():
    with open('book_list.txt', 'a') as f:
        for x in range(5437, 5500):
            if await service.work_exists(x):
                f.write(str(x) + "\n")
                print(f'Added the {x} to file')
    print('Finished the script')


async def relatives(chat_id=163905035):
    await fant_ext._create_db_pool()
    async with await fant_ext._get_user_connection(163905035) as conn:
        print(datetime.datetime.now().isoformat())

        sql = f"SELECT w_id FROM works"
        lis = await fant_ext.query_db(conn, sql)
        lis = [l[0] for l in lis]
        # index = lis.index(3602)
        # print(index)

        for idx in range(4348, 4350):
        # for idx in lis[5000:]:  # 189 3642
            try:
                work = await service.get_work(idx)
                parent_cycle, digests_cycle, children_cycle = None, None, None
                parents, children = None, None

                if work:
                    work_ext = await service.get_extended_work(idx)
                    print(f"Got the work {idx} - {work_ext.title}")

                    parents = await work_ext.get_parents()
                    if parents:
                        if parents.get('cycles'):
                            cycles = parents.get('cycles')
                            parent_cycle = [[parent['work_id'] for parent in parent_cycle] for parent_cycle in cycles]
                            print('Parents cycles:', parent_cycle)

                        if parents.get('digests'):
                            digests = parents.get('digests')
                            digests_cycle = [digest['work_id'] for digest in digests]
                            print('Digests:', digests_cycle)

                    children = await work_ext.get_children()  # 873
                    if children:
                        children_cycle = [child['work_id'] for child in children]
                        print('Children:', children_cycle)
                    try:
                        await fant_int.update_relatives(conn, idx, parent_cycle, digests_cycle, children_cycle)
                        print("+======================================")

                    except Exception as e:
                        print('Relatives are not updated', e)

            except Exception as e:
                print(f'No work {idx}, exeption: {e}')
                print("+======================================")
    print('Process finished')
    print(datetime.datetime.now().isoformat())


async def similars(chat_id=163905035):
    await connector._create_db_pool()
    #
    sql = f"SELECT w_id FROM works WHERE similars IS NULL"
    lis = await connector.query_db(sql)
    lis = [l[0] for l in lis]
    index = lis.index(3602)
    print(index)
    # sql = f"SELECT similars FROM works WHERE w_id = $1"
    for idx in lis[index:]:
        similar_books = await service.get_similars(idx)
        if similar_books:
            await fant_ext.update_similars(chat_id, idx, similar_books)
            print(f"Updated the similars for {idx}")
        else:
            print(f'No similars for {idx}')
    print('Finished the script')


async def checker(chat_id=163905035):
    await fant_ext._create_db_pool()
    async with await fant_ext._get_user_connection(163905035) as conn:
        print(datetime.datetime.now().isoformat())
        # 3159 no genres
        # 4698 no work
        for idx in range(34000, 36000):
            try:
                work = await service.get_work(idx)
                if work:
                    print(f"Got the work {idx} - {work.title}")

                    stored = await fant_int.store_work(conn, work)
                    if stored:
                        work_ext = await service.get_extended_work(idx)
                        if work_ext:
                            print(f'Got extended work {idx}')
                            genres = work_ext.get_characteristics()
                            if genres:
                                await fant_int.update_work_genres(conn, work_ext.id, genres)
                                print(f'Genres for book {work_ext.id} updated')
                            else:
                                print(f"Book {work_ext.id} isn't classified")

                        similar_books = await service.get_similars(idx)
                        if similar_books:
                            await fant_int.update_similars(conn, idx, similar_books)
                            print(f"Updated the similars for {idx}")
                        else:
                            print(f'No similars for {idx}')

                        parents = await work_ext.get_parents()
                        parent_cycle, digests_cycle = None, None

                        if parents:
                            if parents.get('cycles'):
                                cycles = parents.get('cycles')
                                parent_cycle = [[parent['work_id'] for parent in parent_cycle] for parent_cycle in cycles]
                                print('Parents cycles:', parent_cycle)

                            if parents.get('digests'):
                                digests = parents.get('digests')
                                digests_cycle = [digest['work_id'] for digest in digests]
                                print('Digests:', digests_cycle)

                        children = await work_ext.get_children()
                        children_cycle = None
                        if children:
                            children_cycle = [child['work_id'] for child in children]
                            print('Children:', children_cycle)
                        try:
                            await fant_int.update_relatives(conn, work_ext.id, parent_cycle, digests_cycle, children_cycle)
                            # print(f'Relatives for book {work_ext.id} updated')
                            print("+======================================")
                        except Exception as e:
                            print('Relatives are not updated', e)
                    else:
                        print(f'Work {work.id} is allready PRESENT id DB')
                        print("+======================================")

            except Exception as e:
                print(f'No work {idx}, exeption: {e}')
                print("+======================================")
        print('Process finished')
        print(datetime.datetime.now().isoformat())


if __name__ == '__main__':
    # Initialize the Fantlab_api with the base URL
    api_connect = FantlabApi()
    # Initialize DatabaseConnector with the Fantlabapiclient
    service = BookDatabase(api_connect)

    # update_similars()

    fant_ext = database_work.DatabaseConnector('fantlab', True)

    connector = database_work.DatabaseInteractor(fant_ext)

    # Interactor with the fantlab database, main class for requests
    fant_int = database_work.FantInteractor(fant_ext)

    # asyncio.run(checker())
    # asyncio.run(similars())
    # asyncio.run(book_list())
    asyncio.run(checker())

    # # print(work.get_characteristics())
    # work.print_characteristics()

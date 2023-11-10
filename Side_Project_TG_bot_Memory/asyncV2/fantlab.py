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

    def get_parents(self):
        if self.data.get('parents'):
            res = {'cycles': None, 'digests': None}
            cycle_list = []
            digest_list = []
            parents = self.data['parents']
            if parents.get('cycles'):
                cycles = parents['cycles']
                if cycles:
                    for subcycle in cycles:
                        temp = []
                        for el in subcycle:
                            if el.get('work_id'):
                                temp.append(el['work_id'])
                        cycle_list.append(temp)
            if parents.get('digest'):
                digests = parents['digest']
                if digests:
                    for subdigest in digests:
                        for el in subdigest:
                            if el.get('work_id'):
                                digest_list.append(el['work_id'])
            res['cycles'] = cycle_list
            res['digests'] =digest_list
            return res  # dict of parents {'cycles': [[6663, 5835]], 'digests': [530492]}, 6662 is a high cycle,
            # 5835 is a subcycle
        return None

    def get_children(self):
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
                f.write(str(x)+"\n")
                print(f'Added the {x} to file')
    print('Finished the script')


async def relatives():
    connector.db_pool = await connector._create_db_pool()
    print(datetime.datetime.now().isoformat())

    for idx in range(189, 193):
        try:
            work = await service.get_work(idx)
            if work:
                work_ext = await service.get_extended_work(idx)
                print(f"Got the work {idx} - {work.title}")

                parents = work_ext.get_parents()
                if parents:
                    print(parents)
                # children = work_ext.get_children()  # 873
            #     if parents:
            #         await fant_ext.update_parents(idx, parents)
            #         print(f"Updated the parents for {idx}")
            #     else:
            #         print(f'No parents for {idx}')
            # if children:
            #     await fant_ext.update_children(idx, children)
            #     print(f"Updated the children for {idx}")
            # else:
            #     print(f'No children for {idx}')

        except Exception as e:
            print(f'No work {idx}, exeption: {e}')
            print("+======================================")
    print('Process finished')
    print(datetime.datetime.now().isoformat())



async def similars():
    connector.db_pool = await connector._create_db_pool()
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
            await fant_ext.update_similars(idx, similar_books)
            print(f"Updated the similars for {idx}")
        else:
            print(f'No similars for {idx}')
    print('Finished the script')


async def checker():
    connector.db_pool = await connector._create_db_pool()
    print(datetime.datetime.now().isoformat())
    # 3159 no genres
    # 4698 no work
    for idx in range(6000, 6010):
        try:
            work = await service.get_work(idx)
            if work:
                print(f"Got the work {idx} - {work.title}")

                await fant_ext.store_work(work)
                work_ext = await service.get_extended_work(idx)
                if work_ext:
                    print(f'Got extended work {idx}')
                    genres = work_ext.get_characteristics()
                    if genres:
                        await fant_ext.update_work_genres(work_ext.id, genres)
                        print(f'Genres for book {work_ext.id} updated')
                        print("+======================================")
                    else:
                        print(f"Book {work_ext.id} isn't classified")
                        print("+======================================")

                similar_books = await service.get_similars(idx)
                if similar_books:
                    await fant_ext.update_similars(idx, similar_books)
                    print(f"Updated the similars for {idx}")
                else:
                    print(f'No similars for {idx}')
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

    connector = database_work.DatabaseConnector('fantlab')

    # Interactor with the fantlab database, main class for requests
    fant_ext = database_work.FantInteractor(connector)

    # asyncio.run(checker())
    # asyncio.run(similars())
    # asyncio.run(book_list())
    asyncio.run(relatives())

    # # print(work.get_characteristics())
    # work.print_characteristics()

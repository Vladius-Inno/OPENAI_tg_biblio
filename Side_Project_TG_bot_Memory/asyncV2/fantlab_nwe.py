# -*- coding: utf-8 -*-

import requests
import pprint
import random

FANTLAB_API_ADDRESS = 'https://api.fantlab.ru/'
FANTLAB_ADDRESS = 'https://fantlab.ru/'


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
        self.voters = self.data.get("rating").get("voters") if isinstance(self.data.get("rating"), dict) \
            else self.data.get('rating')[1] if self.data.get('rating') else None
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


class FantlabApi:
    def __init__(self, address=FANTLAB_API_ADDRESS):
        self.address = address or FANTLAB_API_ADDRESS

    @handle_errors
    def get_work(self, work_id):
        if not work_id:
            return None
        response = requests.get(f"{self.address}/work/{work_id}")
        if response.status_code == 200:

            return response.json()
        else:
            raise Exception(f"Failed to get work from Fantlab. Status code: {response.status_code}")

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
    def get_random_work(self, image_on=False):
        while True:
            idx = random.randint(1, 1800000)
            work = Work(self.get_work(idx))
            if image_on and not work.image:
                continue
            if work.desc and work.rating and work.title and \
                    (work.work_type.lower() in ['роман', 'повесть', 'рассказ', 'новелла']):
                return work
            continue


class BookDatabase:
    """
    General database connector in case we implement other than Fantlab connector
    """
    def __init__(self, database_client):
        self.database_client = database_client
        self.data = None

    def get_work(self, work_id):
        data = self.database_client.get_work(work_id)
        if data:
            return Work(data)
        return Work(data)

    def get_extended_work(self, work_id):
        data = self.database_client.get_extended_work(work_id)
        # print(data)
        if data:
            return Work(data)
        return Work(data)

    def search_main(self, query):
        self.data = self.database_client.search_main(query)
        return Search(query, self.data)

    def get_random_work(self, image_on=False):
        work = self.database_client.get_random_work(image_on)
        return work


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


if __name__ == '__main__':
    # Initialize the Fantlab_api with the base URL
    api_connect = FantlabApi()
    # Initialize DatabaseConnector with the Fantlabapiclient
    service = BookDatabase(api_connect)

    # get the work by it's id and print
    # service.get_work(487156).show()

    books = service.search_main('Голдинг').book_list()
    [book.show() for book in books]




# -*- coding: utf-8 -*-

import requests
import pprint

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


class Work:
    def __init__(self, data):
        self.title = data["title"]
        self.author = data["authors"][0]["name"]
        self.id = data["work_id"]
        self.image = FANTLAB_ADDRESS + data["image"] if data["image"] else None
        self.desc = data['work_description']
        self.work_type = data["work_type"]
        self.work_name = data["work_name"]
        self.rating = data["rating"]["rating"]

    def show(self):
        print(f'{self.work_type} {self.work_name}, автор {self.author}')
        pprint.pprint(self.desc)
        print(f'Рейтинг - {self.rating}')
        print(self.image or "Изображение отсутствует")


class FantlabApi:
    def __init__(self, address=FANTLAB_API_ADDRESS):
        self.address = address or FANTLAB_API_ADDRESS

    @handle_errors
    def get_work(self, work_id):
        response = requests.get(f"{self.address}/work/{work_id}")
        if response.status_code == 200:
            return response.json()
        else:
            raise Exception(f"Failed to get work from Fantlab. Status code: {response.status_code}")


class BookDatabase:
    def __init__(self, database_client):
        self.database_client = database_client

    def get_work(self, work_id):
        data = self.database_client.get_work(work_id)
        return Work(data)


if __name__ == '__main__':
    # Initialize the Fantlab_api with the base URL
    api_connect = FantlabApi()
    # Initialize DatabaseConnector with the Fantlabapiclient
    service = BookDatabase(api_connect)

    try:
        # Call FantlabApi method to fetch and process data and call the Work method to show it in stdout
        service.get_work(487156).show()

    except Exception as e:
        print(f"An error occurred: {str(e)}")

# -*- coding: utf-8 -*-

from bs4 import BeautifulSoup
import requests
from fantlab_nwe import FantlabApi, BookDatabase

base_url = "https://fantlab.ru/bygenre?"


def _fetch_html(url_string):
    # Send an HTTP GET request to the URL
    response = requests.get(url_string)
    if response.status_code == 200:
        # Get the HTML content
        return response.text
    else:
        print("Failed to retrieve the page. Status code:", response.status_code)
        return None


class FantlabParser:
    def __init__(self):
        pass

    @staticmethod
    def parse_books(url_string, num):
        # parses the num books from the fantlab url
        html_content = _fetch_html(url_string)
        if html_content is None:
            return None
        # Create a BeautifulSoup object
        soup = BeautifulSoup(html_content, 'html.parser')
        # Find all book entries
        book_entries = soup.find_all('tr')  # [3:-1]  # Adjust this to match the actual table structure
        books = []
        # Initialize the Fantlab_api with the base URL
        api_connect = FantlabApi()
        # Initialize DatabaseConnector with the Fantlabapiclient
        service = BookDatabase(api_connect)
        # found books counter
        counter = 0

        for entry in book_entries:
            # if no author, title, rating - drop the entry
            author_tag = entry.find('td')
            if author_tag:
                # Check if an anchor tag exists within the <td> element
                title_tag = author_tag.find('a')
                if title_tag:
                    work_index = title_tag['href'].replace('/work', '')
                else:
                    continue
                rating_tag = entry.find('nobr')
                if not rating_tag:
                    continue
            try:
                books.append(service.get_work(work_index))
                counter += 1
            except Exception as e:
                print(f"An error occurred: {str(e)}")
            if counter >= num:
                break
        return books


if __name__ == "__main__":
    url = base_url + "wg1=on&wg8=on&wg11=on&wg101=on&lang=rus&form"
    # fantasy_parser = FantlabParser()
    books = FantlabParser.parse_books(url, 5)

    if books:
        for i, book in enumerate(books, start=1):
            print(f"Book {i}:")
            print(f"Author: {book.author}")
            print(f"Title: {book.work_name}")
            print(book.image if book.image else "No image")
            print(f"Rating: {book.rating}\n")
    else:
        print("No books found.")

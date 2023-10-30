# -*- coding: utf-8 -*-

import database_work
import fantlab_nwe
import fantlab_page_find


def search_by_string(cursor, string):
    result = database_work.GenreInteractor.multiple_search(cursor, string)
    ids = set()
    # Print the results
    for characteristic, records in result:
        # print(f"Characteristic: {characteristic}")
        for table_name, record in records:
            record_id, parent_id = record
            # print(f"Found in Table: {table_name}, ID: {record_id}, parent_id {parent_id}")
            if record_id:
                ids.add(record_id)
            if parent_id:
                ids.add(parent_id)
    # print(ids)
    return '=on&'.join(list(ids))


if __name__ == "__main__":
    fant_db = database_work.DatabaseConnector('fantlab')
    fant_cursor = fant_db.get_cursor()
    fant_ext = database_work.GenreInteractor(fant_cursor, fant_db.connection)


    input_string = "фэнтези, ужасы, средневековье"

    items = search_by_string(fant_cursor, input_string)
    url = f'https://fantlab.ru/bygenre?form=&{items}' + '=on&'
    print('For the search string', input_string, 'we got the following:')
    print(url)

    fantasy_parser = fantlab_page_find.FantlabParser(url)
    books = fantasy_parser.parse_books(5)

    if books:
        for i, book in enumerate(books, start=1):
            print(f"Book {i}:")
            print(f"Author: {book.author}")
            print(f"Title: {book.work_name}")
            print(book.image if book.image else "No image")
            print(f"Rating: {book.rating}\n")
    else:
        print("No books found.")

    fant_db.close_connection()

# TODO make different searches

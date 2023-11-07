# -*- coding: utf-8 -*-

import database_work
import fantlab_nwe
import fantlab_page_find


async def search_by_string(cursor, string):
    result = await database_work.FantInteractor.multiple_search(cursor, string)
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
    fant_ext = database_work.FantInteractor(fant_db)

    input_string = "фантастика, бластеры"

    items = search_by_string(fant_ext, input_string)
    url = f'https://fantlab.ru/bygenre?form=&{items}' + '=on&'
    print('For the search string', input_string, 'we got the following:')
    print(url)

    books = await fantlab_page_find.FantlabParser.parse_books(url, 5)
    fantlab_nwe.print_books(books)

    fant_db.close_db_pool()

# TODO make different searches

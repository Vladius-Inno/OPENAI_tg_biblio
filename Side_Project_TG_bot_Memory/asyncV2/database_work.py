# -*- coding: utf-8 -*-

import psycopg2
import os
import json

# for checking
import fantlab_nwe

host_name = os.environ['host_name']
user_name = os.environ['user_name']
password = os.environ['password']

SUBSCRIPTION_DATABASE = 'subscriptions'
MESSAGES_DATABASE = 'messages'
OPTIONS_DATABASE = 'options'

DEFAULT_ROLE = 'default_role'

WORKS_DATABASE = 'works'


def handle_database_errors(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except (Exception, psycopg2.DatabaseError) as e:
            # Handle the database connection error here
            print(f"Database error: {e}")
            # You can log the error, retry the connection, or perform other actions as needed
            # You might want to raise an exception or return a specific value here
            return None  # For demonstration purposes, return None in case of an error

    return wrapper


class DatabaseConnector:
    def __init__(self, database, test=False):
        self.test = test
        self.tables = []
        self._setup()
        self.connection = None
        self.database = database+"_test" if test else database
        print(f'Connection to {self.database} initiated')

    def _setup(self):
        self.tables = [SUBSCRIPTION_DATABASE, MESSAGES_DATABASE, OPTIONS_DATABASE]
        if self.test:
            self.tables = [element.strip('.db') + '_test' for element in self.tables]

    def open_connection(self, database=None):
        database = database or self.database
        try:
            conn = psycopg2.connect(
                host=host_name,
                database=database,
                user=user_name,
                password=password)
        except (Exception, psycopg2.DatabaseError) as error:
            print(error)
            conn = None
        self.connection = conn
        print(f'Connection to {self.database} set up')

    def get_cursor(self):
        # table = table.strip('.db')
        # if self.test:
        #     table += '_test'
        if not self.connection:
            self.open_connection()
        conn = self.connection
        # create a cursor
        cur = conn.cursor()
        return cur or None

    def close_connection(self):
        if self.connection is not None:
            self.connection.close()
            print(f'Connection to {self.database} closed.')


class DatabaseInteractor:
    def __init__(self, cursor, conn, table=None, test=False):
        self.table = table.strip('.db') + '_test' if test else table.strip('.db') if table else None
        self.test = test
        self.cursor = cursor
        self.conn = conn


class OptionsInteractor(DatabaseInteractor):
    def __init__(self, cursor, conn, table='options', test=False):
        super().__init__(cursor, conn, table, test)

    @handle_database_errors
    def check_role(self, chat_id):
        # get the gpt_role
        self.cursor.execute(f"SELECT gpt_role FROM {self.table} WHERE chat_id = %s", (chat_id,))
        try:
            gpt_role = self.cursor.fetchone()[0]
        except Exception:
            gpt_role = DEFAULT_ROLE
        return gpt_role

    @handle_database_errors
    def setup_role(self, chat_id, role):
        self.cursor.execute(f"UPDATE {self.table} SET gpt_role = %s WHERE chat_id = %s", (role, chat_id))
        self.conn.commit()

    @handle_database_errors
    def options_exist(self, chat_id):
        # Execute a query to retrieve the user by chat_id
        self.cursor.execute(f'SELECT * FROM {self.table} WHERE chat_id = %s', (chat_id,))
        if self.cursor.fetchone():
            return True
        return False

    @handle_database_errors
    def set_user_option(self, chat_id):
        # Add a new user option record
        self.cursor.execute(f"INSERT INTO {self.table} (chat_id, gpt_role) "
                            "VALUES (%s, %s)", (chat_id, DEFAULT_ROLE))
        self.conn.commit()


class MessagesInteractor(DatabaseInteractor):
    def __init__(self, cursor, conn, table=MESSAGES_DATABASE, test=False):
        super().__init__(cursor, conn, table, test)

    @handle_database_errors
    def insert_message(self, chat_id, text, role, subscription_status, timestamp):
        self.cursor.execute(f"INSERT INTO {self.table} (timestamp, chat_id, role, message, subscription_status) "
                            "VALUES (%s, %s, %s, %s, %s)",
                            (timestamp, chat_id, role, text, subscription_status))
        self.conn.commit()

    @handle_database_errors
    def get_last_messages(self, chat_id, amount):
        self.cursor.execute(f"SELECT chat_id, role, message FROM {self.table} WHERE chat_id = %s AND CLEARED = 0 "
                            f"ORDER BY timestamp DESC LIMIT {amount}", (chat_id,))
        return self.cursor.fetchall()

    @handle_database_errors
    def check_message_limit(self, chat_id, subscription_status, start_of_day_timestamp):
        self.cursor.execute(f'SELECT COUNT(*) FROM {self.table} WHERE chat_id = %s AND role = %s AND '
                            f'subscription_status = %s '
                            'AND timestamp > %s',
                            (chat_id, 'user', subscription_status, start_of_day_timestamp))
        return self.cursor.fetchone()[0]

    @handle_database_errors
    def clear_messages(self, chat_id):
        self.cursor.execute(f'UPDATE {self.table} SET cleared = 1 WHERE chat_id = %s', (chat_id,))
        self.conn.commit()


class SubscriptionsInteractor(DatabaseInteractor):
    def __init__(self, cursor, conn, table=SUBSCRIPTION_DATABASE, test=False):
        super().__init__(cursor, conn, table, test)

    @handle_database_errors
    def get_free_messages(self, chat_id):
        # get the bonus free messages if exist
        self.cursor.execute(f"SELECT bonus_count FROM {self.table} WHERE chat_id = %s", (chat_id,))
        return self.cursor.fetchone()[0]

    @handle_database_errors
    def get_expiration_date(self, chat_id):
        # Retrieve the expiration date for the user
        self.cursor.execute(f"SELECT expiration_date FROM {self.table} WHERE chat_id = %s", (chat_id,))
        return self.cursor.fetchone()[0]

    @handle_database_errors
    def get_referral(self, chat_id):
        # Get a referral link from the database
        self.cursor.execute(f"SELECT referral_link FROM {self.table} WHERE chat_id = %s", (chat_id,))
        return self.cursor.fetchone()[0]

    @handle_database_errors
    def get_subscription(self, chat_id):
        # Get the subscription status, start date, and expiration date for the user
        self.cursor.execute(
            f"SELECT subscription_status, start_date, expiration_date FROM {self.table} WHERE chat_id = %s",
            (chat_id,))
        return self.cursor.fetchone()

    @handle_database_errors
    def user_exists(self, chat_id):
        # Execute a query to retrieve the user by chat_id
        self.cursor.execute(f'SELECT * FROM {self.table} WHERE chat_id = %s', (chat_id,))
        if self.cursor.fetchone():
            return True
        return False

    @handle_database_errors
    def referred_by(self, chat_id):
        self.cursor.execute(f"SELECT referred_by FROM {self.table} WHERE chat_id = %s", (chat_id,))
        return self.cursor.fetchone()[0]

    @handle_database_errors
    def add_referree(self, referree, chat_id):
        self.cursor.execute(f"UPDATE {self.table} SET referred_by = %s WHERE chat_id = %s", (referree, chat_id))
        self.conn.commit()

    @handle_database_errors
    def add_referral_bonus(self, referree, referral_bonus):
        # Execute the SQL query to increment the bonus count
        self.cursor.execute(f"UPDATE {self.table} SET bonus_count = bonus_count + {referral_bonus} WHERE chat_id = %s",
                            (referree,))
        self.conn.commit()

    @handle_database_errors
    def decrease_free_messages(self, chat_id, amount):
        # Execute the SQL query to decrement the free messages count
        self.cursor.execute(f"UPDATE {self.table} SET bonus_count = bonus_count - {amount} WHERE chat_id = %s",
                            (chat_id,))
        # Commit the changes to the database
        self.conn.commit()

    @handle_database_errors
    def add_new_user(self, user_id, revealed_date, referral_link):
        # Add a new user with default subscription status, start date, and expiration date
        self.cursor.execute(f"INSERT INTO {self.table} (chat_id, subscription_status, revealed_date, referral_link) "
                            "VALUES (%s, 0, %s, %s)", (user_id, revealed_date, referral_link))
        self.conn.commit()

    @handle_database_errors
    def update_subscription_status(self, chat_id, subscription_status, start_date, expiration_date):
        # Set the start and expiration dates for the user's subscription
        self.cursor.execute(f"UPDATE {self.table} SET subscription_status = %s, start_date = %s, expiration_date = %s "
                            f"WHERE chat_id = %s", (subscription_status, start_date, expiration_date, chat_id))
        self.conn.commit()


class FantInteractor(DatabaseInteractor):
    tables_default = ["characteristics", "age", "genres", "linearity", "place", "plot",
                      "time"]  # Replace with your table names

    def __init__(self, cursor, conn):
        super().__init__(cursor, conn)
        self.table = WORKS_DATABASE

    @staticmethod
    @handle_database_errors
    def multiple_search(cursor, input_string, tables=None):
        # Split the input string into individual characteristics
        characteristics = [char.strip() for char in input_string.split(',')]
        # Define a list of table names to search
        table_names = tables or FantInteractor.tables_default
        # Dictionary to store results
        result_dict = {}
        # Iterate through each characteristic and search in each table
        for characteristic in characteristics:
            for table_name in table_names:
                # print(f'Searching "{characteristic}" in "{table_name}"')
                # Replace "column_name" with the column you want to search in
                query = f"SELECT wg_id, parent_id FROM {table_name} WHERE name ILIKE %s"
                # query = f"SELECT wg_id, parent_id FROM {table_name} WHERE to_tsvector('russian', name) @@
                # to_tsquery('russian', %s)"
                cursor.execute(query, [f"%{characteristic}%"])
                records = cursor.fetchall()
                if records:
                    # print('Got the match:')
                    if characteristic in result_dict:
                        result_dict[characteristic].append((table_name, records[0]))
                        # print(records[0])
                    else:
                        result_dict[characteristic] = [(table_name, records[0])]
        return result_dict.items()

    @handle_database_errors
    def store_work(self, work):
        data_json = json.dumps(work.data)
        self.cursor.execute(f"INSERT INTO {self.table} (wg_id, work_json) VALUES (%s, %s)",
                            (work.id, data_json))
        self.conn.commit()
        return "ok"

    @handle_database_errors
    def get_work_db(self, work_id):
        self.cursor.execute(f"SELECT work_json FROM {self.table} WHERE wg_id = %s", (str(work_id), ))
        result = self.cursor.fetchone()
        if result:
            data_json = result[0]
            print(data_json)
        else:
            return None
        return fantlab_nwe.Work(data_json)


if __name__ == '__main__':
    # mess_db = DatabaseConnector('messages', test=True)
    # cursor = mess_db.get_cursor()
    # opt_ext = OptionsInteractor(cursor, mess_db.connection, test=True)

    # Connector to the fantlab database
    fant_db = DatabaseConnector('fantlab')
    # Cursor the fantlab database
    fant_cursor = fant_db.get_cursor()
    # Interactor with the fantlab database, main class for requests
    fant_ext = FantInteractor(fant_cursor, fant_db.connection)

    # input_string = "фантастика, вампиры, европейский сеттинг"
    # result = FantInteractor.multiple_search(fant_cursor, input_string)
    # ids = set()
    # # Print the results
    # for characteristic, records in result:
    #     # print(f"Characteristic: {characteristic}")
    #     for table_name, record in records:
    #         record_id, parent_id = record
    #         # print(f"Found in Table: {table_name}, ID: {record_id}, parent_id {parent_id}")
    #         if record_id:
    #             ids.add(record_id)
    #         if parent_id:
    #             ids.add(parent_id)
    # # print(ids)
    # items = '=on&'.join(list(ids))
    # string = f'https://fantlab.ru/bygenre?form=&{items}' + '=on&'
    # print(string)

    work_id = 1
    # Initialize the Fantlab_api with the base URL
    api_connect = fantlab_nwe.FantlabApi()
    # Initialize DatabaseConnector with the Fantlabapiclient
    service = fantlab_nwe.BookDatabase(api_connect)

    # get the work by it's id and print
    # work = service.get_work(487156)
    # work.show()
    # store the work in the db
    # fant_ext.store_work(work)

    # books = service.search_main('Голдинг').book_list()
    # [book.show() for book in books]

    # make the func for that in main
    work = fant_ext.get_work_db(work_id)
    if not work:
        work = service.get_work(work_id)
        fant_ext.store_work(work)
    work.show()

    # Close the fantlab connection
    fant_db.close_connection()

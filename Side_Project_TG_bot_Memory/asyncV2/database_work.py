import psycopg2
import os

host_name = os.environ['host_name']
user_name = os.environ['user_name']
password = os.environ['password']

SUBSCRIPTION_DATABASE = 'subscriptions'
MESSAGES_DATABASE = 'messages'
OPTIONS_DATABASE = 'options'

DEFAULT_ROLE = 'default_role'


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
    def __init__(self, test=False):
        self.test = test
        self.tables = []
        self._setup()
        print('Connection initiated, list of tables:', self.tables)
        self.connection = None
        self.database = 'messages_test' if test else 'messages'

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
        print('Connection set up')

    def get_cursor(self, table):
        table = table.strip('.db')
        if self.test:
            table += '_test'
        if not self.connection:
            self.open_connection()
        conn = self.connection
        # create a cursor
        cur = conn.cursor()
        return cur or None

    def close_connection(self):
        if self.connection is not None:
            self.connection.close()
            print('Database connection closed.')


class DatabaseInteractor:
    def __init__(self, cursor, conn, table, test=False):
        self.table = table.strip('.db') + '_test' if test else table.strip('.db')
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
    def get_refferal(self, chat_id):
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


if __name__ == '__main__':
    db = DatabaseConnector(test=True)
    cursor_options = db.get_cursor(OPTIONS_DATABASE)
    opt_ext = OptionsInteractor(cursor_options, db.connection, test=True)

    print(opt_ext.check_role(374458904))

    db.close_connection()

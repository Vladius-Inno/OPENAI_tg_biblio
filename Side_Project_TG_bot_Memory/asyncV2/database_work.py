# -*- coding: utf-8 -*-

import asyncpg
import os
import json
import asyncio
# for checking
import fantlab

host_name = os.environ['host_name']
user_name = os.environ['user_name']
password = os.environ['password']

SUBSCRIPTION_DATABASE = 'subscriptions'
MESSAGES_DATABASE = 'messages'
OPTIONS_DATABASE = 'options'

DEFAULT_ROLE = 'default_role'

WORKS_DATABASE = 'works'
WORK_GENRES = "work_genres"
USER_ACTIONS = "user_actions"



def handle_database_errors(func):
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        # except (Exception, psycopg2.DatabaseError) as e:
        except (Exception,  asyncpg.exceptions.PostgresError) as e:
            # Handle the database connection error here

            # Database error: cursor already closed

            print(f"Database error: {e}")
            # You can log the error, retry the connection, or perform other actions as needed
            # You might want to raise an exception or return a specific value here
            return None  # For demonstration purposes, return None in case of an error

    return wrapper


class DatabaseConnector:
    def __init__(self, database, test=False):
        self.test = test
        self.tables = []
        # self.connection = None
        self.db_pool = None
        self.database = database
        self._setup()

    def _setup(self):
        self.tables = [OPTIONS_DATABASE, MESSAGES_DATABASE, SUBSCRIPTION_DATABASE]
        if self.test:
            self.tables = [element.strip('.db') + '_test' for element in self.tables]
        # self.db_pool = asyncio.run(self._create_db_pool())
        print(f'Setup of {self.database} created')

    @handle_database_errors
    async def _create_db_pool(self):
        self.db_pool = await asyncpg.create_pool(
            user=user_name, password=password,
            host=host_name, database=self.database,
            min_size=5,  # Minimum number of connections
            max_size=50  # Maximum number of connections
        )
        print('Created the pool')
        # return db_pool

    @handle_database_errors
    async def _close_db_pool(self):
        await self.db_pool.close()
        print("Pool closed")

    @handle_database_errors
    async def execute_query(self, conn, sql, *params):
        async with conn.transaction():
            await conn.execute(sql, *params)

    @handle_database_errors
    async def executemany_query(self, conn, sql, *params):
        async with conn.transaction():
            await conn.executemany(sql, *params)

    @handle_database_errors
    async def query_db(self, conn, sql, *params, method='fetchall'):
        print("SQL:", sql, params)
        # print(conn)
        result = await conn.fetch(sql, *params)
        print('Fetched')
        if method == 'fetchall':
            return result
        elif method == 'fetchone':
            return result[0] if result else None

        elif method == 'execute':
            return None
        else:
            raise ValueError("Invalid method parameter")

    # the manager of queries, sends the request to one of the functions
    @handle_database_errors
    async def db_query(self, conn, sql, *params, method='fetchall'):
        if method == 'execute':
            await self.execute_query(conn, sql, *params)
        elif method == 'executemany':
            await self.executemany_query(conn, sql, *params)
        else:
            return await self.query_db(conn, sql, *params, method=method)

    @handle_database_errors
    async def _get_user_connection(self, chat_id):
        element = UserDBConnection(self.db_pool, chat_id)
        return element


class UserDBConnection:
    def __init__(self, db_pool, chat_id):
        self.db_pool = db_pool
        self.chat_id = chat_id
        self.connection = None

    @handle_database_errors
    async def __aenter__(self):
        self.connection = await self.db_pool.acquire()
        return self.connection

    @handle_database_errors
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.db_pool.release(self.connection)
        self.connection = None


class DatabaseInteractor:
    def __init__(self, connector):
        # self.table = table.strip('.db') + '_test' if test else table.strip('.db') if table else None
        self.tables = connector.tables
        # self.test = test
        self.connector = connector

# class OptionsInteractor(DatabaseInteractor):
#     def __init__(self, connector, table='options', test=False):
#         super().__init__(connector, table, test)

    @handle_database_errors
    async def check_role(self, conn, chat_id):
        # get the gpt_role
        sql = f"SELECT gpt_role FROM {self.tables[0]} WHERE chat_id = $1"
        try:
            gpt_role = await self.connector.db_query(conn, sql, chat_id, method='fetchone')
            gpt_role = gpt_role.get('gpt_role')
        except Exception as e:
            print("Role bug:", e)
            gpt_role = DEFAULT_ROLE
        return gpt_role

    @handle_database_errors
    async def setup_role(self, conn, chat_id, role):
        sql = f"UPDATE {self.tables[0]} SET gpt_role = $1 WHERE chat_id = $2"
        await self.connector.db_query(conn, sql, role, chat_id, method='execute')

    @handle_database_errors
    async def options_exist(self, conn, chat_id):
        # Execute a query to retrieve the user by chat_id
        sql = f'SELECT * FROM {self.tables[0]} WHERE chat_id = $1'
        if await self.connector.db_query(conn, sql, chat_id, method='fetchone'):
            return True
        return False

    @handle_database_errors
    async def set_user_option(self, conn, chat_id):
        # Add a new user option record
        sql = f"INSERT INTO {self.tables[0]} (chat_id, gpt_role) VALUES ($1, $2)"
        await self.connector.db_query(conn, sql, chat_id, DEFAULT_ROLE, method='execute')

# class MessagesInteractor(DatabaseInteractor):
#     def __init__(self, connector, table=MESSAGES_DATABASE, test=False):
#         super().__init__(connector, table, test)

    @handle_database_errors
    async def insert_message(self, conn, chat_id, text, role, subscription_status, timestamp):
        sql = f"INSERT INTO {self.tables[1]} (timestamp, chat_id, role, message, subscription_status) VALUES ($1, $2, $3, " \
              f"$4, $5) "
        await self.connector.db_query(conn, sql, timestamp, chat_id, role, text, subscription_status, method='execute')

    @handle_database_errors
    async def get_last_messages(self, conn, chat_id, amount):
        sql = f"SELECT chat_id, role, message FROM {self.tables[1]} WHERE chat_id = $1 AND CLEARED = 0 ORDER BY timestamp " \
              f"DESC LIMIT {amount} "
        result = await self.connector.db_query(conn, sql, chat_id, method='fetchall')
        return [(message['chat_id'], message['role'], message['message']) for message in result]

    # TODO check if it returns the integer
    @handle_database_errors
    async def check_message_limit(self, conn, chat_id, subscription_status, start_of_day_timestamp):
        sql = f'SELECT COUNT(*) FROM {self.tables[1]} WHERE chat_id = $1 AND role = $2 AND subscription_status = $3 AND ' \
              f'timestamp > $4 '
        res = await self.connector.db_query(conn, sql, chat_id, 'user', subscription_status, start_of_day_timestamp,
                                            method='fetchone')
        return res[0]

    @handle_database_errors
    async def clear_messages(self, conn, chat_id):
        sql = f'UPDATE {self.tables[1]} SET cleared = 1 WHERE chat_id = $1'
        await self.connector.db_query(conn, sql, chat_id, method='execute')

# class SubscriptionsInteractor(DatabaseInteractor):
#     def __init__(self, connector, table=SUBSCRIPTION_DATABASE, test=False):
#         super().__init__(connector, table, test)

    @handle_database_errors
    async def get_free_messages(self, conn, chat_id):
        # get the bonus free messages if exist
        sql = f"SELECT bonus_count FROM {self.tables[2]} WHERE chat_id = $1"
        res = await self.connector.db_query(conn, sql, chat_id, method='fetchone')
        return res[0]

    @handle_database_errors
    async def get_expiration_date(self, conn, chat_id):
        # Retrieve the expiration date for the user
        sql = f"SELECT expiration_date FROM {self.tables[2]} WHERE chat_id = $1"
        res = await self.connector.db_query(conn, sql, chat_id, method='fetchone')
        return res[0]

    @handle_database_errors
    async def get_referral(self, conn, chat_id):
        # Get a referral link from the database
        sql = f"SELECT referral_link FROM {self.tables[2]} WHERE chat_id = $1"
        res = await self.connector.db_query(conn, sql, chat_id, method='fetchone')
        return res[0]

    @handle_database_errors
    async def get_subscription(self, conn, chat_id):
        # Get the subscription status, start date, and expiration date for the user
        sql = f"SELECT subscription_status, start_date, expiration_date FROM {self.tables[2]} WHERE chat_id = $1"
        result = await self.connector.db_query(conn, sql, chat_id, method='fetchone')
        return (result.get('subscription_status'), result.get('start_date'), result.get('expiration_date'))

    @handle_database_errors
    async def user_exists(self, conn, chat_id):
        sql = f'SELECT * FROM {self.tables[2]} WHERE chat_id = $1'
        # Execute a query to retrieve the user by chat_id
        if await self.connector.db_query(conn, sql, chat_id, method='fetchone'):
            return True
        return False

    @handle_database_errors
    async def referred_by(self, conn, chat_id):
        sql = f"SELECT referred_by FROM {self.tables[2]} WHERE chat_id = $1"
        res = await self.connector.db_query(conn, sql, chat_id, method='fetchone')
        return res[0]

    @handle_database_errors
    async def add_referree(self, conn, referree, chat_id):
        sql = f"UPDATE {self.tables[2]} SET referred_by = $1 WHERE chat_id = $2"
        await self.connector.db_query(conn, sql, referree, chat_id, method='execute')

    @handle_database_errors
    async def add_referral_bonus(self, conn, referree, referral_bonus):
        # Execute the SQL query to increment the bonus count
        sql = f"UPDATE {self.tables[2]} SET bonus_count = bonus_count + {referral_bonus} WHERE chat_id = $1"
        await self.connector.db_query(conn, sql, referree, method='execute')

    @handle_database_errors
    async def decrease_free_messages(self, conn, chat_id, amount):
        # Execute the SQL query to decrement the free messages count
        sql = f"UPDATE {self.tables[2]} SET bonus_count = bonus_count - {amount} WHERE chat_id = $1"
        await self.connector.db_query(conn, sql, chat_id, method='execute')

    @handle_database_errors
    async def add_new_user(self, conn, user_id, revealed_date, referral_link):
        # Add a new user with default subscription status, start date, and expiration date
        sql = f"INSERT INTO {self.tables[2]} (chat_id, subscription_status, revealed_date, referral_link) VALUES ($1, 0, " \
              f"$2, $3) "
        await self.connector.db_query(conn, sql, user_id, revealed_date, referral_link, method='execute')

    @handle_database_errors
    async def update_subscription_status(self, conn, chat_id, subscription_status, start_date, expiration_date):
        # Set the start and expiration dates for the user's subscription
        sql = f"UPDATE {self.tables[2]} SET subscription_status = $1, start_date = $2, expiration_date = $3 WHERE chat_id " \
              f"= $4 "
        await self.connector.db_query(conn, sql, subscription_status, start_date, expiration_date, chat_id, method='execute')

    @handle_database_errors
    async def get_recommendation(self, conn, chat_id):
        select_query = """
                   WITH highest_scored_book AS (
                       SELECT
                           rb.work_id
                       FROM
                           recommended_books rb
                       WHERE
                           rb.chat_id = $1
                           AND NOT EXISTS (
                               SELECT 1
                               FROM user_actions ua
                               WHERE ua.chat_id = $1
                                   AND ua.w_id = rb.work_id
                                   AND ua.action_type IN ('like', 'dislike', 'rate')
                           )
                       ORDER BY
                           rb.score DESC
                       LIMIT 1
                   )
                   SELECT work_id FROM highest_scored_book;
               """

        # Query to delete the selected book from recommended_books
        delete_query = """
                DELETE FROM recommended_books
                WHERE chat_id = $1 AND work_id = $2;
               """
        recommendation = await self.connector.db_query(conn, select_query, chat_id, method='fetchone')
        if recommendation:
            recommendation_id = recommendation[0]
            print(f"Recommendation for {chat_id} is the book {recommendation_id}!")
            await self.connector.db_query(conn, delete_query, chat_id, recommendation_id, method='execute')
            print(f'Book {recommendation_id} DELETED from recommendations')
            return recommendation_id

    @handle_database_errors
    async def get_work_db(self, conn, work_id):
        sql = f"SELECT work_json FROM works WHERE w_id = $1"
        result = await self.connector.db_query(conn, sql, work_id, method='fetchone')
        if result:
            data_json = json.loads(result['work_json'])
            # print(data_json)
        else:
            return None
        return fantlab.Work(data_json)

    async def update_pref_score(self, conn, chat_id, work_id, pref, rate_digit=None):

        if pref == 'like':
            sql = """
                -- Get the corresponding genres for the liked book
                UPDATE user_prefs
                SET pref_score = CASE
                    WHEN pref_score < 1 THEN pref_score + 0.05 * (1 - ABS(pref_score))
                    ELSE pref_score
                END
                FROM work_genres
                WHERE user_prefs.wg_id = work_genres.genre_id
                    AND user_prefs.chat_id = $1
                    AND work_genres.w_id = $2
            """
            try:
                await self.connector.db_query(conn, sql, chat_id, work_id, method='execute')
                print('Prefs were increased')
            except Exception as e:
                print('Could not update user prefs', e)

        elif pref == 'dislike':
            sql = """
                -- Get the corresponding genres for the disliked book
                UPDATE user_prefs
                SET pref_score = CASE
                    WHEN pref_score < 1 THEN pref_score - 0.05 * (1 - ABS(pref_score))
                    ELSE pref_score
                END
                FROM work_genres
                WHERE user_prefs.wg_id = work_genres.genre_id
                    AND user_prefs.chat_id = $1
                    AND work_genres.w_id = $2
            """
            try:
                await self.connector.db_query(conn, sql, chat_id, work_id, method='execute')
                print('Prefs were decreased')
            except Exception as e:
                print('Could not update user prefs', e)

        elif pref == 'rate':
            sql = """
                -- Get the corresponding genres for the rated book
                UPDATE user_prefs
                SET pref_score = CASE
                    WHEN pref_score < 1 THEN pref_score + 0.02 * (-5.5 + $3) * (1 - ABS(pref_score))
                    ELSE pref_score
                END
                FROM work_genres
                WHERE user_prefs.wg_id = work_genres.genre_id
                    AND user_prefs.chat_id = $1
                    AND work_genres.w_id = $2
            """
            try:
                await self.connector.db_query(conn, sql, chat_id, work_id, rate_digit, method='execute')
                print('Prefs were changed by the rate')
            except Exception as e:
                print('Could not update user prefs', e)

        else:
            return
        return

    async def get_best_prefs(self, conn, chat_id):
        sql = """
            SELECT
                user_prefs.chat_id,
                genre.name,
                user_prefs.pref_score
            FROM
                user_prefs
            JOIN genre ON user_prefs.wg_id = genre.wg_id
            WHERE
                user_prefs.chat_id = $1
            ORDER BY pref_score DESC
        """
        result = await self.connector.db_query(conn, sql, chat_id, method='fetchall')
        print('\n'.join([f"{a['name']} - " + "{:.3f}".format(a["pref_score"]) for a in result]))


class FantInteractor(DatabaseInteractor):
    tables_default = ["genre"]  # Replace with your table names

    def __init__(self, connector, test=False):
        super().__init__(connector)
        self.table = WORKS_DATABASE
        self.work_genre_table = WORK_GENRES
        self.user_actions_table = USER_ACTIONS

    # TODO refacrot because of fetched records format
    @handle_database_errors
    async def multiple_search(self, conn, chat_id, input_string, tables=None):
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
                sql = f"SELECT wg_id, parent_id FROM {table_name} WHERE name ILIKE %s"
                # query = f"SELECT wg_id, parent_id FROM {table_name} WHERE to_tsvector('russian', name) @@
                # to_tsquery('russian', %s)"\
                records = await self.connector.db_query(conn, sql, [f"%{characteristic}%"], method='fetchall')
                if records:
                    # print('Got the match:')
                    if characteristic in result_dict:
                        result_dict[characteristic].append((table_name, records[0]))
                        # print(records[0])
                    else:
                        result_dict[characteristic] = [(table_name, records[0])]
        return result_dict.items()

    @handle_database_errors
    async def work_in_db(self, conn, work):
        # if the work is given - extract the id
        # print(type(work))
        # print(type(fantlab.Work))
        try:
        # if str(type(work)) == "<class '__main__.Work'>":
        #     print('is an instance')
            work = work.id
            print(f'Checking if {work} in DB')
        except Exception as e:
            print('Problem with work id')
        sql = f"SELECT 1 FROM {self.table} WHERE w_id = $1 LIMIT 1"
        result = await self.connector.db_query(conn, sql, work, method='fetchone')
        if result and result[0]:
            print('Book exists in DB')
            return True
        return False

    @handle_database_errors
    async def store_work(self, conn, work):
        if await self.work_in_db(conn, work):
            return False
        data_json = json.dumps(work.data)
        sql = f"INSERT INTO {self.table} (w_id, work_json, image, type) VALUES ($1, $2, $3, $4)"
        await self.connector.db_query(conn, sql, work.id, data_json, work.image, work.work_type, method='execute')
        print(f"Book {work.id} stored in DB")
        return True

    @handle_database_errors
    async def update_work_genres(self, conn, work_id, genres: list):
        sql = f"INSERT INTO {self.work_genre_table} (w_id, genre_id, genre_weight, weight_voters) VALUES ($1, $2, $3, $4)"
        await self.connector.db_query(conn, sql, genres, method='executemany')
        return "ok"

    @handle_database_errors
    async def update_similars(self, conn, work_id, similars: list):
        sql = f"UPDATE {self.table} SET similars = $1 WHERE w_id = $2"
        await self.connector.db_query(conn, sql, similars, work_id, method='execute')
        return "ok"

    @handle_database_errors
    async def update_user_prefs(self, conn, chat_id, work_id, pref, rate=None):
        # if one rates the work, we update the previous record with like or dislike
        if rate:
            sql = f"INSERT INTO {self.user_actions_table} (chat_id, w_id, action_type, rate) VALUES ($1, $2, $3, " \
                  f"$4) ON CONFLICT (chat_id, w_id) DO UPDATE SET action_type = $3, rate = $4 WHERE " \
                  f"({self.user_actions_table}.action_type = 'like' OR {self.user_actions_table}.action_type = " \
                  f"'dislike' OR {self.user_actions_table}.action_type = 'no_pref') AND {self.user_actions_table}.rate IS NULL"
            await self.connector.db_query(conn, sql, chat_id, work_id, pref, rate)
            print(f'User {chat_id} preference updated (rated)')
            return

        # if one reverts like or dislike
        if pref in ['unlike', 'undislike', 'unrate']:
            sql = f"INSERT INTO {self.user_actions_table} (chat_id, w_id, action_type, rate) VALUES " \
                  f"($1, $2, 'no_pref', NULL) ON CONFLICT (chat_id, w_id) DO UPDATE " \
                  f"SET action_type = 'no_pref', rate = NULL WHERE {self.user_actions_table}.action_type = 'like' OR " \
                  f"{self.user_actions_table}.action_type = 'dislike' OR {self.user_actions_table}.action_type = 'rate'"
            await self.connector.db_query(conn, sql, chat_id, work_id, method='execute')
            print(f'User {chat_id} preference updated (reverts)')
            return

        # if one is shown the work, likes or dislikes the work
        try:
            sql = f"INSERT INTO {self.user_actions_table} (chat_id, w_id, action_type) VALUES ($1, $2, $3" \
            f") ON CONFLICT (chat_id, w_id) DO UPDATE SET action_type = $3 WHERE " \
            f"{self.user_actions_table}.action_type = 'no_pref'" \
            f" AND {self.user_actions_table}.rate IS NULL"
            await self.connector.db_query(conn, sql, chat_id, work_id, pref)
            print(f'User {chat_id} preference updated (general)')
        except Exception as e:
            print("No update required in the user prefs (general)", e)
            return
        return

    @handle_database_errors
    async def update_recommendations(self, conn, chat_id, work_id, pref, rate_digit):
        # TODO create a reset process for actions "unlike" and so on
        if pref in ['like', 'rate', 'dislike']:
            sql = """
                INSERT INTO recommended_books (chat_id, work_id, score)
                SELECT
                    $2 AS chat_id,
                    similar_works.w_id AS work_id,
                    CASE
                        WHEN ua.action_type = 'like' THEN 0.6
                        WHEN ua.action_type = 'rate' THEN ua.rate::FLOAT / 10.0
                        WHEN ua.action_type = 'dislike' THEN 0.2
                        ELSE 0.0
                    END AS score
                FROM
                    user_actions ua
                JOIN
                    works w ON ua.w_id = w.w_id
                JOIN
                    unnest(w.similars) similar_works(w_id) ON true
                WHERE
                    ua.w_id = $1
                ON CONFLICT (chat_id, work_id) DO UPDATE
                SET
                    score = EXCLUDED.score;
            """
            await self.connector.db_query(conn, sql, work_id, chat_id, method='execute')
            print(f"Recommendations for {chat_id} about the book {work_id} inserted successfully!")

        elif pref in ['unrate', 'unlike', 'undislike']:
            sql = """
            DELETE FROM recommended_books
            WHERE chat_id = $2 AND work_id IN (
                SELECT similar_works.w_id
                FROM user_actions ua
                JOIN works w ON ua.w_id = w.w_id
                JOIN unnest(w.similars) similar_works(w_id) ON true
                WHERE ua.w_id = $1
            );
            """
            await self.connector.db_query(conn, sql, work_id, chat_id, method='execute')
            print(f"Recommendations for {chat_id} about the book {work_id} deleted successfully!")


    # @handle_database_errors
    # async def delete_recommendations(self, conn, chat_id, work_id):
    #     sql_code = """
    #         DELETE FROM recommended_books
    #         WHERE chat_id = $2 AND work_id IN (
    #             SELECT similar_works.w_id
    #             FROM user_actions ua
    #             JOIN works w ON ua.w_id = w.w_id
    #             JOIN unnest(w.similars) similar_works(w_id) ON true
    #             WHERE ua.w_id = $1
    #         );
    # """
    #     await self.connector.db_query(conn, sql_code, work_id, chat_id, method='execute')
    #     print(f"Recommendations for {chat_id} about the book {work_id} updated successfully!")



async def checker():
    fant_db.db_pool = await fant_db._create_db_pool()
    while True:
        try:
            role = await opt_ext.check_role(163905035)
            print(role)
            # messages = await mess_ext.get_last_messages(163905035, 3)
            # print(messages)
            # await opt_ext.setup_role(163905035, "default_role")
            await asyncio.sleep(5)
            s = await subs_ext.get_subscription(163905035)
            print(s)
        except KeyboardInterrupt:
            print('Stopping')
        # finally:
        #     await fant_db.close_db_pool()


# the initial population for the recomendations
def update_similars():
    import psycopg2

    # Connect to the PostgreSQL database
    with psycopg2.connect(
            host=host_name,
            database="fantlab",
            user=user_name,
            password=password
    ) as conn:

        # Create a cursor object to interact with the database
        with conn.cursor() as cur:
            try:
                # Execute your SQL query
                cur.execute("""
                    insert into recommended_books (chat_id, work_id, score)
                    select
                    ua.chat_id,
                    coalesce(bs.similars, ua.w_id) as work_id,
                    case
                    when ua.action_type = 'like' then 0.6
                    when ua.action_type = 'rate' then
                                CASE
                                    WHEN ua.rate >= 6 THEN ua.rate::float / 10.0
                                    ELSE NULL -- Handle other cases as needed
                                END
                    else null
                    end as score
                    from user_actions ua
                    join
                    works b on ua.w_id = b.w_id
                    left join
                    unnest(b.similars) bs(similars)
                    on
                    true
                    where
                    ua.action_type in ('like', 'rate')
                    ON CONFLICT (chat_id, work_id) DO NOTHING;
""")

                # Fetch the results if needed
                results = cur.fetchall()

                # Commit the changes to the database
                conn.commit()

            except Exception as e:
                # Handle any exceptions or errors
                print(f"Error: {e}")


async def work_printer():
    await fant_db._create_db_pool()

    async with await fant_db._get_user_connection(163905035) as conn:
        work = await connector.get_work_db(conn, 5000)
    print(type(work))


async def prefs_printer():
    await fant_db._create_db_pool()
    async with await fant_db._get_user_connection(163905035) as conn:
        await connector.get_best_prefs(conn, 163905035)


if __name__ == '__main__':
    # mess_db = DatabaseConnector('messages', test=True)
    # cursor = mess_db.get_cursor()
    # opt_ext = OptionsInteractor(cursor, mess_db.connection, test=True)

    # Connector to the fantlab database
    fant_db = DatabaseConnector('fantlab', True)
    # update_similars()

    connector = DatabaseInteractor(fant_db)

    # asyncio.run(work_printer())
    asyncio.run(prefs_printer())


    # Executor for the options table
    # opt_ext = OptionsInteractor(fant_db, test=True)
    # mess_ext = MessagesInteractor(fant_db, test=True)
    # subs_ext = SubscriptionsInteractor(fant_db, test=True)

    # asyncio.run(checker())

    # # Cursor the fantlab database
    # fant_cursor = fant_db.get_cursor()
    # # Interactor with the fantlab database, main class for requests
    # fant_ext = FantInteractor(fant_cursor, fant_db.connection)

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
    #
    # # Initialize the Fantlab_api with the base URL
    # api_connect = fantlab_nwe.FantlabApi()
    # # Initialize DatabaseConnector with the Fantlabapiclient
    # service = fantlab_nwe.BookDatabase(api_connect)

    # get the work by it's id and print
    # work = service.get_work(487156)
    # work.show()
    # store the work in the db
    # fant_ext.store_work(work)

    # books = service.search_main('Голдинг').book_list()
    # [book.show() for book in books]

    # work_id = 1800202

    # TODO make the func for that in main
    # work = fant_ext.get_work_db(work_id)
    # if not work:
    #     work = service.get_work(work_id)
    #     fant_ext.store_work(work)
    # work.show()

    # work = service.get_random_work()
    # work.show()
    #
    # # Close the fantlab connection
    # fant_db.close_connection()

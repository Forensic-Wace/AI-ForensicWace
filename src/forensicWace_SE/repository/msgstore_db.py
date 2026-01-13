import sqlite3
from typing import List, Tuple, Any

class SQLiteDB:
    def __init__(self, db_file: str):
        """
        Initialize a new instance of SQLiteDB.

        :param db_file: The path to the SQLite database file.
        """
        self.db_file = db_file
        self.connection = None

    def connect(self):
        """
        Connect to the SQLite database.
        """
        try:
            self.connection = sqlite3.connect(self.db_file)
            print(f"Connected to database: {self.db_file}")
        except sqlite3.Error as e:
            print(f"Error connecting to database: {e}")

    def close(self):
        """
        Close the database connection.
        """
        if self.connection:
            self.connection.close()
            print(f"Closed connection to database: {self.db_file}")

    def execute_query(self, query: str, params: Tuple = ()) -> List[Tuple[Any]]:
        """
        Execute a query and return the results.

        :param query: The SQL query to execute.
        :param params: Optional parameters to bind to the query.
        :return: A list of tuples containing the query results.
        """
        try:
            cursor = self.connection.cursor()
            cursor.execute(query, params)
            results = cursor.fetchall()
            return results
        except sqlite3.Error as e:
            print(f"Error executing query: {e}")
            return []

    def execute_update(self, query: str, params: Tuple = ()) -> int:
        """
        Execute an update or insert statement.

        :param query: The SQL query to execute.
        :param params: Optional parameters to bind to the query.
        :return: The number of rows affected.
        """
        try:
            cursor = self.connection.cursor()
            cursor.execute(query, params)
            self.connection.commit()
            return cursor.rowcount
        except sqlite3.Error as e:
            print(f"Error executing update: {e}")
            return 0

    def create_table(self, create_table_sql: str):
        """
        Create a table using the provided SQL statement.

        :param create_table_sql: The SQL statement to create a table.
        """
        try:
            cursor = self.connection.cursor()
            cursor.execute(create_table_sql)
            self.connection.commit()
            print("Table created successfully.")
        except sqlite3.Error as e:
            print(f"Error creating table: {e}")

# Example usage:
# db = SQLiteDB('example.db')
# db.connect()
# db.create_table("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT NOT NULL, age INTEGER);")
# db.execute_update("INSERT INTO users (name, age) VALUES (?, ?)", ('Alice', 30))
# results = db.execute_query("SELECT * FROM users")
# print(results)
# db.close()
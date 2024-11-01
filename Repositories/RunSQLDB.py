import sqlite3

class RunSQLDB:
    def __init__(self):
        self.database_path = "./database/database.db"

    def connect_to_database(self):
        # Connect to the database
        conn = sqlite3.connect(self.database_path)  # Adjust this path as necessary
        cursor = conn.cursor()
        return conn, cursor

    def close_database_connection(self, conn):
        # Commit the changes and close the connection
        conn.commit()
        conn.close()
    
    def search_in_database(self, sql):
        conn, cursor = self.connect_to_database()
        # your SQL
        try:
            cursor.execute(sql)
        except sqlite3.Error as e:
            print(f"An error occurred: {e}")

        result = cursor.fetchall()
        
        self.close_database_connection(conn)

        return result

    def update_database(self, sql):
        conn, cursor = self.connect_to_database()

        # your SQL
        try:
            cursor.execute(sql)
        except sqlite3.Error as e:
            print(f"An error occurred: {e}")

        self.close_database_connection(conn)


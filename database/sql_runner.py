import sqlite3

def run_sql(sql):
    # Connect to the database
    conn = sqlite3.connect('./database/database.db')  # Adjust this path as necessary
    cursor = conn.cursor()

    # your SQL
    try:
        cursor.execute(sql)
    except sqlite3.Error as e:
        print(f"An error occurred: {e}")

    result = cursor.fetchall()
    
    # Commit the changes and close the connection
    conn.commit()
    conn.close()
    return result



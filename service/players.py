import sqlite3

def add_player(dbu_name, mobilepay_name, team):
    # Connect to the database
    conn = sqlite3.connect('database/database.db') 
    cursor = conn.cursor()

    # Insert a new player into the players table
    cursor.execute('''
    INSERT INTO players (dbu_name, mobilepay_name, team, deposit, total_fines, balance)
    VALUES (?, ?, ?, ?, ?, ?)
    ''', (dbu_name, mobilepay_name, team, 0, 0, 0))

    # Commit the changes and close the connection
    conn.commit()
    conn.close()
    print("Player added successfully.")
    # return player id
    return cursor.lastrowid

import sqlite3
import datetime

def add_team(team_name, password):
    # Connect to the database
    conn = sqlite3.connect('database/database.db') 
    cursor = conn.cursor()

    season_name = new_season_name()
    season_date = new_season_date()
    # Insert a new player into the players table
    cursor.execute('''
    INSERT INTO teams (team_name, season, season_start_date, password)
    VALUES (?, ?, ?, ?)
    ''', (team_name, season_name, season_date, password))

    # Commit the changes and close the connection
    conn.commit()
    conn.close()
    print("Team added successfully.")
    
    # return team id
    return cursor.lastrowid

def new_season_date():
    # Get the current date
    current_date = datetime.date.today()

    # Format the date as YYYY-MM-DD
    return current_date.strftime("%Y-%m-%d")
    return 

def new_season_name():
    # Get the current date
    current_date = datetime.datetime.now()

    # Extract the year
    current_year = current_date.year

    # Extract the current month
    current_month = current_date.month

    if current_month < 7:
        return current_year + 10000
    return current_year + 20000
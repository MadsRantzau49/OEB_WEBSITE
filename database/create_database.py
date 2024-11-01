import sqlite3

# Connect to (or create) the database
conn = sqlite3.connect('database/database.db')

# Create a cursor object to interact with the database
cursor = conn.cursor()

# Create the teams table with id and team_name
cursor.execute('''
CREATE TABLE IF NOT EXISTS teams (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    team_name TEXT NOT NULL,
    club_name TEXT NOT NULL,
    season INT NOT NULL,
    season_start TEXT NOT NULL,
    password TEXT NOT NULL               
)
''')

# Create the fines table with a foreign key on the team column
cursor.execute('''
CREATE TABLE IF NOT EXISTS players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dbu_name TEXT NOT NULL,
    mobilepay_name TEXT NOT NULL,
    team INTEGER NOT NULL,
    deposit INTEGER,
    total_fines INTEGER,
    balance INTEGER,
    is_active INTEGER NOT NULL,
    FOREIGN KEY (team) REFERENCES teams(id)
)
''')

# Create matches table
cursor.execute('''
CREATE TABLE IF NOT EXISTS matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_url_id TEXT NOT NULL,
    team INTEGER,
    team_scored INTEGER,
    opponent_scored INTEGER,
    fine INTEGER,
    clothe_washer INTEGER,
    match_played BOOLEAN,
    season INTEGER,
    FOREIGN KEY (clothe_washer) REFERENCES players(id),
    FOREIGN KEY (team) REFERENCES teams(id)
)
''')

# Create player played match
cursor.execute('''
CREATE TABLE IF NOT EXISTS player_match (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player INTEGER,
    match INTEGER,    
    FOREIGN KEY (player) REFERENCES players(id),
    FOREIGN KEY (match) REFERENCES matches(id)
)
''')

# Player washed
cursor.execute('''
CREATE TABLE IF NOT EXISTS player_washed (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player INTEGER,
    match INTEGER,    
    FOREIGN KEY (player) REFERENCES players(id),
    FOREIGN KEY (match) REFERENCES matches(id)
)
''')


# Create player extra fines
cursor.execute('''
CREATE TABLE IF NOT EXISTS extra_fines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    description TEXT NOT NULL,
    amount INTEGER,    
    player INTEGER,
    FOREIGN KEY (player) REFERENCES players(id)
)
''')


# Commit the changes and close the connection
conn.commit()
conn.close()

print("Database and tables created successfully.")

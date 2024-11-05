from .RunSQLDB import RunSQLDB
from Model.Team import Team

class TeamDB:
    def __init__(self):
        self.runSQLDB = RunSQLDB()

    def team_already_exist(self, team_name):
        conn, cursor = self.runSQLDB.connect_to_database()

        cursor.execute('SELECT COUNT(*) FROM teams WHERE team_name = ?', (team_name,))
        team_exists = cursor.fetchone()[0]

        self.runSQLDB.close_database_connection(conn)
        return team_exists > 0
    
    def add_team(self, team):
        conn, cursor = self.runSQLDB.connect_to_database()

        # Insert a new player into the players table
        cursor.execute('''
        INSERT INTO teams (team_name, club_name ,season, season_start, password)
        VALUES (?, ?, ?, ?, ?)
        ''', (team.team_name, team.club_name, team.season, team.season_start, team.password))

        team_id = cursor.lastrowid
        self.runSQLDB.close_database_connection(conn)
        return team_id
    
    def get_team_information(self, team_name):
        conn, cursor = self.runSQLDB.connect_to_database()
        cursor.execute('''
        SELECT * FROM teams WHERE team_name = ?
        ''', (team_name,))
        
        data = cursor.fetchone()
        self.runSQLDB.close_database_connection(conn)
        if data:
            team = Team()
            team.id = data[0] 
            team.team_name = data[1] 
            team.club_name = data[2]
            team.season = data[3]
            team.season_start = data[4], 
            team.password = data[5]
            return team
        else:
            return None
        
    def get_team_players(self, team_id):
        players = self.runSQLDB.search_in_database(f"SELECT * FROM players where team = {team_id}")
        print(players)
        return players

    def get_team_matches(self, team_id):
        matches = self.runSQLDB.search_in_database(f"SELECT * FROM matches where team = {team_id}")
        print(matches)
        return matches
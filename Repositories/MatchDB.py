from .RunSQLDB import RunSQLDB

class MatchDB(RunSQLDB):

    def add_match(self, match):
        
        conn, cursor = RunSQLDB.connect_to_database()        
        # Insert a new player into the players table
        cursor.execute('''
        INSERT INTO matches (match_url_id, team, match_played, season)
        VALUES (?, ?, ?, ?)
        ''', (match.match_url_id, match.team, False, match.season))

        RunSQLDB.close_database_connection(conn)
        return cursor.lastrowid
    
    def update_match(self, match):
        conn, cursor = RunSQLDB.connect_to_database()        

        # Update a match
        cursor.execute('''
        UPDATE matches 
        SET oeb_scored = ?, opp_scored = ?, fine = ?, match_played = ?
        WHERE id = ?
    ''', (match.team_scored, match.opponent_scored, match.fine, 1, match.id ))
        
        RunSQLDB.close_database_connection(conn)

    def update_washer(self, match_id,player_id):
        conn, cursor = RunSQLDB.connect_to_database()        

        # Update a match
        cursor.execute('''
        UPDATE matches 
        SET clothe_washer = ?, season = ?
        WHERE id = ?
    ''', (player_id,12024,match_id))

        RunSQLDB.close_database_connection(conn)

    def find_club_name(self):
        club_name = RunSQLDB.search_in_database(f"SELECT club_name from teams WHERE teams.id = {self.match.team}")
        print(club_name)  
        return club_name
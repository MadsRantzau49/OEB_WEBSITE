import requests
from bs4 import BeautifulSoup
import re
import json
from Repositories.MatchDB import MatchDB
from Model.Match import Match
import sqlite3

class MatchService:
    def __init__(self):
        self.match_db = MatchDB()

    def create_match(self, match_url_id, team_id, season_id):
        match_already_exist = self.match_db.match_already_exist(match_url_id, team_id, season_id)

        if match_already_exist:
            raise ValueError("Match already exist.")
        
        if not season_id:
            raise ValueError("No season found")
        match = Match(match_url_id=match_url_id, team_id=team_id, season_id=season_id, team_scored=0, opponent_scored=0)

        # Add the team to the database
        match_id = self.match_db.add_match(match)

        return match    
    

    # Find a match result, e.g., ØB VEJGAARD: 2-1
    def find_match_result(self, match_url_id):
        match_result_url = "https://www.dbu.dk/resultater/kamp/" + self.match_url_id + "/kampinfo"

        # Request HTML code from dbu.dk
        match_result_html_request = requests.get(match_result_url)
        # Parse HTML using BeautifulSoup
        soup = BeautifulSoup(match_result_html_request.text, 'html.parser')
        
        # Find all team lineup information
        match_result_info = soup.find_all("div", {"class": "sr--match--live-score--result"})
        # Extract text from HTML elements
        match_result_text = [info.get_text() for info in match_result_info]

        match_result_text = re.sub(r'\n\s*\n', '\n', match_result_text[0]).strip()

        # Split the string into lines
        lines = match_result_text.split('\n')

        # Check if ØB is home or away
        if "ØB" in lines[0]:  # Adjusted to check the team name directly
            self.match.team_scored = int(lines[2])
            self.match.opponent_scored = int(lines[-3])
        else:
            self.match.team_scored = int(lines[-3])
            self.match.opponent_scored = int(lines[2])
    
    def get_all_matches_from_season(self, season_id):
        return self.seasonDB.get_matches_by_season(season_id)

    # Calculate fines based on the match result
    def calculate_fine(self):
        with open('./database/fines.json', 'r') as file:
            data = json.load(file)
        
        won_match_fine = data['won_match']
        draw_match_fine = data['draw_match']
        lost_match_fine = data['lost_match']
        conceded_goal_fine = data['conceded_goal']
        scored_goal_fine = data['scored_goal']

        self.match.fine = 0

        # Depends on who won
        self.match.fine += self.oeb_won(won_match_fine, lost_match_fine, draw_match_fine)

        # Scored goal fine
        self.match.fine += self.match.team_scored * scored_goal_fine
        self.match.fine += self.match.opponent_scored * conceded_goal_fine

    # Determine fine based on match result (win, loss, draw)
    def oeb_won(self, win, lose, draw):
        if self.match.team_scored > self.match.opponent_scored:
            return win
        elif self.match.team_scored < self.match.opponent_scored:
            return lose
        else:
            return draw

    # Get matches by season ID
    def get_matches_by_season(self, season_id):
        if season_id:
            return self.match_db.get_matches_by_season(season_id)
        return []
    

#EALIER FUNCTION TO INSPIRATION 
def add_player_match(player,match):
    # Connect to the database
    conn = sqlite3.connect('database/database.db') 
    cursor = conn.cursor()

    # Insert a new player into the players table
    cursor.execute('''
    INSERT INTO player_match (player, match)
    VALUES (?, ?)
    ''', (player,match))

    # Commit the changes and close the connection
    conn.commit()
    conn.close()
    print("Match added successfully.")


#Webscrape the player list from DBU webiste
def find_game_lineup(match_id):
    team_lineup_url = "https://www.dbu.dk/resultater/kamp/" + match_id +"/kampinfo"


    #request html code from dbu.dk
    team_lineup_html_request = requests.get(team_lineup_url)
    
    # Parse HTML using BeautifulSoup
    soup = BeautifulSoup(team_lineup_html_request.text, 'html.parser')

    # Find all team lineup information
    team_lineup_info = soup.find_all("div", {"class": "sr--match--team-cards dbu-grid"})
    if not team_lineup_info:
        raise ValueError("Match Not Found")
    
    # Extract text from HTML elements
    team_lineup_text = [info.get_text() for info in team_lineup_info]
    team_lineup_text_string = ""
    for elements in team_lineup_text:
        team_lineup_text_string += elements
    
    team_lineup_text_string = re.sub(r'\n\s*\n', '\n', team_lineup_text_string).strip()

    return team_lineup_text_string


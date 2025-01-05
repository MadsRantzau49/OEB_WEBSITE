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
        self.HOME_TEAM_LINEUP_SEARCH = "table", {"class": "dbu-data-table dbu-data-table--no-hover dbu-data-table-oddeven home-team"}
        self.AWAY_TEAM_LINEUP_SEARCH = "table", {"class": "dbu-data-table dbu-data-table--no-hover away-team dbu-data-table-oddeven"}

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
    
    def delete_match(self, match_id):
        return self.match_db.delete_match(match_id)
    
    #Webscrape the player list from DBU webiste
    def find_team_lineup(self, match_id, club_name):
        soup = self.get_match_info_from_dbu(match_id)
        if self.is_match_played_on_home_stadion(soup, club_name):
            team_lineup_div = soup.find(self.HOME_TEAM_LINEUP_SEARCH)
        else:
            team_lineup_div = soup.find(self.AWAY_TEAM_LINEUP_SEARCH)

        if not team_lineup_div:
            raise ValueError("Lineup not found")
        
        # takes every span values in the team_lineup_div and then ignore the first (which is the club name)
        return [span.text for span in team_lineup_div.select('span')][1:]
        

    def get_match_info_from_dbu(self, match_id):
        team_lineup_url = "https://www.dbu.dk/resultater/kamp/" + match_id +"/kampinfo"
        #request html code from dbu.dk
        team_lineup_html_request = requests.get(team_lineup_url)
        
        # Parse HTML using BeautifulSoup
        return BeautifulSoup(team_lineup_html_request.text, 'html.parser')
    
    def is_match_played_on_home_stadion(self, soup, club_name):
        home_team_club_name = soup.find(self.HOME_TEAM_LINEUP_SEARCH).find('th', class_='reserve').find('span').text
        if home_team_club_name == club_name:
            return True
        away_team_club_name = soup.find(self.AWAY_TEAM_LINEUP_SEARCH).find('th', class_='reserve').find('span').text
        if away_team_club_name == club_name:
            return False
        raise Exception("Club name not found in match, ensure the club name is equal to DBU database.")

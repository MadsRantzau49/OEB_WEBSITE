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
        match = Match(match_url_id=match_url_id, team_id=team_id, season_id=season_id, home_scored=None, away_scored=None)

        # Add the team to the database
        match_id = self.match_db.add_match(match)

        return match    
    
    def get_all_matches_from_season(self, season_id):
        return self.seasonDB.get_matches_by_season(season_id)

    # Get matches by season ID
    def get_matches_by_season(self, season_id):
        if season_id:
            return self.match_db.get_matches_by_season(season_id)
        return []
    
    def delete_match(self, match_id):
        return self.match_db.delete_match(match_id)
    
    def get_match_by_id(self, match_id):
        return self.match_db.find_match_by_id(match_id)

    def update_match(self, match):
        return self.match_db.update_match(match)

    def update_match_information(self, match_id):
        try:
            match = self.get_match_by_id(match_id)
            soup = self.get_match_info_from_dbu(match.match_url_id)
            match.home_club = self.get_home_club_name(soup)
            match.away_club = self.get_away_club_name(soup)

            match.home_scored = self.get_home_team_scored_goals(soup)
            match.away_scored = self.get_away_team_scored_goals(soup)
            print(match.home_club,"\n",match.home_scored,"\n",match.away_club,"\n",match.away_scored,"\n\n\n\n")

            return self.update_match(match)

        except Exception as e:
            print("\n\nERRRORRRR\n\n")
            print(e)
            raise ValueError("Kamp data ikke fundet")

    def update_all_season_matches_information(self, season_id):
        season_matches = self.get_matches_by_season(season_id)
        for match in season_matches:
            try:
                self.update_match_information(match.id)
            # If no data is found just continue.
            except ValueError as e:
                continue


    #Webscrape the player list from DBU webiste
    def find_team_lineup(self, match_id, club_name):
        try:
            soup = self.get_match_info_from_dbu(match_id)
            if self.is_match_played_on_home_stadion(soup, club_name):
                team_lineup_div = soup.find(self.HOME_TEAM_LINEUP_SEARCH)
            else:
                team_lineup_div = soup.find(self.AWAY_TEAM_LINEUP_SEARCH)

            if not team_lineup_div:
                raise ValueError("Lineup not found")
            
            # takes every span values in the team_lineup_div and then ignore the first (which is the club name)
            return [span.text for span in team_lineup_div.select('span')][1:]
        except Exception as e:
            return []

    def get_match_info_from_dbu(self, match_id):
        match_info_url = "https://www.dbu.dk/resultater/kamp/" + match_id +"/kampinfo"
        #request html code from dbu.dk
        match_info_url_request = requests.get(match_info_url)
        # Parse HTML using BeautifulSoup
        return BeautifulSoup(match_info_url_request.text, 'html.parser')
    
    def get_home_club_name(self, soup):
        return soup.find("div", {"class": "sr--match--live-score--result--home"}).find("div", {"class": "teamname"}).text.strip()

    def get_away_club_name(self, soup):
        return soup.find("div", {"class": "sr--match--live-score--result--away"}).find("div", {"class": "teamname"}).text.strip()

    def get_home_team_scored_goals(self, soup):
        return soup.find("div", {"class": "sr-match-score"}).find("div", {"class": "home"}).text.strip()
    
    def get_away_team_scored_goals(self, soup):
        return soup.find("div", {"class": "sr-match-score"}).find("div", {"class": "away"}).text.strip()

    def is_match_played_on_home_stadion(self, home_club, away_club, club_name):
        if home_club == club_name:
            return True
        elif away_club == club_name:
            return False
        raise Exception("Club name not found in match, ensure the club name is equal to DBU database.")

    def get_match_club_location_scored_goals(self, soup, location):
        return 5

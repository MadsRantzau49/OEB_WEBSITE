from bs4 import BeautifulSoup
import requests
from sqlalchemy.orm import Session
from Repositories.SeasonDB import SeasonDB
from Model.Season import Season
from datetime import datetime
from Service.MatchService import MatchService
from Model.Match import Match

class SeasonService:
    def __init__(self):
        # Initialize the repository layer
        self.seasonDB = SeasonDB()
        self.match_service = MatchService()

    def create_first_season(self, team_id):
        current_date = str(datetime.today().date()) #typecast due to bug in convertHTMLDate if not a string I AM SHIT AT CODING. 
        return self.create_season(team_id, "season1", None, current_date, None)

    def create_season(self, team_id, season_name, season_url ,season_start, season_end):
        # Check if team already exists
        if self.seasonDB.season_name_already_exist_for_team(team_id, season_name):
            raise ValueError("Team name already exists. Please choose a different name.")
        
        season_start_date = self.convertHTMLDate(season_start)
        season_end_date = self.convertHTMLDate(season_end) if season_end else None


        season = Season(name=season_name, season_url = season_url, start_date=season_start_date, end_date=season_end_date, team_id=team_id)

        # Add the team to the database
        season_id = self.seasonDB.add_season(season)
        return season

    def convertHTMLDate(self, start_date):
        return datetime.strptime(start_date, '%Y-%m-%d').date()


    def get_all_seasons_from_team(self, team_id):
        return self.seasonDB.get_seasons_by_team(team_id)
    
    def find_latest_season_by_team_id(self, team_id):
        return self.seasonDB.find_latest_season_by_team_id(team_id)
    
    def find_season_by_id(self, season_id):
        return self.seasonDB.find_season_by_id(season_id)
    
    def update_season(self, season_id, season_name, season_url, season_start, season_end):
        season = self.seasonDB.find_season_by_id(season_id)

        season.name = season_name
        season.season_url = season_url
        season.start_date = self.convertHTMLDate(season_start) if season_start else None
        season.end_date = self.convertHTMLDate(season_end) if season_end else None

        updated_season = self.seasonDB.update_season(season)

        return season

    def get_suggested_season_matches(self, season_id):
        try:
            season = self.find_season_by_id(season_id)
            soup = self.get_season_information_from_dbu(season.season_url)
            all_match_table = soup.find("div", {"id": "teamMatchProgram"})
            table_row = all_match_table.find_all("tr", {"class": "has-hover"})
            
            suggested_matches = []

            for row in table_row:
                row_cell = row.find_all("td", {"hide-on-mobile"})
                match_id = row_cell[1].text.strip()
                full_match_url = self.merge_match_with_season_url(match_id, season.season_url)
                
                match = Match(match_url_id = full_match_url, season_id = season_id)
                if self.match_service.match_already_exist(match.match_url_id, match.season_id):
                    continue
                soup = self.match_service.get_match_info_from_dbu(match.match_url_id)
                match.home_club = self.match_service.get_home_club_name(soup)
                match.away_club = self.match_service.get_away_club_name(soup)
                suggested_matches.append(match)


            if not suggested_matches:
                raise ValueError
            return suggested_matches
        
        except ValueError as e:
                raise ValueError("No suggested matches found. Ensure season_url is updated (id from https://www.dbu.dk/resultater/hold/xxxx_xxxxxx/kampprogram)")
        except Exception as e:
            raise ValueError("Suggested matches not found, ensure season_url is updated (id from https://www.dbu.dk/resultater/hold/xxxx_xxxxxx/kampprogram)")
        
    def merge_match_with_season_url(self, match_id, season_url):
        dbu_season_id = season_url.split("_")[1]
        return f"{match_id}_{dbu_season_id}"

    def get_season_information_from_dbu(self, season_url):
        season_info_url = "https://www.dbu.dk/resultater/hold/" + season_url +"/kampprogram"
        #request html code from dbu.dk
        season_info_url_request = requests.get(season_info_url)
        # Parse HTML using BeautifulSoup
        return BeautifulSoup(season_info_url_request.text, 'html.parser')
    
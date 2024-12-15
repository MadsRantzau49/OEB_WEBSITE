from sqlalchemy.orm import Session
from Repositories.SeasonDB import SeasonDB
from Model.Season import Season
from datetime import datetime

class SeasonService:
    def __init__(self):
        # Initialize the repository layer
        self.seasonDB = SeasonDB()

    def create_first_season(self, team_id):
        current_date = str(datetime.today().date()) #typecast due to bug in convertHTMLDate if not a string I AM SHIT AT CODING. 
        return self.create_season(team_id, "season1", current_date, None)

    def create_season(self, team_id, season_name, season_start, season_end):
        # Check if team already exists
        if self.seasonDB.season_name_already_exist_for_team(team_id, season_name):
            raise ValueError("Team name already exists. Please choose a different name.")
        
        season_start_date = self.convertHTMLDate(season_start)
        season_end_date = self.convertHTMLDate(season_end) if season_end else None


        season = Season(name=season_name, start_date=season_start_date, end_date=season_end_date, team_id=team_id)

        # Add the team to the database
        season_id = self.seasonDB.add_season(season)
        return season

    def convertHTMLDate(self, start_date):
        return datetime.strptime(start_date, '%Y-%m-%d').date()


    def get_all_seasons_from_team(self, team_id):
        return self.seasonDB.get_seasons_by_team(team_id)
    
    def find_latest_season_by_team_id(self, team_id):
        return self.seasonDB.find_latest_season_by_team_id(team_id)
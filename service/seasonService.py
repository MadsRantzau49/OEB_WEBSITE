from sqlalchemy.orm import Session
from Repositories.SeasonDB import SeasonDB
from Model.Season import Season
from datetime import datetime

class SeasonService:
    def __init__(self):
        # Initialize the repository layer
        self.seasonDB = SeasonDB()

    def create_first_season(self, team_id):
        current_date = datetime.today().date()
        return self.create_season(team_id, "season1", current_date, None)

    def create_season(self, team_id, season_name, season_start, season_end):
        # Check if team already exists
        if self.seasonDB.season_name_already_exist_for_team(team_id, season_name):
            raise ValueError("Team name already exists. Please choose a different name.")
        
        season = Season(name=season_name, start_date=season_start, end_date=season_end, team_id=team_id)

        # Add the team to the database
        season_id = self.seasonDB.add_season(season)
        print(season)
        return season

    def get_all_seasons_from_team(self, team_id):
        return self.seasonDB.get_seasons_by_team(team_id)
    
    def get_all_matches_from_season(self, season_id):
        return self.seasonDB.get_matches_by_season(season_id)
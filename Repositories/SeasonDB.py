from sqlalchemy.orm import Session
from Model.Season import Season
from Database.database_setup import SessionLocal
from .session_handler import session_handler
class SeasonDB:
    def __init__(self):
        self.db_session = SessionLocal()

    @session_handler
    def add_season(self, season: Season) -> int:
        self.db_session.add(season)
        self.db_session.commit()
        self.db_session.refresh(season)  # Refresh the object to get the season ID
        return season.id

    @session_handler
    def get_seasons_by_team(self, team_id: int) -> list:
        seasons = self.db_session.query(Season).filter(Season.team_id == team_id).all()
        return seasons

    @session_handler
    def season_name_already_exist_for_team(self, team_id, season_name) -> bool:
        season = self.db_session.query(Season).filter(Season.name == season_name, Season.team_id == team_id).first()
        return season is not None

    @session_handler
    def find_latest_season_by_team_id(self, team_id):
        season = self.db_session.query(Season).filter(Season.team_id == team_id).order_by(Season.id.desc()).first()
        return season


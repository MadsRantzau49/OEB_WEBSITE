from sqlalchemy.orm import Session
from Model.Match import Match
from database.database_setup import SessionLocal
from .session_handler import session_handler


class MatchDB:
    def __init__(self):
        self.db_session = SessionLocal()

    @session_handler
    def add_match(self, match: Match) -> int:
        self.db_session.add(match)
        self.db_session.commit()
        self.db_session.refresh(match)  # Refresh the object to get the match ID
        return match.id

    @session_handler
    def get_matches_by_season(self, season_id: int) -> list:
        return self.db_session.query(Match).filter(Match.season_id == season_id).all()

    @session_handler
    def match_already_exist(self, match_url_id, team_id, season_id):
        match = self.db_session.query(Match).filter(
            Match.match_url_id == match_url_id, 
            Match.team_id == team_id,            
            Match.season_id == season_id        
        ).first()
        return match is not None

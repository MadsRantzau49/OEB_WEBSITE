from sqlalchemy.orm import Session
from Model.Match import Match
from Database.database_setup import SessionLocal
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

    @session_handler
    def find_match_by_id(self, match_id) -> Match:
        match = self.db_session.query(Match).filter(Match.id == match_id).first()
        return match

    @session_handler
    def delete_match(self, match_id) -> bool:
        match = self.find_match_by_id(match_id)
        if match:
            self.db_session.delete(match)
            self.db_session.commit()  # Commit the deletion to the database
            return True
        return False
    
    @session_handler
    def update_match(self, match):
        self.db_session.merge(match)
        self.db_session.commit()
        return match
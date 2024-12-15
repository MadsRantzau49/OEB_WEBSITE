from sqlalchemy.orm import Session
from Model.Match import Match
from database.database_setup import SessionLocal

class MatchDB:
    def __init__(self):
        self.db_session = SessionLocal()

    def add_match(self, match: Match) -> int:
        self.db_session.add(match)
        self.db_session.commit()
        self.db_session.refresh(match)  # Refresh the object to get the match ID
        return match.id

    def get_matches_by_season(self, season_id: int) -> list:
        return self.db_session.query(Match).filter(Match.season_id == season_id).all()

    def close(self):
        self.db_session.close()

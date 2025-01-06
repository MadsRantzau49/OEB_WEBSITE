from sqlalchemy import Column, Integer, String, ForeignKey
from Database.database_setup import Base

class Match(Base):
    __tablename__ = 'matches'

    id = Column(Integer, primary_key=True, autoincrement=True)
    match_url_id = Column(String(255), nullable=False)
    team_id = Column(Integer, ForeignKey('teams.id'), nullable=False)
    season_id = Column(Integer, ForeignKey('seasons.id'), nullable=False)
    home_club = Column(String(255), nullable=True)
    away_club = Column(String(255), nullable=True)
    team_scored = Column(Integer, nullable=False)
    opponent_scored = Column(Integer, nullable=False)

from sqlalchemy import Column, Integer, ForeignKey
from database.database_setup import Base

class Season_Match(Base):
    __tablename__ = 'season_matches'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    team_id = Column(Integer, ForeignKey('teams.id'), nullable=False)
    season_id = Column(Integer, ForeignKey('seasons.id'), nullable=False)
    match_id = Column(Integer, ForeignKey('matches.id'), nullable=False)

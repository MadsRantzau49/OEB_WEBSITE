from sqlalchemy import Column, Integer, String, ForeignKey
from Database.database_setup import Base

class Match(Base):
    __tablename__ = 'matches'

    id = Column(Integer, primary_key=True, autoincrement=True)
    match_url_id = Column(String(255), nullable=False)
    season_id = Column(Integer, ForeignKey('seasons.id', ondelete="CASCADE"), nullable=False)
    home_club = Column(String(255), nullable=True)
    away_club = Column(String(255), nullable=True)
    home_scored = Column(Integer, nullable=True)
    away_scored = Column(Integer, nullable=True)
    clothes_washer = Column(Integer, ForeignKey('players.id', ondelete="SET NULL") ,nullable=True)
    

from sqlalchemy import Column, Integer, ForeignKey
from Database.database_setup import Base

class Player_Match(Base):
    __tablename__ = 'player_match'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(Integer, ForeignKey('players.id'), nullable=False)
    match_id = Column(Integer, ForeignKey('matches.id'), nullable=False)

from sqlalchemy import Column, Integer, ForeignKey, Date
from Database.database_setup import Base
import datetime

class Player_Fine(Base):
    __tablename__ = 'player_fines'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    player_id = Column(Integer, ForeignKey('players.id', ondelete="CASCADE"), nullable=False)
    fine_id = Column(Integer, ForeignKey('fines.id', ondelete="CASCADE"), nullable=False)
    season_id = Column(Integer, ForeignKey('seasons.id', ondelete="CASCADE"), nullable=False)
    date = Column(Date, nullable=False, default=datetime.date.today)




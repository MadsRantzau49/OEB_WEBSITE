from sqlalchemy import Column, Integer, String, ForeignKey, Date
from Database.database_setup import Base
import datetime

class Fine(Base):
    __tablename__ = 'fines'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False )
    description = Column(String(255), nullable=False)
    amount = Column(Integer, nullable=True)
    match_id = Column(Integer, ForeignKey('matches.id'), nullable=True)
    team_id = Column(Integer, ForeignKey('teams.id'), nullable=False)
    date = Column(Date, nullable=False, default=datetime.date.today)

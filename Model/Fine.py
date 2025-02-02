from sqlalchemy import Column, Integer, String, ForeignKey, Date, Enum
from Database.database_setup import Base
import datetime
from Model.FineType import FineType

class Fine(Base):
    __tablename__ = 'fines'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False )
    description = Column(String(255), nullable=False)
    amount = Column(Integer, nullable=True)
    team_id = Column(Integer, ForeignKey('teams.id'), nullable=False)
    match_id = Column(Integer, ForeignKey('matches.id'), nullable=True)
    fine_type = Column(Enum(FineType), nullable=False)
    date = Column(Date, nullable=False, default=datetime.date.today)

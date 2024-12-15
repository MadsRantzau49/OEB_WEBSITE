from sqlalchemy import Column, Integer, Text, ForeignKey
from database.database_setup import Base

class Extra_Fine(Base):
    __tablename__ = 'extra_fines'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    description = Column(Text, nullable=False)
    amount = Column(Integer, nullable=True)
    player_id = Column(Integer, ForeignKey('players.id'), nullable=False)


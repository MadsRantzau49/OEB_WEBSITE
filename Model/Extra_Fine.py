from sqlalchemy import Column, Integer, String, ForeignKey
from Database.database_setup import Base

class Extra_Fine(Base):
    __tablename__ = 'extra_fines'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False )
    description = Column(String(255), nullable=False)
    amount = Column(Integer, nullable=True)
    player_id = Column(Integer, ForeignKey('players.id'), nullable=False)


from sqlalchemy import Boolean, Column, Integer, String, ForeignKey
from Database.database_setup import Base

class Player(Base):
    __tablename__ = 'players'

    id = Column(Integer, primary_key=True)
    dbu_name = Column(String, nullable=False)
    mobilepay_name = Column(String, nullable=False)
    total_fines = Column(Integer, nullable=False)
    deposit = Column(Integer, nullable=False)
    is_active = Column(Boolean, nullable=False)
    team_id = Column(Integer, ForeignKey('teams.id'))  # Foreign key to Team

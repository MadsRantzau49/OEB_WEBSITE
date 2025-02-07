from sqlalchemy import Boolean, Column, Integer, String, ForeignKey
from Database.database_setup import Base

class Player(Base):
    __tablename__ = 'players'

    id = Column(Integer, primary_key=True)
    dbu_name = Column(String, nullable=False)
    mobilepay_name = Column(String, nullable=False)
    team_id = Column(Integer, ForeignKey('teams.id', ondelete="CASCADE"))  # Foreign key to Team

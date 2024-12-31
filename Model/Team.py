from sqlalchemy import Column, Integer, String
from Database.database_setup import Base

class Team(Base):
    __tablename__ = 'teams'

    id = Column(Integer, primary_key=True)
    team_name = Column(String, unique=True, nullable=False)
    club_name = Column(String)
    password = Column(String)

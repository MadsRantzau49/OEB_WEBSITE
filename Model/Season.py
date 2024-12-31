from sqlalchemy import Column, Integer, String, ForeignKey, Date
from Database.database_setup import Base

class Season(Base):
    __tablename__ = 'seasons'

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)
    team_id = Column(Integer, ForeignKey('teams.id'))  # Foreign key to Team


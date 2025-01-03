from sqlalchemy import Column, Integer, ForeignKey, LargeBinary
from Database.database_setup import Base

class MobilePayTransaction(Base):
    __tablename__ = 'mobilepay_transactions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    excel_file = Column(LargeBinary, nullable=False)  # Store the Excel file as binary data
    team_id = Column(Integer, ForeignKey('teams.id'), nullable=False)  # Foreign key to the Teams

    def __init__(self, excel_file: bytes, team_id: int):
        self.excel_file = excel_file
        self.team_id = team_id

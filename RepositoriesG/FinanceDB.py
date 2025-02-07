from sqlalchemy.orm import Session
from Model.MobilePayTransaction import MobilePayTransaction
from Database.database_setup import SessionLocal
from .session_handler import session_handler


class FinanceDB:
    def __init__(self):
        self.db_session = SessionLocal()

    @session_handler
    def upload_file(self, file: MobilePayTransaction):
        self.db_session.add(file)
        self.db_session.commit()
        self.db_session.refresh(file)  # Refresh the object to get the fine ID
        return file
    
    def get_all_team_files(self, team_id):
        return self.db_session.query(MobilePayTransaction).filter(MobilePayTransaction.team_id == team_id).all()

    def get_team_file(self, team_id):
        return self.db_session.query(MobilePayTransaction).filter(MobilePayTransaction.team_id == team_id).first()


    @session_handler
    def delete_file(self, file):
        self.db_session.delete(file)
        self.db_session.commit()
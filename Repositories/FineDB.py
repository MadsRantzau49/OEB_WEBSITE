from sqlalchemy.orm import Session
from Model.Fine import Fine
from Database.database_setup import SessionLocal
from .session_handler import session_handler


class FineDB:
    def __init__(self):
        self.db_session = SessionLocal()

    @session_handler
    def add_fine(self, fine: Fine):
        self.db_session.add(fine)
        self.db_session.commit()
        self.db_session.refresh(fine)  # Refresh the object to get the fine ID
        return fine
    
    @session_handler
    def get_all_team_fines(self, team_id):
        return self.db_session.query(Fine).filter(Fine.team_id == team_id).all()

    @session_handler
    def get_fine_by_id(self, fine_id):
        return self.db_session.query(Fine).filter(Fine.id == fine_id).first()
    
    @session_handler
    def update_fine(self, fine):
        self.db_session.merge(fine)
        self.db_session.commit()
        return fine
    
    @session_handler
    def remove_fine(self, fine):
        self.db_session.delete(fine)
        self.db_session.commit()
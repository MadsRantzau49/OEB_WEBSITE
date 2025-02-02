from sqlalchemy.orm import Session
from Model.Player_Fine import Player_Fine
from Database.database_setup import SessionLocal
from .session_handler import session_handler


class Player_FineDB:
    def __init__(self):
        self.db_session = SessionLocal()

    @session_handler
    def add_player_fine(self, player_fine: Player_Fine):
        self.db_session.add(player_fine)
        self.db_session.commit()
        self.db_session.refresh(player_fine)
        return player_fine
    
    @session_handler
    def get_all_player_fines_by_players_id(self, player_id):
        return self.db_session.query(Player_Fine).filter(Player_Fine.player_id == player_id).all()
    
    @session_handler
    def remove_player_fine(self, player_fine):
        self.db_session.delete(player_fine)
        self.db_session.commit()

    @session_handler
    def delete_all_player_fines_by_match_id(self, fine_id):
        self.db_session.query(Player_Fine).filter(
            Player_Fine.fine_id == fine_id
        ).delete(synchronize_session=False) 

        self.db_session.commit()  
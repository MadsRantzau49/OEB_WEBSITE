from sqlalchemy.orm import Session
from Model.Player import Player
from Database.database_setup import SessionLocal
from .session_handler import session_handler


class PlayerDB:
    def __init__(self):
        self.db_session = SessionLocal()

    @session_handler
    def add_player(self, player: Player) -> int:
        self.db_session.add(player)
        self.db_session.commit()
        self.db_session.refresh(player)  # Refresh the object to get the player ID
        return player.id

    @session_handler
    def get_players_by_team(self, team_id: int) -> list:
        players = self.db_session.query(Player).filter(Player.team_id == team_id).all()
        return players
    
    @session_handler
    def player_already_exist(self, name_type, name: str, team_id) -> bool:
        player = self.db_session.query(Player).filter(name_type == name, team_id == team_id).first()
        return player is not None

    @session_handler
    def close(self):
        self.db_session.close()

    @session_handler
    def find_player_by_id(self, player_id):
        return self.db_session.query(Player).filter(Player.id == player_id).first()

    @session_handler
    def delete_player(self, player_id) -> bool:
        player = self.find_player_by_id(player_id)
        if player:
            self.db_session.delete(player)
            self.db_session.commit()  
            return True
        return False
    
    @session_handler
    def update_player(self, player):
        self.db_session.merge(player)
        self.db_session.commit()
        return player
    
    @session_handler
    def find_player_by_dbu_name(self, dbu_name, team_id):
        return self.db_session.query(Player).filter(
            Player.dbu_name == dbu_name,
            Player.team_id == team_id
            ).first()
from sqlalchemy.orm import Session
from Model.Player import Player
from database.database_setup import SessionLocal
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
    def player_already_exist(self, name_type, name: str) -> bool:
        player = self.db_session.query(Player).filter(name_type == name).first()
        return player is not None

    @session_handler
    def close(self):
        self.db_session.close()

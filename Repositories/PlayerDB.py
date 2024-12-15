from sqlalchemy.orm import Session
from Model.Player import Player
from database.database_setup import SessionLocal

class PlayerDB:
    def __init__(self):
        self.db_session = SessionLocal()

    def add_player(self, player: Player) -> int:
        self.db_session.add(player)
        self.db_session.commit()
        self.db_session.refresh(player)  # Refresh the object to get the player ID
        return player.id

    def get_players_by_team(self, team_id: int) -> list:
        players = self.db_session.query(Player).filter(Player.team_id == team_id).all()
        return players
    
    def player_already_exist(self, name_type, name: str) -> bool:
        player = self.db_session.query(Player).filter(name_type == name).first()
        return player is not None

    def close(self):
        self.db_session.close()

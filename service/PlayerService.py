from Repositories.PlayerDB import PlayerDB
from Model.Player import Player
from sqlalchemy.orm import Session

class PlayerService:
    def __init__(self):
        # Initialize the other layers
        self.playerDB = PlayerDB()

    def create_player(self, dbu_name, mobilepay_name, team_id):
        dbu_name_exist = self.playerDB.player_already_exist(Player.dbu_name, dbu_name)
        mobilepay_name_exist = self.playerDB.player_already_exist(Player.mobilepay_name, mobilepay_name)

        if dbu_name_exist or mobilepay_name_exist:
            raise ValueError("Team name already exists. Please choose a different name.")
        
        # Create the Team object
        player = Player(dbu_name=dbu_name, mobilepay_name=mobilepay_name, total_fines=0, deposit=0, is_active=True, team_id=team_id)

        # Add the team to the database
        player_id = self.playerDB.add_player(player)

        return player    
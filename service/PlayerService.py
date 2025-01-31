from Repositories.PlayerDB import PlayerDB
from Model.Player import Player
from sqlalchemy.orm import Session

class PlayerService:
    def __init__(self):
        # Initialize the other layers
        self.playerDB = PlayerDB()

    def create_player(self, dbu_name, mobilepay_name, team_id):
        dbu_name_exist = self.playerDB.player_already_exist(Player.dbu_name, dbu_name, team_id)
        mobilepay_name_exist = self.playerDB.player_already_exist(Player.mobilepay_name, mobilepay_name, team_id)

        if dbu_name_exist or mobilepay_name_exist:
            raise ValueError("Player already added.")
        
        player = Player(dbu_name=dbu_name, mobilepay_name=mobilepay_name, total_fines=0, deposit=0, team_id=team_id)

        player_id = self.playerDB.add_player(player)

        return player    
    
    def delete_player(self, player_id):
        if not self.playerDB.delete_player(player_id):
            raise Exception("Player not deleted")

    def edit_player_name(self, player_id, dbu_name, mobilepay_name):
        player = self.get_player_from_id(player_id)
        player.dbu_name = dbu_name
        player.mobilepay_name = mobilepay_name
        
        updated_player = self.playerDB.update_player(player)

        return player

    def get_player_from_id(self, player_id):
        return self.playerDB.find_player_by_id(player_id)
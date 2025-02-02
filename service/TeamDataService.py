from flask import render_template
from .TeamService import TeamService
from .FineService import FineService
from Repositories.PlayerDB import PlayerDB


class TeamDataService:
    def __init__(self):
         self.team_service = TeamService()
         self.fine_service = FineService()
         self.player_DB = PlayerDB()

    def edit_team_data_html(self, season_id, *args, **kwargs):
        try:
            edit_team_data = self.team_service.get_all_edit_team_informations(season_id)
            
            return render_template('edit_team.html', team_data=edit_team_data, **kwargs)
    
        except Exception as e:
            # In case of error, render index.html with error
            return render_template('index.html', error=e)

    def user_team_data_html(self, season_id, *args, **kwargs):
        try:
            user_team_data = self.team_service.get_all_edit_team_informations(season_id)
            for player in user_team_data.players:
                player.balance = player.deposit - player.total_fines
            
            for match in user_team_data.matches:
                match.fine_amount = self.fine_service.calculate_match_total_fine(match.id, user_team_data.team.id)
                if match.clothes_washer:
                    match.clothes_washer_name = self.player_DB.find_player_by_id(match.clothes_washer).dbu_name
            return render_template('team.html', team_data=user_team_data, **kwargs)
    
        except Exception as e:
            return render_template('team.html', error=e)
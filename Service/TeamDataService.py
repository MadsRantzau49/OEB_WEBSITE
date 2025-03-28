from flask import render_template, redirect, url_for, request
from .TeamService import TeamService
from .FineService import FineService
from .FinanceService import FinanceService
from Repositories.PlayerDB import PlayerDB
from Repositories.MatchDB import MatchDB


class TeamDataService:
    def __init__(self):
         self.team_service = TeamService()
         self.fine_service = FineService()
         self.finance_service = FinanceService()
         self.player_DB = PlayerDB()
         self.match_DB = MatchDB()

    def edit_team_data_html(self, season_id, *args, **kwargs):
        try:
            edit_team_data = self.team_service.get_all_edit_team_informations(season_id)
            return render_template("edit_team.html", season_id=season_id, team_data=edit_team_data, **kwargs)
    
        except Exception as e:
            return render_template("admin_index.html", error=e)

    def user_team_data_html(self, season_id, *args, **kwargs):
        try:
            user_team_data = self.team_service.get_all_edit_team_informations(season_id)
            for player in user_team_data.players:
                # Get all deposit from excel file and add .total_deposit and .deposit_list
                player = self.finance_service.update_player_deposit_by_season(player, season_id)
                # Get all fines and add .total_fines and .fine_list
                player = self.fine_service.update_player_fines_by_season(player, season_id)
                player.balance = player.total_deposit - player.total_fines
                player.number_of_clothes_washes = self.match_DB.find_amount_of_player_clothes_washes_by_season(player.id, season_id)
            
            for match in user_team_data.matches:
                match.fine_amount = self.fine_service.calculate_match_total_fine(match.id, user_team_data.team.id)
                if match.clothes_washer:
                    match.clothes_washer_name = self.player_DB.find_player_by_id(match.clothes_washer).dbu_name

            user_team_data.expenses = self.finance_service.get_all_season_expenses(season_id)

            return render_template('team.html', team_data=user_team_data, **kwargs)
    
        except Exception as e:
            return render_template('team.html', error=e)

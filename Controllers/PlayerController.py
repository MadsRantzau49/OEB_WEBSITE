from flask import Blueprint, request, render_template
from Service.PlayerService import PlayerService
from Service.TeamService import TeamService
from Service.SeasonService import SeasonService
from Service.TeamDataService import TeamDataService
from Service.FinanceService import FinanceService
from Service.FineService import FineService
from Service.MatchService import MatchService
# Initialize the service
player_service = PlayerService()
team_service = TeamService()
season_service = SeasonService()
team_data_service = TeamDataService()
finance_service = FinanceService()
fine_service = FineService()
match_service = MatchService()
# Define the Blueprint
player_controller = Blueprint('player_controller', __name__)

@player_controller.route("/add_player", methods=["POST"])
def create_player():
    try:
        dbu_name = request.form['player_name']
        mobilepay_name = request.form['mobilepay_name']
        team_id = request.form['team_id']
        season_id = request.form.get("season_id",None)
        
        player = player_service.create_player(dbu_name, mobilepay_name, team_id)

        suggested_player_list = team_service.get_suggested_players(season_id)

        return team_data_service.edit_team_data_html(season_id, suggested_player_list=suggested_player_list)

    except ValueError as e:
        return team_data_service.edit_team_data_html(season_id, error=e)
    except Exception as e:
        return render_template('admin_index.html', error=e)

@player_controller.route("/remove_player", methods=["POST"])
def remove_player():
    try:
        player_id = request.form['player_id']
        season_id = request.form.get("season_id",None)
        
        player_service.delete_player(player_id)

        return team_data_service.edit_team_data_html(season_id)

    except ValueError as e:
        return team_data_service.edit_team_data_html(season_id, error=e)
    except Exception as e:
        return render_template('admin_index.html', error=e)

@player_controller.route("/edit_player_name", methods=["POST"])
def edit_player_name():
    try:
        season_id = request.form.get("season_id",None)
        player_id = request.form['player_id']
        dbu_name = request.form['dbu_name']
        mobilepay_name = request.form['mobilepay_name']

        player = player_service.edit_player_name(player_id, dbu_name, mobilepay_name)

        return team_data_service.edit_team_data_html(season_id)

    except ValueError as e:
        return team_data_service.edit_team_data_html(season_id, error=e)
    except Exception as e:
        return render_template('admin_index.html', error=e)

@player_controller.route("/get_suggested_players_list", methods=["POST"])
def get_suggested_players_list():
    try:
        season_id = request.form.get("season_id",None)

        suggested_player_list = team_service.get_suggested_players(season_id)

        return team_data_service.edit_team_data_html(season_id, suggested_player_list=suggested_player_list)

    except ValueError as e:
        return team_data_service.edit_team_data_html(season_id, error=e)
    except Exception as e:
        return render_template('admin_index.html', error=e)

@player_controller.route("/add_suggested_players", methods=["POST"])
def add_suggested_players():
    try:
        dbu_name_list = request.form.getlist('player_name')
        team_id = request.form['team_id']
        season_id = request.form.get("season_id",None)
        
        # The mobilepay may be wrong but most likely correct. 
        for dbu_name in dbu_name_list:
            player = player_service.create_player(dbu_name, dbu_name, team_id)

        return team_data_service.edit_team_data_html(season_id)

    except ValueError as e:
        return team_data_service.edit_team_data_html(season_id, error=e)
    except Exception as e:
        return render_template('admin_index.html', error=e)
    
@player_controller.route("/see_player_status", methods=["POST"])
def see_player_status():
    try:
        season_id = request.form.get("season_id",None)
        is_admin = request.form.get("is_admin", False)
        player_id = request.form["player_id"]

        player = player_service.get_player_from_id(player_id)
        highlighted_player = finance_service.update_player_deposit_by_season(player, season_id)
        highlighted_player = fine_service.update_player_fines_by_season(player, season_id)
        highlighted_player.balance = highlighted_player.total_deposit - highlighted_player.total_fines
        return team_data_service.user_team_data_html(season_id, highlighted_player=highlighted_player, is_admin=is_admin)

    except ValueError as e:
        return team_data_service.user_team_data_html(season_id ,error=e)
    except Exception as e:
        return render_template('index.html', error=e)
    
@player_controller.route("/delete_player_fine", methods=["POST"])
def delete_player_fine():
    try:
        season_id = request.form.get("season_id",None)
        is_admin = request.form.get("is_admin", False)
        player_id = request.form["player_id"]
        player_fine_id = request.form["player_fine_id"]

        fine_service.delete_player_fine(player_fine_id)

        player = player_service.get_player_from_id(player_id)
        highlighted_player = finance_service.update_player_deposit_by_season(player, season_id)
        highlighted_player = fine_service.update_player_fines_by_season(player, season_id)
        highlighted_player.balance = highlighted_player.total_deposit - highlighted_player.total_fines
        return team_data_service.user_team_data_html(season_id, highlighted_player=highlighted_player, is_admin=is_admin)

    except ValueError as e:
        return team_data_service.user_team_data_html(season_id, error=e)
    except Exception as e:
        return render_template('index.html', error=e)

from flask import Blueprint, request, render_template
from Service.PlayerService import PlayerService
from Service.TeamService import TeamService
from Service.SeasonService import SeasonService
from Service.EditTeamDataService import EditTeamDataService
# Initialize the service
player_service = PlayerService()
team_service = TeamService()
season_service = SeasonService()
edit_team_data_service = EditTeamDataService()
# Define the Blueprint
player_controller = Blueprint('player_controller', __name__)

@player_controller.route("/add_player", methods=["POST"])
def create_player():
    error = None
    try:
        dbu_name = request.form['player_name']
        mobilepay_name = request.form['mobilepay_name']
        team_id = request.form['team_id']
        season_id = request.form.get("season_id",None)
        
        player = player_service.create_player(dbu_name, mobilepay_name, team_id)

        suggested_player_list = team_service.get_suggested_players(season_id)

        return edit_team_data_service.edit_team_data_html(season_id, suggested_player_list=suggested_player_list)

    except ValueError as e:
        return edit_team_data_service.edit_team_data_html(season_id, error=e)
    except Exception as e:
        return render_template('index.html', error=e)

@player_controller.route("/remove_player", methods=["POST"])
def remove_player():
    try:
        player_id = request.form['player_id']
        season_id = request.form.get("season_id",None)
        
        player_service.delete_player(player_id)

        return edit_team_data_service.edit_team_data_html(season_id)

    except ValueError as e:
        return edit_team_data_service.edit_team_data_html(season_id, error=e)
    except Exception as e:
        return render_template('index.html', error=e)

@player_controller.route("/edit_player_name", methods=["POST"])
def edit_player_name():
    try:
        season_id = request.form.get("season_id",None)
        player_id = request.form['player_id']
        dbu_name = request.form['dbu_name']
        mobilepay_name = request.form['mobilepay_name']

        player = player_service.edit_player_name(player_id, dbu_name, mobilepay_name)

        return edit_team_data_service.edit_team_data_html(season_id)

    except ValueError as e:
        return edit_team_data_service.edit_team_data_html(season_id, error=e)
    except Exception as e:
        return render_template('index.html', error=e)

@player_controller.route("/get_suggested_players_list", methods=["POST"])
def get_suggested_players_list():
    try:
        season_id = request.form.get("season_id",None)

        suggested_player_list = team_service.get_suggested_players(season_id)

        return edit_team_data_service.edit_team_data_html(season_id, suggested_player_list=suggested_player_list)

    except ValueError as e:
        return edit_team_data_service.edit_team_data_html(season_id, error=e)
    except Exception as e:
        return render_template('index.html', error=e)

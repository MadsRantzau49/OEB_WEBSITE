from flask import Blueprint, request, render_template
from Service.SeasonService import SeasonService
from Service.TeamDataService import TeamDataService
from Service.FineService import FineService

# Initialize the service
season_service = SeasonService()
team_data_service = TeamDataService()
fine_service = FineService()

# Define the Blueprint
fine_controller = Blueprint('fine_controller', __name__)

@fine_controller.route("/add_fine", methods=["POST"])
def add_fine():
    try:
        season_id = request.form.get("season_id",None)

        name = request.form["fine_name"]
        description = request.form["fine_description"]
        amount = request.form["fine_amount"]
        type_value = request.form["fine_dropdown"]
        fine_service.add_fine(name, description, amount, season_id, type_value)
                
        return team_data_service.edit_team_data_html(season_id)
    
    except ValueError as e:
        return team_data_service.edit_team_data_html(season_id, error=e)
    except Exception as e:
        return render_template('admin_index.html', error=e)

@fine_controller.route("/edit_fine", methods=["POST"])
def edit_fine():
    try:
        season_id = request.form.get("season_id",None)

        fine_id = request.form["fine_id"]
        name = request.form["fine_name"]
        description = request.form["fine_description"]
        amount = request.form["fine_amount"]

        fine_service.edit_fine(fine_id, name, description, amount)
                
        return team_data_service.edit_team_data_html(season_id)
    
    except ValueError as e:
        return team_data_service.edit_team_data_html(season_id, error=e)
    except Exception as e:
        return render_template('admin_index.html', error=e)
    
@fine_controller.route("/remove_fine", methods=["POST"])
def remove_fine():
    try:
        season_id = request.form.get("season_id",None)

        fine_id = request.form["fine_id"]
    
        fine_service.remove_fine(fine_id)
                
        return team_data_service.edit_team_data_html(season_id)
    
    except ValueError as e:
        return team_data_service.edit_team_data_html(season_id, error=e)
    except Exception as e:
        return render_template('admin_index.html', error=e)
    
@fine_controller.route("/give_player_fine", methods=["POST"])
def give_player_fine():
    try:
        season_id = request.form.get("season_id",None)

        fine_id = request.form["fine_id"]
        name = request.form["fine_name"]
        description = request.form["fine_description"]
        amount = request.form["fine_amount"]
        player_id = request.form["player_id"]
    
        fine_service.add_player_fine(season_id, fine_id, name, description, amount, player_id)
                
        return team_data_service.user_team_data_html(season_id, is_admin=True)
    
    except ValueError as e:
        return team_data_service.user_team_data_html(season_id, is_admin=True, error=e)
    except Exception as e:
        return render_template('admin_index.html', error=e)
    
@fine_controller.route("/give_fine_to_multiple_players", methods=["POST"])
def give_fine_to_multiple_players():
    try:
        season_id = request.form.get("season_id",None)

        fine_id = request.form["fine_id"]
        name = request.form["fine_name"]
        description = request.form["fine_description"]
        amount = request.form["fine_amount"]
        player_ids = request.form.getlist("player_ids[]") 

        for player_id in player_ids:
            fine_service.add_player_fine(season_id, fine_id, name, description, amount, player_id)
                
        return team_data_service.user_team_data_html(season_id, is_admin=True, success="Successfully added fines")
    
    except ValueError as e:
        return team_data_service.user_team_data_html(season_id, is_admin=True, error=e)
    except Exception as e:
        return render_template('admin_index.html', error=e)
    
    
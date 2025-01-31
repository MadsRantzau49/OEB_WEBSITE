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

        fine_service.add_fine(name, description, amount, season_id)
                
        return team_data_service.edit_team_data_html(season_id)
    
    except ValueError as e:
        return team_data_service.edit_team_data_html(season_id, error=e)
    except Exception as e:
        return render_template('index.html', error=e)

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
        return render_template('index.html', error=e)
    
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
        return render_template('index.html', error=e)



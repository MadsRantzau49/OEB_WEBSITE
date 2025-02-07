from flask import Blueprint, request, render_template
from Service.TeamService import TeamService
from Service.SeasonService import SeasonService
from Service.TeamDataService import TeamDataService
# Initialize the service
team_service = TeamService()
season_service = SeasonService()
team_data_service = TeamDataService()
# Define the Blueprint
season_controller = Blueprint('season_controller', __name__)

@season_controller.route("/create_season", methods=["POST"])
def create_season():
    try:
        name = request.form['season_name']
        season_url = request.form.get('season_url',None)
        start_date = request.form['season_start']
        end_date = request.form.get('season_end',None)
        team_id = request.form["team_id"]

        season = season_service.create_season(team_id, name, season_url, start_date, end_date)

        return team_data_service.edit_team_data_html(season.id)

    except ValueError as e:
        return team_data_service.edit_team_data_html(season.id, error=e)
    except Exception as e:
        return render_template('index.html', error=e)


@season_controller.route("/change_season", methods=["POST"])
def change_season():
    try:
        season_id = request.form['season_id']      

        return team_data_service.edit_team_data_html(season_id)

    except ValueError as e:
        return team_data_service.edit_team_data_html(season_id, error=e)
    except Exception as e:
        return render_template('index.html', error=e)


@season_controller.route("/edit_season", methods=["POST"])
def edit_season():
    try:
        season_id = request.form['season_id']
        season_name = request.form['season_name']
        season_url = request.form.get('season_url',None)
        season_start = request.form.get('season_start',None)
        season_end = request.form.get('season_end',None)

        season = season_service.update_season(season_id, season_name, season_url, season_start, season_end)

        return team_data_service.edit_team_data_html(season_id)

    except ValueError as e:
        return team_data_service.edit_team_data_html(season_id, error=e)
    except Exception as e:
        return render_template('index.html', error=e)

@season_controller.route("/change_team_user_season", methods=["POST"])
def change_user_season():
    try:
        season_id = request.form['season_id']    
        is_admin = request.form.get("is_admin", False)

        return team_data_service.user_team_data_html(season_id, is_admin=is_admin)

    except ValueError as e:
        return team_data_service.edit_team_data_html(season_id, error=e)
    except Exception as e:
        return render_template('index.html', error=e)
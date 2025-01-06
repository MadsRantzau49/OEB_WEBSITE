from flask import Blueprint, request, render_template
from Service.TeamService import TeamService
from Service.SeasonService import SeasonService
# Initialize the service
team_service = TeamService()
season_service = SeasonService()
# Define the Blueprint
season_controller = Blueprint('season_controller', __name__)

@season_controller.route("/create_season", methods=["POST"])
def create_season():
    try:
        name = request.form['season_name']
        start_date = request.form['season_start']
        end_date = request.form.get('season_end',None)
        team_id = request.form["team_id"]

        season = season_service.create_season(team_id, name, start_date, end_date)

        edit_team_data = team_service.get_all_edit_team_informations(season.id)
        return render_template('edit_team.html', edit_team_data=edit_team_data)

    
    except Exception as e:
        # In case of error
        return render_template("index.html", error=f"Error: {str(e)}")

import json


@season_controller.route("/change_season", methods=["POST"])
def change_season():
    try:
        season_id = request.form['season_id']

        edit_team_data = team_service.get_all_edit_team_informations(season_id)
        return render_template('edit_team.html', edit_team_data=edit_team_data)
    
    except Exception as e:
        # In case of error
        return render_template("index.html", error=f"Error: {str(e)}")

@season_controller.route("/edit_season", methods=["POST"])
def edit_season():
    try:
        season_id = request.form['season_id']
        season_name = request.form['season_name']
        season_start = request.form.get('season_start',None)
        season_end = request.form.get('season_end',None)
        print(season_end)


        season = season_service.update_season(season_id, season_name, season_start, season_end)

        edit_team_data = team_service.get_all_edit_team_informations(season.id)
        return render_template('edit_team.html', edit_team_data=edit_team_data)
    
    except Exception as e:
        # In case of error
        return render_template("index.html", error=f"Error: {str(e)}")




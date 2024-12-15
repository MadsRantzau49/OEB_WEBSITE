from flask import Blueprint, request, render_template
from Service.TeamService import TeamService
from Service.SeasonService import SeasonService
from Repositories.TeamDB import TeamDB
# Initialize the service
team_service = TeamService()
season_service = SeasonService()
teamDB = TeamDB()
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

        team = teamDB.get_team_by_id(team_id)
        players, seasonList, matches = team_service.get_all_edit_team_informations(team,season.id)
       
        return render_template('edit_team.html', team=team, players=players, seasonList=seasonList, matches=matches)
    
    except Exception as e:
        # In case of error
        return render_template("index.html", error=f"Error: {str(e)}")

@season_controller.route("/change_season", methods=["POST"])
def change_season():
    try:
        season_id = request.form['season_id']
        team_id = request.form["team_id"]

        team = teamDB.get_team_by_id(team_id)
        players, seasonList, matches = team_service.get_all_edit_team_informations(team,season_id)
        return render_template('edit_team.html', team=team, players=players, seasonList=seasonList, season_id=season_id, matches=matches)
    
    except Exception as e:
        # In case of error
        return render_template("index.html", error=f"Error: {str(e)}")




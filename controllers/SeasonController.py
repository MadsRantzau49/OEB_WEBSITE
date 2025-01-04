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
        team = request.form["team"]

        season = season_service.create_season(team.id, name, start_date, end_date)

        edit_team_data = team_service.get_all_edit_team_informations(team,season)
        return render_template('edit_team.html', 
                               team=edit_team_data.team, 
                               players=edit_team_data.players, 
                               seasonList=edit_team_data.seasonList, 
                               season=edit_team_data.season, 
                               matches=edit_team_data.matches
                               )
    
    except Exception as e:
        # In case of error
        return render_template("index.html", error=f"Error: {str(e)}")

@season_controller.route("/change_season", methods=["POST"])
def change_season():
    try:
        season = request.form['season']
        team = request.form["team"]

        edit_team_data = team_service.get_all_edit_team_informations(team,season)
        return render_template('edit_team.html', 
                               team=edit_team_data.team, 
                               players=edit_team_data.players, 
                               seasonList=edit_team_data.seasonList, 
                               season=edit_team_data.season, 
                               matches=edit_team_data.matches
                               )
    
    except Exception as e:
        # In case of error
        return render_template("index.html", error=f"Error: {str(e)}")




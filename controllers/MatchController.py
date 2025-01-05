from flask import Blueprint, request, render_template
from Service.MatchService import MatchService
from Repositories.TeamDB import TeamDB
from Service.TeamService import TeamService
from Service.SeasonService import SeasonService
# Initialize the service
match_service = MatchService()
team_DB = TeamDB()
team_service = TeamService()
season_service = SeasonService()
# Define the Blueprint
match_controller = Blueprint('match_controller', __name__)

@match_controller.route("/add_match", methods=["POST"])
def create_match():
    try:
        match_url = request.form['match_url']
        team_id = request.form['team_id']
        season_id = request.form.get("season_id",None)
        
        match = match_service.create_match(match_url, team_id, season_id)

        edit_team_data = team_service.get_all_edit_team_informations(team_id, season_id)
        return render_template('edit_team.html', edit_team_data=edit_team_data)

    
    except Exception as e:
        # In case of error
        return render_template("index.html", error=f"Error: {str(e)}")

@match_controller.route("/remove_match", methods=["POST"])
def delete_match():
    try:
        match_id = request.form['match_id']
        team_id = request.form['team_id']
        season_id = request.form.get("season_id",None)
        
        match_service.delete_match(match_id)

        edit_team_data = team_service.get_all_edit_team_informations(team_id, season_id)
        return render_template('edit_team.html', edit_team_data=edit_team_data)

    
    except Exception as e:
        # In case of error
        return render_template("index.html", error=f"Error: {str(e)}")
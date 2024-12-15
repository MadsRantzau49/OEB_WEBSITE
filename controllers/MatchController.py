from flask import Blueprint, request, render_template
from Service.MatchService import MatchService
from Repositories.TeamDB import TeamDB
from Service.TeamService import TeamService
# Initialize the service
match_service = MatchService()
teamDB = TeamDB()
team_service = TeamService()
# Define the Blueprint
match_controller = Blueprint('match_controller', __name__)

@match_controller.route("/add_match", methods=["POST"])
def create_match():
    try:
        match_url = request.form['match_url']
        team_id = request.form['team_id']
        season_id = request.form.get("season_id", None)
        
        match = match_service.create_match(match_url, team_id, season_id)

        team = teamDB.get_team_by_id(team_id)
        players, seasonList, matches = team_service.get_all_edit_team_informations(team,season_id)
       
        return render_template('edit_team.html', team=team, players=players, seasonList=seasonList, season_id=season_id, matches=matches)
    
    except Exception as e:
        # In case of error
        return render_template("index.html", error=f"Error: {str(e)}")

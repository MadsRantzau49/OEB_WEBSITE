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
        team = request.form['team']
        season = request.form.get("season",None)
        
        match = match_service.create_match(match_url, team.id, season.id)

        edit_team_data = team_service.get_all_edit_team_informations(team, season)
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

@match_controller.route("/remove_match", methods=["POST"])
def delete_match():
    try:
        match_id = request.form['match_id']
        team = request.form['team']
        season = request.form.get("season",None)
        
        match_service.delete_match(match_id)

        edit_team_data = team_service.get_all_edit_team_informations(team, season)
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
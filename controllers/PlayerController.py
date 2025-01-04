from flask import Blueprint, request, render_template
from Service.PlayerService import PlayerService
from Service.TeamService import TeamService
from Service.SeasonService import SeasonService

# Initialize the service
player_service = PlayerService()
team_service = TeamService()
season_service = SeasonService()

# Define the Blueprint
player_controller = Blueprint('player_controller', __name__)

@player_controller.route("/add_player", methods=["POST"])
def create_player():
    try:
        dbu_name = request.form['player_name']
        mobilepay_name = request.form['mobilepay_name']
        team = request.form['team']
        season = request.form.get("season",None)
        
        player = player_service.create_player(dbu_name, mobilepay_name, team.id)

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

@player_controller.route("/remove_player", methods=["POST"])
def create_player():
    try:
        dbu_name = request.form['player_name']
        mobilepay_name = request.form['mobilepay_name']
        team = request.form['team']
        season = request.form.get("season",None)
        
        player = player_service.create_player(dbu_name, mobilepay_name, team.id)

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

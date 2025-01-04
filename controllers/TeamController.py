from flask import Blueprint, request, render_template
from Service.TeamService import TeamService
from Service.SeasonService import SeasonService
# Initialize the service
team_service = TeamService()
season_service = SeasonService()
# Define the Blueprint
team_controller = Blueprint('team_controller', __name__)

@team_controller.route("/create_team", methods=["POST"])
def create_team():
    try:
        team_name = request.form['team_name']
        club_name = request.form['club_name']
        password = request.form['password']
        
        team = team_service.create_team(team_name, club_name, password)
    
        return render_template("index.html", success="Team created successfully! You can now log in.")

    except Exception as e:
        return render_template("index.html", error=f"Error: {str(e)}")

@team_controller.route("/edit_team", methods=["POST"])
def edit_team():
    try:
        team_name = request.form["team_name"]
        password = request.form["password"]

        team = team_service.verify_login(team_name, password)

        edit_team_data = team_service.get_all_edit_team_informations(team,None)
        return render_template('edit_team.html', 
                               team=edit_team_data.team, 
                               players=edit_team_data.players, 
                               seasonList=edit_team_data.seasonList, 
                               season=edit_team_data.season, 
                               matches=edit_team_data.matches
                               )

    except Exception as e:
        return render_template("index.html", error=f"Error: {str(e)}")


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
        # Extract form data
        team_name = request.form['team_name']
        club_name = request.form['club_name']
        password = request.form['password']
        
        # Call service layer to create a team
        team = team_service.create_team(team_name, club_name, password)
    
        return render_template("index.html", success="Team created successfully! You can now log in.")

    except Exception as e:
        # In case of error
        return render_template("index.html", error=f"Error: {str(e)}")

@team_controller.route("/edit_team", methods=["POST"])
def edit_team():
    try:
        team_name = request.form["team_name"]
        password = request.form["password"]

        team = team_service.verify_login(team_name, password)
        season_id = request.form.get("season", season_service.find_latest_season_by_team_id(team.id).id)
        players, seasonList, matches = team_service.get_all_edit_team_informations(team,season_id)
       
        return render_template('edit_team.html', team=team, players=players, seasonList=seasonList, season_id=season_id, matches=matches)

    except Exception as e:
        print(e)
        return render_template("index.html", error=f"Error: {str(e)}")


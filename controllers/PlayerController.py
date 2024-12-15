from flask import Blueprint, request, render_template
from Service.PlayerService import PlayerService
from Service.TeamService import TeamService
from Repositories.TeamDB import TeamDB

# Initialize the service
player_service = PlayerService()
team_service = TeamService()
teamDB = TeamDB()

# Define the Blueprint
player_controller = Blueprint('player_controller', __name__)

@player_controller.route("/add_player", methods=["POST"])
def create_player():
    try:
        dbu_name = request.form['player_name']
        mobilepay_name = request.form['mobilepay_name']
        team_id = request.form['team_id']
        season_id = request.form.get("season", None)
        print(dbu_name,mobilepay_name,team_id,season_id)
        player = player_service.create_player(dbu_name, mobilepay_name, team_id)

        team = teamDB.get_team_by_id(team_id)
        players, seasonList, matches = team_service.get_all_edit_team_informations(team,season_id)
       
        return render_template('edit_team.html', team=team, players=players, seasonList=seasonList, season_id=season_id, matches=matches)
    
    except Exception as e:
        # In case of error
        return render_template("index.html", error=f"Error: {str(e)}")

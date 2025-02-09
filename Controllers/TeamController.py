from flask import Blueprint, request, render_template
from Service.TeamService import TeamService
from Service.SeasonService import SeasonService
from Service.TeamDataService import TeamDataService
import traceback        


# Initialize the service
team_service = TeamService()
season_service = SeasonService()
team_data_service = TeamDataService()
# Define the Blueprint
team_controller = Blueprint('team_controller', __name__)

@team_controller.route("/create_team", methods=["POST"])
def create_team():
    try:
        team_name = request.form['team_name'].upper()
        club_name = request.form['club_name'].upper()
        password = request.form['password']
        
        team = team_service.create_team(team_name, club_name, password)
    
        season_id = season_service.find_latest_season_by_team_id(team.id).id

        return team_data_service.edit_team_data_html(season_id)

    except Exception as e:
        return render_template("index.html", error=f"Error: {str(e)}")

@team_controller.route("/render/edit_team", methods=["POST"])
def render_edit_team():
    try:
        season_id = request.form.get("season_id", None)

        team_name = request.form["team_name"].upper()
        password = request.form["password"]

        team = team_service.verify_login(team_name, password)
        if not season_id:
            season_id = season_service.find_latest_season_by_team_id(team.id).id

        return team_data_service.user_team_data_html(season_id, is_admin=True)

    except Exception as e:
        return render_template('index.html', error=e)

@team_controller.route("/edit_team", methods=["POST"])
def edit_team():
    try:
        season_id = request.form.get("season_id",None)

        team_id = request.form["team_id"]
        password = request.form["password"]
        club_name = request.form["club_name"].upper()
        introduction_text = request.form["introduction_text"]


        team = team_service.edit_team(team_id, password, club_name, introduction_text)

        return team_data_service.edit_team_data_html(season_id)

    except Exception as e:
        return render_template('index.html', error=e)

@team_controller.route("/see_team_as_admin", methods=["POST"])
def see_team_as_admin():
    try:
        season_id = request.form["season_id"]

        return team_data_service.user_team_data_html(season_id, is_admin=True)

    except Exception as e:
        return render_template('index.html', error=e)

@team_controller.route("/see_team_as_user", methods=["POST"])
def see_team_as_user():
    try:
        team_name = request.form["team_name"].upper()

        team = team_service.get_team_by_name(team_name)
        if not team:
            raise Exception("Forkert brugernavn, prøv igen.")
        season_id = season_service.find_latest_season_by_team_id(team.id).id

        return team_data_service.user_team_data_html(season_id, is_admin=False)

    except Exception as e:
        return render_template('index.html', error=e)

@team_controller.route("/<team_name>", methods=["GET"])
def see_team_as_user_url(team_name):
    try:
        team_name = team_name.upper()

        team = team_service.get_team_by_name(team_name)
        if not team:
            raise Exception("Forkert brugernavn, prøv igen.")
        
        season_id = season_service.find_latest_season_by_team_id(team.id).id

        return team_data_service.user_team_data_html(season_id, is_admin=False)
    
    except Exception as e:
        traceback.print_exc()
        return render_template('index.html', error=e)

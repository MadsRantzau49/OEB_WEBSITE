from flask import Blueprint, request, render_template
from Repositories.TeamDB import TeamDB
from Model.Team import Team
from service.TeamService import TeamService

team_controller = Blueprint('team_controller', __name__)

teamService = TeamService()
teamDB = TeamDB()

@team_controller.route("/create_team", methods=["POST"])
def create_team():
    team = Team()
    
    team.team_name = request.form['team_name']
    team.club_name = request.form['club_name']
    team.password = request.form['password']
    team.season = teamService.new_season_name()
    team.season_start = teamService.new_season_date()

    if teamDB.team_already_exist(team.team_name) :
        return render_template("index.html", error = "brugernavn eksistere i forvejen, find på noget nyt")
    elif not teamService.is_valid_name(team.team_name):
        return render_template("index.html", error = "brugernavn kun indeholde bogstaver og tal. Det må ikke indeholde mellemrum og specieltegn")
    else:
        teamDB.add_team(team)
        return render_template("index.html", error = "Holdet er nu oprettet, du kan nu logge ind")


@team_controller.route("/edit_team", methods=["POST"])
def edit_team():
    team_name = request.form["team_name"]
    password = request.form["password"]

    team = teamService.verify_login(team_name,password)
    if team:
        pass
        
class TeamController:
    def edit_team_html(self, team):
        pass
    

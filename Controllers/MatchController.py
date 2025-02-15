from flask import Blueprint, request, render_template
from Service.MatchService import MatchService
from Repositories.TeamDB import TeamDB
from Service.TeamService import TeamService
from Service.SeasonService import SeasonService
from Service.TeamDataService import TeamDataService
from Service.FineService import FineService
# Initialize the service
match_service = MatchService()
team_DB = TeamDB()
team_service = TeamService()
season_service = SeasonService()
team_data_service = TeamDataService()
fine_service = FineService()
# Define the Blueprint
match_controller = Blueprint('match_controller', __name__)

@match_controller.route("/add_match", methods=["POST"])
def create_match():
    try:
        match_url = request.form['match_url']
        season_id = request.form.get("season_id",None)
        
        match = match_service.create_match(match_url, season_id)
        return team_data_service.edit_team_data_html(season_id)
    
    except ValueError as e:
        return team_data_service.edit_team_data_html(season_id, error=e)
    except Exception as e:
        return render_template('admin_index.html', error=e)


@match_controller.route("/remove_match", methods=["POST"])
def delete_match():
    try:
        match_id = request.form['match_id']
        season_id = request.form.get("season_id",None)
        
        match_service.delete_match(match_id)

        return team_data_service.edit_team_data_html(season_id)

    except ValueError as e:
        return team_data_service.edit_team_data_html(season_id, error=e)
    except Exception as e:
        return render_template('admin_index.html', error=e)
        

@match_controller.route("/update_all_season_matches_information/admin", methods=["POST"])
def update_all_season_matches_information():
    try:
        season_id = request.form.get("season_id",None)
        
        match_service.update_all_season_matches_information(season_id)

        return team_data_service.edit_team_data_html(season_id)

    except ValueError as e:
        return team_data_service.edit_team_data_html(season_id, error=e)
    except Exception as e:
        return render_template('admin_index.html', error=e)
    
@match_controller.route("/update_all_season_matches_information/user", methods=["POST"])
def update_all_season_matches_information_user():
    try:
        season_id = request.form.get("season_id",None)
        
        match_service.update_all_season_matches_information(season_id)
        return team_data_service.user_team_data_html(season_id, is_admin=True)

    except ValueError as e:
        return team_data_service.user_team_data_html(season_id, is_admin=True, error=e)
    except Exception as e:
        return render_template('admin_index.html', error=e)


@match_controller.route("/update_match_information", methods=["POST"])
def update_match_information():
    try:
        season_id = request.form.get("season_id",None)
        match_id = request.form["match_id"]

        match_service.update_match_information(match_id)

        return team_data_service.user_team_data_html(season_id, is_admin=True)

    except ValueError as e:
        return team_data_service.user_team_data_html(season_id, is_admin=True, error=e)
    except Exception as e:
        return render_template('admin_index.html', error=e)



@match_controller.route("/get_suggested_season_matches", methods=["POST"])
def get_suggested_season_matches():
    try:
        season_id = request.form.get("season_id",None)

        suggested_matches = season_service.get_suggested_season_matches(season_id)
        
        return team_data_service.edit_team_data_html(season_id, suggested_matches=suggested_matches)

    except ValueError as e:
        return team_data_service.edit_team_data_html(season_id, error=e)
    except Exception as e:
        return render_template('admin_index.html', error=e)

@match_controller.route("/add_suggested_matches", methods=["POST"])
def add_suggested_matches():
    try:
        match_url_list = request.form.getlist('match_url')
        season_id = request.form.get("season_id",None)
        
        for match_url in match_url_list:
            match_service.create_match(match_url, season_id)
        return team_data_service.edit_team_data_html(season_id)
    
    except ValueError as e:
        return team_data_service.edit_team_data_html(season_id, error=e)
    except Exception as e:
        return render_template('admin_index.html', error=e)
    
@match_controller.route("/change_clothes_washer", methods=["POST"])
def change_clothes_washer():
    try:
        season_id = request.form.get("season_id",None)

        match_id = request.form["match_id"]
        player_id = request.form["player_id"]

        match_service.change_match_washer(match_id, player_id)

        return team_data_service.user_team_data_html(season_id, is_admin=True)
    
    except ValueError as e:
        return team_data_service.user_team_data_html(season_id, is_admin=True, error=e)
    except Exception as e:
        return render_template('admin_index.html', error=e)

@match_controller.route("/add_match_manually", methods=["POST"])
def add_match_manually():
    try:
        season_id = request.form.get("season_id",None)

        home_team = request.form["home_team"]
        away_team = request.form["away_team"]
        home_goals = request.form["home_team_scored"]
        away_goals = request.form["away_team_scored"]

        match = match_service.creat_match_manually(season_id, home_team, away_team, home_goals, away_goals)

        team_id = team_service.get_team_by_season_id(season_id).id
        fine_service.update_match_fine([], match, team_id)

        return team_data_service.edit_team_data_html(season_id)

    except ValueError as e:
        return team_data_service.edit_team_data_html(season_id, error=e)
    except Exception as e:
        return render_template('admin_index.html', error=e)
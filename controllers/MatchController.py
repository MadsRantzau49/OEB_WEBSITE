from flask import Blueprint, request, render_template
from Service.MatchService import MatchService
from Repositories.TeamDB import TeamDB
from Service.TeamService import TeamService
from Service.SeasonService import SeasonService
from Service.TeamDataService import TeamDataService
# Initialize the service
match_service = MatchService()
team_DB = TeamDB()
team_service = TeamService()
season_service = SeasonService()
team_data_service = TeamDataService()
# Define the Blueprint
match_controller = Blueprint('match_controller', __name__)

@match_controller.route("/add_match", methods=["POST"])
def create_match():
    try:
        match_url = request.form['match_url']
        season_id = request.form.get("season_id",None)
        
        match = match_service.create_match(match_url, season_id)
        suggested_matches = season_service.get_suggested_season_matches(season_id)
        return team_data_service.edit_team_data_html(season_id, suggested_matches=suggested_matches)
    
    except ValueError as e:
        return team_data_service.edit_team_data_html(season_id, error=e)
    except Exception as e:
        return render_template('index.html', error=e)


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
        return render_template('index.html', error=e)
        

@match_controller.route("/update_all_season_matches_information", methods=["POST"])
def update_all_season_matches_information():
    try:
        season_id = request.form.get("season_id",None)
        
        match_service.update_all_season_matches_information(season_id)

        return team_data_service.edit_team_data_html(season_id)

    except ValueError as e:
        return team_data_service.edit_team_data_html(season_id, error=e)
    except Exception as e:
        return render_template('index.html', error=e)

@match_controller.route("/get_suggested_season_matches", methods=["POST"])
def get_suggested_season_matches():
    try:
        season_id = request.form.get("season_id",None)

        suggested_matches = season_service.get_suggested_season_matches(season_id)
        
        return team_data_service.edit_team_data_html(season_id, suggested_matches=suggested_matches)

    except ValueError as e:
        return team_data_service.edit_team_data_html(season_id, error=e)
    except Exception as e:
        return render_template('index.html', error=e)

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
        return render_template('index.html', error=e)
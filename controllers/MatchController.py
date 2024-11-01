from flask import Blueprint, request
from Model.Match import Match
from Repositories.MatchDB import MatchDB

match_controller = Blueprint('match_controller', __name__)

class MatchController:
    @match_controller.route('/add_match', methods=['POST'])
    def add_match(self):
        match = Match()
        match.team = request.form['team_id']
        match.match_url_id = request.form['match_url']
        match.season = request.form['season']
        MatchDB.add_match(match)
    
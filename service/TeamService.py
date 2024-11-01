import datetime
import re
from Repositories.TeamDB import TeamDB

class TeamService:
    def __init__(self):
        self.teamDB = TeamDB()
    def is_valid_name(self, name):
        # Check if the username only contains letters (a-z, A-Z), Danish characters (æ, ø, å), and numbers (0-9), no spaces
        return bool(re.fullmatch(r"[a-zA-ZæøåÆØÅ0-9]+", name))

    def new_season_date(self):
        # Get the current date
        current_date = datetime.date.today()

        # Format the date as YYYY-MM-DD
        return current_date.strftime("%Y-%m-%d")

    def new_season_name(self):
        # Get the current date
        current_date = datetime.datetime.now()

        # Extract the year
        current_year = current_date.year

        # Extract the current month
        current_month = current_date.month

        if current_month < 7:
            return current_year + 10000
        return current_year + 20000
    
    def verify_login(self, team_name, password):
        team = self.teamDB.get_team_information(team_name, password)
        if team and password == team.password:
            return team
        return False
            
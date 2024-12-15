import re
from Repositories.TeamDB import TeamDB
from Repositories.PlayerDB import PlayerDB
from Repositories.SeasonDB import SeasonDB
from Model.Team import Team
from Service.seasonService import SeasonService
from sqlalchemy.orm import Session

class TeamService:
    def __init__(self):
        # Initialize the other layers
        self.teamDB = TeamDB()
        self.playerDB = PlayerDB()
        self.seasonDB = SeasonDB()
        self.seasonService = SeasonService()

    def create_team(self, team_name, club_name, password):
        """
        Creates a new team, verifying that the team name is unique and valid.
        If the team is successfully created, returns the team object.
        """
        # Validate team name format
        if not self.is_valid_name(team_name):
            raise ValueError("Invalid team name. Only letters, numbers, and Danish characters are allowed, no spaces.")
        
        # Check if team already exists
        if self.teamDB.team_already_exist(team_name):
            raise ValueError("Team name already exists. Please choose a different name.")
        
        # Create the Team object
        team = Team(team_name=team_name, club_name=club_name, password=password)

        # Add the team to the database
        team_id = self.teamDB.add_team(team)

        # Create a default season
        season = self.seasonService.create_first_season(team_id)
        return team

    def is_valid_name(self, name):
        """
        Validate that the team name contains only valid characters.
        Valid characters: A-Z, a-z, Danish characters (æ, ø, å), and digits (0-9).
        No spaces are allowed.
        """
        # Using a regular expression to match the allowed characters
        return bool(re.fullmatch(r"[a-zA-ZæøåÆØÅ0-9]+", name))

    def verify_login(self, team_name, password):
        """
        Verify if the team credentials (team_name, password) are correct.
        Returns the team object if successful, otherwise False.
        """
        # Retrieve team information from the database
        team = self.teamDB.get_team_information(team_name)
        
        # Check if team exists and if the password matches
        if team and password == team.password:
            return team
        raise ValueError("Wrong username and password")
    
    def get_all_team_players(self, team_id):
        return self.playerDB.get_players_by_team(team_id)


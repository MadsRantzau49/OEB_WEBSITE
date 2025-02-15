import re
from Repositories.TeamDB import TeamDB
from Repositories.PlayerDB import PlayerDB
from Model.Team import Team
from Service.SeasonService import SeasonService
from sqlalchemy.orm import Session
from Service.MatchService import MatchService
from Model.TeamData import TeamData
from Repositories.FineDB import FineDB
from Model.FineType import FineType

class TeamService:
    def __init__(self):
        # Initialize the other layers
        self.team_DB = TeamDB()
        self.player_DB = PlayerDB()
        self.season_service = SeasonService()
        self.match_service = MatchService()
        self.fine_DB = FineDB()
    def create_team(self, team_name, club_name, password):
        """
        Creates a new team, verifying that the team name is unique and valid.
        If the team is successfully created, returns the team object.
        """
        # Validate team name format
        if not self.is_valid_name(team_name):
            raise ValueError("Invalid team name. Only letters, numbers, and Danish characters are allowed, no spaces.")
        
        # Check if team already exists
        if self.team_DB.team_already_exist(team_name):
            raise ValueError("Team name already exists. Please choose a different name.")
        
        # Create the Team object
        team = Team(team_name=team_name, club_name=club_name, password=password)

        # Add the team to the database
        team_id = self.team_DB.add_team(team)

        # Create a default season
        season = self.season_service.create_first_season(team_id)
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
        team = self.team_DB.get_team_information(team_name)
        
        # Check if team exists and if the password matches
        if team and password == team.password:
            return team
        raise ValueError("Wrong username and password")
    
    def get_all_team_players(self, team_id):
        return self.player_DB.get_players_by_team(team_id)

    def get_all_edit_team_informations(self, season_id):
        season = self.season_service.find_season_by_id(season_id)
        team = self.get_team_by_id(season.team_id)
        players = self.get_all_team_players(team.id)
        seasonList = self.season_service.get_all_seasons_from_team(team.id)        
        matches = self.match_service.get_matches_by_season(season.id)
        fines = self.fine_DB.get_team_fines_without_custom_type(team.id)
        type_list = [t for t in FineType]
    
        return TeamData(team, season, players, seasonList, matches, fines, type_list)

    def get_team_by_id(self, team_id):
        return self.team_DB.get_team_by_id(team_id)
    
    def get_suggested_players(self, season_id):
        season = self.season_service.find_season_by_id(season_id)
        team = self.get_team_by_id(season.team_id)

        team_players = self.get_all_team_players(season.team_id)
        team_player_dbu_names = [player.dbu_name for player in team_players]
        
        matches = self.match_service.get_matches_by_season(season.id)
        suggested_player_list = []

        for match in matches:
            match_player_list = self.match_service.find_team_lineup(match.match_url_id, team.club_name)
            for player in match_player_list:
                if player not in team_player_dbu_names and player not in suggested_player_list:
                    suggested_player_list.append(player)
        
        if not suggested_player_list:
            raise ValueError("No suggested players found, (they are found by players who had played on season matches and the club name)")
        return suggested_player_list                     

    def get_team_by_season_id(self, season_id):
        season = self.season_service.find_season_by_id(season_id)
        return self.get_team_by_id(season.team_id)
    
    def edit_team(self, team_id, password, club_name, introduction_text):

        team = self.get_team_by_id(team_id)
        team.password = password
        team.club_name = club_name
        team.introduction_text = introduction_text

        return self.team_DB.edit_team(team)
        
        
    def get_team_by_name(self, team_name):
        return self.team_DB.get_team_by_name(team_name)
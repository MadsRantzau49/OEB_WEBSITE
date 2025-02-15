from sqlalchemy.orm import Session
from Model.Team import Team
from Database.database_setup import SessionLocal
from .session_handler import session_handler

class TeamDB:       
    def __init__(self):
        self.db_session = SessionLocal()

    @session_handler
    def team_already_exist(self, team_name: str) -> bool:
        team = self.db_session.query(Team).filter(Team.team_name == team_name).first()
        return team is not None

    @session_handler
    def add_team(self, team: Team) -> int:
        self.db_session.add(team)
        self.db_session.commit()
        self.db_session.refresh(team)  # Refresh the object to get the team ID
        return team.id
    
    @session_handler
    def get_team_information(self, team_name: str) -> Team:
        team = self.db_session.query(Team).filter(Team.team_name == team_name).first()
        return team
    
    @session_handler
    def get_team_by_id(self, team_id) -> Team:
        return self.db_session.query(Team).filter(Team.id == team_id).first()

    @session_handler
    def get_all_teams(self) -> list:
        teams = self.db_session.query(Team).all()
        return teams

    @session_handler
    def edit_team(self, team):
        self.db_session.merge(team)
        self.db_session.commit()
        return team
    
    @session_handler
    def get_team_by_name(self, team_name):
        return self.db_session.query(Team).filter(Team.team_name == team_name).first()
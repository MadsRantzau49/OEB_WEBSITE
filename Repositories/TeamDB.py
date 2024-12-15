from sqlalchemy.orm import Session
from Model.Team import Team
from database.database_setup import SessionLocal

class TeamDB:       
    def __init__(self):
        self.db_session = SessionLocal()

    def team_already_exist(self, team_name: str) -> bool:
        team = self.db_session.query(Team).filter(Team.team_name == team_name).first()
        return team is not None

    def add_team(self, team: Team) -> int:
        self.db_session.add(team)
        self.db_session.commit()
        self.db_session.refresh(team)  # Refresh the object to get the team ID
        return team.id

    def get_team_information(self, team_name: str) -> Team:
        team = self.db_session.query(Team).filter(Team.team_name == team_name).first()
        return team

    def get_all_teams(self) -> list:
        teams = self.db_session.query(Team).all()
        return teams

    def close(self):
        self.db_session.close()

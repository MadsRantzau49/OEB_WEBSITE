from Repositories.FineDB import FineDB
from Service.TeamService import TeamService
from Model.Fine import Fine

class FineService:
    def __init__(self):
        self.team_service = TeamService()
        self.fine_db = FineDB()

    def add_fine(self, name, description, amount, season_id):
        team = self.team_service.get_team_by_season_id(season_id)
        fine = Fine(name=name, description=description, amount=amount, team_id=team.id)
        self.fine_db.add_fine(fine)

    def edit_fine(self, fine_id, name, description, amount):
        fine = self.get_fine_by_id(fine_id)
        fine.name = name
        fine.description = description
        fine.amount = amount
        return self.fine_db.update_fine(fine)

    def remove_fine(self, fine_id):
        fine = self.get_fine_by_id(fine_id)
        self.fine_db.remove_fine(fine)

    def get_fine_by_id(self, fine_id):
        return self.fine_db.get_fine_by_id(fine_id)

    def get_all_team_fines(self, team_id):
        return self.fine_db.get_all_team_fines(team_id)

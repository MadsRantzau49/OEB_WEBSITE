from Repositories.FineDB import FineDB
from Repositories.Player_FineDB import Player_FineDB
from Repositories.SeasonDB import SeasonDB
from Repositories.PlayerDB import PlayerDB
from Repositories.MatchDB import MatchDB
from Repositories.TeamDB import TeamDB
from Model.Fine import Fine
from Model.Player_Fine import Player_Fine
from Model.FineType import FineType


class FineService:
    def __init__(self):
        self.fine_db = FineDB()
        self.player_DB = PlayerDB()
        self.player_fine_DB = Player_FineDB()
        self.season_DB = SeasonDB()
        self.matches_DB = MatchDB()
        self.team_DB = TeamDB()

    def add_fine(self, name, description, amount, season_id, fine_type_value):
        season = self.season_DB.find_season_by_id(season_id)

        fine_type_enum = FineType(fine_type_value)
        if fine_type_enum != FineType.TEAM_FINE and fine_type_enum != FineType.CUSTOM_FINE:
            if self.fine_db.get_fine_from_type(fine_type_enum,season.team_id):                
                raise ValueError(f"You can only create one {fine_type_enum.value} but you can make infinite Team Fines")
        fine = Fine(name=name, description=description, amount=amount, team_id=season.team_id, fine_type=fine_type_enum)
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

    def add_player_fine(self, season_id, fine_id, name, description, amount, player_id):
        season = self.season_DB.find_season_by_id(season_id)

        new_fine = Fine(name=name, description=description, amount=amount, team_id=season.team_id, fine_type=FineType.CUSTOM_FINE)
        # The fine id is equal 0 if its an existing fine
        if fine_id != "0":
            # This is only for if the fine is known but something is changed such as the amount, name or description in somewhatever case :_D
            existing_fine = self.fine_db.get_fine_by_id(fine_id)
            # (hope future me understand this) because its a trash solution.
            if not self.is_the_fines_equal(existing_fine,new_fine):
                fine_id = self.fine_db.add_fine(new_fine).id

            player_fine = Player_Fine(player_id=player_id, fine_id=fine_id, season_id=season_id)
            return self.player_fine_DB.add_player_fine(player_fine)

        # Otherwise is a custom fine.
        new_added_fine = self.fine_db.add_fine(new_fine)
        player_fine = Player_Fine(player_id=player_id, fine_id=new_added_fine.id, season_id=season_id)
        return self.player_fine_DB.add_player_fine(player_fine)
    
    def is_the_fines_equal(self, fine1, fine2):
        if fine1.name != fine2.name:
            return False
        if fine1.description != fine2.description:
            return False
        if int(fine1.amount) != int(fine2.amount):
            return False
        return True
    
    def update_match_fine(self, match_lineup, match, team_id):
        match_fine = self.fine_db.get_match_fine(match.id)
        if not match_fine:
            match_fine = Fine(name=f"{match.home_club[:3]}-{match.away_club[:3]}: {match.home_scored}-{match.away_scored}:", 
                                  description=f"{match.home_scored}-{match.away_scored}: {match.home_club} - {match.away_club} ",
                                  amount=self.calculate_match_total_fine(match.id, team_id),
                                  team_id = team_id,
                                  match_id = match.id,
                                  fine_type = FineType.MATCH_FINE
                                 )
            
            match_fine = self.fine_db.add_fine(match_fine) 

        else:
            match_fine.amount = self.calculate_match_total_fine(match.id, team_id)
            self.fine_db.update_fine(match_fine)
        self.update_player_match_fines(match_fine, match_lineup, match.season_id)
                
    
    def update_player_match_fines(self, match_fine, match_lineup, season_id):
        # First delete all players fines to ensure if players is removed from the DBU lineup they will be deleted.
        self.player_fine_DB.delete_all_player_fines_by_match_id(match_fine.id)

        for player_name in match_lineup:
            player = self.player_DB.find_player_by_dbu_name(player_name, match_fine.team_id)
            if player:
                player_fine = Player_Fine(player_id=player.id, fine_id=match_fine.id, season_id=season_id)
                self.player_fine_DB.add_player_fine(player_fine)

    def calculate_match_total_fine(self, match_id, team_id):
        match = self.matches_DB.find_match_by_id(match_id)
        if match.home_scored is None or match.away_scored is None:
            return None
        team = self.team_DB.get_team_by_id(team_id)

        fine_types = [t for t in FineType]
        
        fines = {fine: (self.fine_db.get_fine_from_type(fine, team_id) or 0) for fine in fine_types}

        fine_amounts = {k: (fines[k].amount if fines[k] else 0) for k in fines}

        amount = 0
        home_won = match.home_scored > match.away_scored
        away_won = match.home_scored < match.away_scored
        draw = match.home_scored == match.away_scored

        if team.club_name.upper() in match.home_club.upper():
            amount += match.home_scored * fine_amounts[FineType.SCORED_GOAL]
            amount += match.away_scored * fine_amounts[FineType.CONCEDED_GOAL]
            amount += fine_amounts[FineType.WIN_FINE] if home_won else 0
            amount += fine_amounts[FineType.DRAW_FINE] if draw else 0
            amount += fine_amounts[FineType.LOSE_FINE] if not home_won and not draw else 0
        else:
            amount += match.away_scored * fine_amounts[FineType.SCORED_GOAL]
            amount += match.home_scored * fine_amounts[FineType.CONCEDED_GOAL]
            amount += fine_amounts[FineType.WIN_FINE] if away_won else 0
            amount += fine_amounts[FineType.DRAW_FINE] if draw else 0
            amount += fine_amounts[FineType.LOSE_FINE] if not away_won and not draw else 0

        return amount

    def update_player_fines_by_season(self, player, season_id):
        player_fines = self.player_fine_DB.get_all_player_fines_by_players_id_and_season(player.id, season_id)
        player.total_fines = 0
        player.fine_list = []
        for player_fine in player_fines:
            fine = self.fine_db.get_fine_by_id(player_fine.fine_id)
            fine.date = player_fine.date
            fine.player_fine_id = player_fine.id
            if not fine.amount:
                fine.amount = 0
            player.total_fines += fine.amount
            player.fine_list.append(fine)
        return player
            
    def delete_player_fine(self, player_fine_id):
        player_fine = self.player_fine_DB.get_player_fine_by_id(player_fine_id)
        self.player_fine_DB.remove_player_fine(player_fine)


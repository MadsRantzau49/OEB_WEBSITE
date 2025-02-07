from Model.FineType import FineType
class TeamData:
    def __init__(self, team, season, players, seasonList, matches, fines, type_list):
        self.team = team
        self.season = season
        self.players = players
        self.seasonList = seasonList
        self.matches = matches
        self.fines = fines
        self.type_list = type_list
        self.FineType = FineType

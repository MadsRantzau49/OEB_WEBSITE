class Match:
    def __init__(self, id: int = None, match_url_id: str = None, team: int = None, 
                 team_scored: int = None, opponent_scored: int = None, fine: int = None, 
                 clothe_washer: int = None, match_played: bool = None, season: int = None):
        self.id = id
        self.match_url_id = match_url_id
        self.team = team
        self.team_scored = team_scored
        self.opponent_scored = opponent_scored
        self.fine = fine
        self.clothe_washer = clothe_washer
        self.match_played = match_played
        self.season = season

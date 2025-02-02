import enum

class FineType(enum.Enum):
    TEAM_FINE = "Team fine"
    WIN_FINE = "Win fine"
    DRAW_FINE = "Draw fine"
    LOSE_FINE = "Lose fine"
    CONCEDED_GOAL = "Conceded goals fine"
    SCORED_GOAL = "Scored goals fine"
    CUSTOM_FINE = "Custom fine"
    MATCH_FINE = "Match Fine"


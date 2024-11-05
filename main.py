from append_data.teams import add_team
from append_data.players import add_player
from append_data.match import update_match_content, add_match
from append_data.player_match import find_game_lineup, add_player_match
from append_data.money import read_trans, reset_deposit_total_fines_balance, find_game_fines, find_extra_fines, update_balance, update_fines
from model.RunSQLDB import run_sql #takes the sql string as input


# Mostly used SQL for debug:
# run_sql("UPDATE matches SET oeb_scored = NULL, opp_scored = NULL, fine = NULL, match_played = 0") # reset matches
# run_sql("DELETE FROM player_match") # Remove all player match rows. 

# Finance
def update_finance(team,season):
    player_list = run_sql(f"SELECT id, mobilepay_name FROM players WHERE team = {team}")
    reset_deposit_total_fines_balance()
    read_trans(player_list)
    
    for player in player_list:
        player_id = player[0]
        print(player_id)
        game_fines = find_game_fines(player_id,season)
        extra_fines = find_extra_fines(player_id,season)
        update_fines(game_fines,extra_fines)
        update_balance()


def update_boedekasse(team,season,match_list):
    player_list = run_sql(f"SELECT id, dbu_name FROM players WHERE team = {team}")
   
    for match in match_list:
        match_id, match_url = match
        try:
            update_match_content(match_id, match_url)  # Finding game result and add match fine.
            # Find the players who played the game.
            string_player_list = find_game_lineup(match_url)
            for player in player_list:
                player_id, player_dbu_name = player
                if player_dbu_name in string_player_list:
                    add_player_match(player_id, match_id)
        except Exception as e:
            # Only handle the exception here and print the error once
            print(f"Data not found on match: \nid: {match_id}\nurl: {match_url}\n")
print("THIS PAGE SHOULD BE DELETED IN THE FUTURE")
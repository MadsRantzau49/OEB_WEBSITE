import pandas as pd
from model.RunSQLDB import run_sql #takes the sql string as input

def read_trans(player_list):
    # Load the Excel or CSV file
    df = pd.read_excel('./database/trans.xlsx')

    # Ensure the 'Date' column is in datetime format
    df['Date'] = pd.to_datetime(df['Date'], format='%d/%m/%Y %H:%M')

    # Define the cutoff date
    cutoff_date = pd.Timestamp('2024-03-10')

    # Process data line by line using the 'iterrows()' method, ignoring rows where date < 2024-03-10
    for index, row in df.iterrows():
        date = row['Date']
        
        # Skip the row if the date is before the cutoff date
        if date < cutoff_date:
            continue
        
        # Extract other data from each row
        name = row['Name']
        # type_ = row['Type']
        # number = row['Number']
        # message = row['Message']
        amount = row['Amount']
        currency = row['Currency']
        transaction_type = row['Transaction type']
        
        for player in player_list:
            player_id, mobilepay_player_name = player
            if mobilepay_player_name == name and currency == "DKK" and transaction_type == "Pay in":
                run_sql(f"UPDATE players SET deposit = deposit + {amount} WHERE id = {player_id}")


def find_game_fines(player_id, season):
    fines = run_sql(f"SELECT m.fine FROM matches m JOIN player_match pm ON m.id = pm.match WHERE pm.player = {player_id} AND m.season = {season}")
    return sum(fine[0] for fine in fines) if fines else 0
         
def find_extra_fines(player_id, season):
    fines = run_sql(f"SELECT amount FROM extra_fines WHERE player = {player_id} AND season = {season}")
    return sum(fine[0] for fine in fines) if fines else 0

def update_fines(game_fines,extra_fines):
    run_sql(f"UPDATE players SET total_fines = {game_fines+extra_fines}")

def update_balance():
    run_sql(f"UPDATE players SET balance = deposit - total_fines")

def reset_deposit_total_fines_balance():
    run_sql("UPDATE players SET deposit = 0, total_fines = 0, balance = 0")
    

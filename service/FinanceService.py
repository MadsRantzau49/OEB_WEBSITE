from Service.TeamService import TeamService
from Model.MobilePayTransaction import MobilePayTransaction
from Repositories.FinanceDB import FinanceDB
from Repositories.SeasonDB import SeasonDB
from Repositories.PlayerDB import PlayerDB

import io
import pandas as pd
from datetime import datetime


class FinanceService:
    def __init__(self):
        self.team_service = TeamService()
        self.finance_DB = FinanceDB()
        self.season_DB = SeasonDB()
        self.player_DB = PlayerDB()

    def upload_file(self, file, season_id):
        team = self.team_service.get_team_by_season_id(season_id)
        file_data = file.read()
        mobilepay_file = MobilePayTransaction(excel_file=file_data, team_id=team.id)

        self.delete_team_files(team.id)                

        self.finance_DB.upload_file(mobilepay_file)
        return mobilepay_file

    def delete_team_files(self, team_id):
        team_files = self.finance_DB.get_all_team_files(team_id)
        for file in team_files:
            self.finance_DB.delete_file(file)

    def update_team_finance(self, mobilePayTransaction, season_id):
        try:
            players = self.player_DB.get_players_by_team(mobilePayTransaction.team_id)

            self.reset_all_team_players_deposit(players)


            file_stream = io.BytesIO(mobilePayTransaction.excel_file)

            df = pd.read_excel(file_stream, engine="openpyxl")

            season = self.season_DB.find_season_by_id(season_id)
            start_date = pd.to_datetime(season.start_date)
            end_date = pd.to_datetime(season.end_date)

            # Process data line by line using the 'iterrows()' method, ignoring rows where date < 2024-03-10
            for index, row in df.iterrows():
                date = row['Date']
                if end_date and date > end_date:
                    continue
                if date < start_date:
                    continue

                name = row['Name']
                # type_ = row['Type']
                # number = row['Number']
                message = row['Message']
                amount = row['Amount']
                currency = row['Currency']
                transaction_type = row['Transaction type']

                if transaction_type == "Pay out":
                    continue

                for player in players:
                    if player.mobilepay_name.lower() == name.lower() or player.dbu_name.lower() == str(message).lower().strip():
                        player.deposit += amount
                        self.player_DB.update_player(player)
        except Exception as e:
            raise ValueError("Fejl opstod ved upload af filen. Prøv igen")


    def reset_all_team_players_deposit(self, players):
        for player in players:
            player.deposit = 0
            self.player_DB.update_player(player)
    

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
    

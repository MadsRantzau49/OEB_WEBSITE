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
    

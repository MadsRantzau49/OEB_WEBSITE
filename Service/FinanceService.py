from Service.TeamService import TeamService
from Model.MobilePayTransaction import MobilePayTransaction
from Model.MobilePay_Row import MobilePay_Row
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

    def update_player_deposit_by_season(self, player, season_id):
        try:
            season = self.season_DB.find_season_by_id(season_id)
            mobilePayTransaction = self.finance_DB.get_team_file(season.team_id)
            player.total_deposit = 0
            player.deposit_list = []
            if not mobilePayTransaction:
                return player
            file_stream = io.BytesIO(mobilePayTransaction.excel_file)

            df = pd.read_excel(file_stream, engine="openpyxl")

            start_date = pd.to_datetime(season.start_date)
            end_date = pd.to_datetime(season.end_date)


            # Process data line by line using the 'iterrows()' method, ignoring rows where date < 2024-03-10
            for index, row in df.iterrows():
                date = row.get('Date', row.get('Dato'))
                if end_date and date > end_date:
                    continue
                if date < start_date:
                    continue

                name = row.get('Name', row.get('Navn'))
                # type_ = row['Type']
                # number = row.get('Number', row.get('Nummer'))
                message = row.get('Message', row.get('Besked')) or ""
                amount = row.get('Amount', row.get('Beløb'))
                currency = row.get('Currency', row.get('Valuta'))
                transaction_type = row.get('Transaction type', row.get('Transaktionstype'))
                print("\n", name, message, amount, currency, transaction_type, "\n\n\n\n\n")

                if transaction_type == "Pay out":
                    continue

                if player.mobilepay_name.lower() == name.lower() or player.mobilepay_name.lower() == str(message).lower().strip():
                    player.total_deposit += amount
                    mobilepay_row = MobilePay_Row(name, message, amount, date=date)
                    player.deposit_list.append(mobilepay_row)
        
            return player
        
        except Exception as e:
            raise ValueError("Fejl opstod ved upload af filen. Prøv igen")


    def reset_all_team_players_deposit(self, players):
        for player in players:
            player.deposit = 0
            self.player_DB.update_player(player)
    

    def get_all_season_expenses(self, season_id):
        try:
            season = self.season_DB.find_season_by_id(season_id)

            mobilePayTransaction = self.finance_DB.get_team_file(season.team_id)
            if not mobilePayTransaction:
                return []
            file_stream = io.BytesIO(mobilePayTransaction.excel_file)

            df = pd.read_excel(file_stream, engine="openpyxl")

            start_date = pd.to_datetime(season.start_date)
            end_date = pd.to_datetime(season.end_date)

            # Process data line by line using the 'iterrows()' method, ignoring rows where date < 2024-03-10
            
            mobilepay_rows = []

            for index, row in df.iterrows():
                date = row.get('Date', row.get('Dato'))
                if end_date and date > end_date:
                    continue
                if date < start_date:
                    continue

                name = row.get('Name', row.get('Navn'))
                # type_ = row['Type']
                # number = row.get('Number', row.get('Nummer'))
                message = row.get('Message', row.get('Besked')) or ""
                amount = row.get('Amount', row.get('Beløb'))
                currency = row.get('Currency', row.get('Valuta'))
                transaction_type = row.get('Transaction type', row.get('Transaktionstype'))
                print("\n", name, message, amount, currency, transaction_type, "\n\n\n\n\n")
                if transaction_type == "Pay in":
                    continue

                if transaction_type == "Pay out":
                    date_shorted = pd.to_datetime(date).strftime("%Y-%m-%d")
                    row = MobilePay_Row(name=name, message=message, amount=amount, date=date_shorted)
                    mobilepay_rows.append(row)
            return mobilepay_rows
        except Exception as e:
            raise ValueError("Fejl opstod ved upload af filen. Prøv igen")
        
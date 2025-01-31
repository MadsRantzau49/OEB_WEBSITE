from flask import Blueprint, request, render_template
from Service.TeamDataService import TeamDataService
from Service.FinanceService import FinanceService

# Initialize the service
team_data_service = TeamDataService()
finance_service = FinanceService()

# Define the Blueprint
finance_controller = Blueprint('finance_controller', __name__)

@finance_controller.route("/add_mobilepay_transactions", methods=["POST"])
def add_file():
    try:
        season_id = request.form.get("season_id",None)

        file = request.files["mobilepay_transaction_file"]
        mobilePayTransaction = finance_service.upload_file(file, season_id)
        
        finance_service.update_team_finance(mobilePayTransaction, season_id)

        return team_data_service.edit_team_data_html(season_id)
    
    except ValueError as e:
        return team_data_service.edit_team_data_html(season_id, error=e)
    except Exception as e:
        return render_template('index.html', error=e)

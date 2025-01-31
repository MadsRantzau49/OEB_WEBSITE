from flask import render_template
from .TeamService import TeamService


class TeamDataService:
    def __init__(self):
         self.team_service = TeamService()
    def edit_team_data_html(self, season_id, *args, **kwargs):
        try:
            edit_team_data = self.team_service.get_all_edit_team_informations(season_id)
            
            return render_template('edit_team.html', edit_team_data=edit_team_data, **kwargs)
    
        except Exception as e:
            # In case of error, render index.html with error
            return render_template('index.html', error=e)

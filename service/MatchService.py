from bs4 import BeautifulSoup
import requests
import re
import json

from Model.Match import Match
from Repositories.MatchDB import MatchDB

class MatchService(Match):
    match = Match()
    
    #find a match result ex ØB VEJGAARD: 2-1
    def find_match_result(self):
        match_result_url = "https://www.dbu.dk/resultater/kamp/" + self.match.match_url_id + "/kampinfo"

        #request html code from dbu.dk
        match_result_html_request = requests.get(match_result_url)
        # Parse HTML using BeautifulSoup
        soup = BeautifulSoup(match_result_html_request.text, 'html.parser')
        
        # Find all team lineup information
        match_result_info = soup.find_all("div", {"class": "sr--match--live-score--result"})
        # Extract text from HTML elements
        match_result_text = [info.get_text() for info in match_result_info]

        match_result_text = re.sub(r'\n\s*\n', '\n', match_result_text[0]).strip()

        # Split the string into lines
        lines = match_result_text.split('\n')

        #Check if OEB is home or away
        if MatchDB.find_club_name in lines[0]:
            self.match.team_scored = int(lines[2])
            self.match.opponent_scored = int(lines[-3])
        else:
            self.match.team_scored = int(lines[-3])
            self.match.opponent_scored = int(lines[2])

    def calculate_fine(self):
        with open('./database/fines.json', 'r') as file:
            data = json.load(file)
        
        won_match_fine = data['won_match']
        draw_match_fine = data['draw_match']
        lost_match_fine = data['lost_match']
        conceded_goal_fine = data['conceded_goal']
        scored_goal_fine = data['scored_goal']

        self.match.fine = 0

        #depends who won 
        self.match.fine += self.match.oeb_won(won_match_fine,lost_match_fine,draw_match_fine)

        #scored goal fine
        self.match.fine += self.match.team_scored * scored_goal_fine
        self.match.fine += self.match.opponent_scored * conceded_goal_fine

    def oeb_won(self, win,lose,draw):
        if(self.match.team_scored > self.match.opponent_scored):
            return win
        elif(self.match.team_scored < self.match.opponent_scored):
            return lose
        else:
            return draw
        
    
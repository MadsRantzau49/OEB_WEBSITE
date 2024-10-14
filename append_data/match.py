import sqlite3
from bs4 import BeautifulSoup
import requests
import re
import json


def add_match(match_url_id,team,season):
    # Connect to the database
    conn = sqlite3.connect('database/database.db') 
    cursor = conn.cursor()

    # Insert a new player into the players table
    cursor.execute('''
    INSERT INTO matches (match_url_id, team, match_played, season)
    VALUES (?, ?, ?)
    ''', (match_url_id, team, False, season,))

    # Commit the changes and close the connection
    conn.commit()
    conn.close()
    print("Match added successfully.")

#find a match result ex ØB VEJGAARD: 2-1
def find_match_result(match_url_id):
    match_result_url = "https://www.dbu.dk/resultater/kamp/" + match_url_id + "/kampinfo"

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
    if "Øster Sundby" in lines[0]:
        oster_sundby_score = int(lines[2])
        opponent_score = int(lines[-3])
    else:
        oster_sundby_score = int(lines[-3])
        opponent_score = int(lines[2])
    return  oster_sundby_score, opponent_score


def calculate_fine(oeb_scored, opp_scored):
    with open('./database/fines.json', 'r') as file:
        data = json.load(file)
    
    won_match = data['won_match']
    draw_match = data['draw_match']
    lost_match = data['lost_match']
    conceded_goal = data['conceded_goal']
    scored_goal = data['scored_goal']

    fine = 0

    #depends who won 
    fine += oeb_won(oeb_scored,opp_scored,won_match,lost_match,draw_match)

    #scored goal fine
    fine += oeb_scored * scored_goal
    fine += opp_scored * conceded_goal

    return fine

def oeb_won(oeb_scored,opp_scored,win,lose,draw):
    if(oeb_scored > opp_scored):
        return win
    elif(oeb_scored < opp_scored):
        return lose
    else:
        return draw
    
def update_match(id, oeb_scored, opp_scored, fine):
    # Connect to the database
    conn = sqlite3.connect('database/database.db') 
    cursor = conn.cursor()

    # Update a match
    cursor.execute('''
    UPDATE matches 
    SET oeb_scored = ?, opp_scored = ?, fine = ?, match_played = ?
    WHERE id = ?
''', (oeb_scored, opp_scored, fine, 1, id ))

    # Commit the changes and close the connection
    conn.commit()
    conn.close()

def update_washer(match_id,player_id):
        # Connect to the database
    conn = sqlite3.connect('database/database.db') 
    cursor = conn.cursor()

    # Update a match
    cursor.execute('''
    UPDATE matches 
    SET clothe_washer = ?, season = ?
    WHERE id = ?
''', (player_id,12024,match_id))

    # Commit the changes and close the connection
    conn.commit()
    conn.close()


def update_match_content(match_id,match_url):
    oeb_scored, opp_scored  = find_match_result(match_url)
    fine = calculate_fine(oeb_scored,opp_scored)
    update_match(match_id,oeb_scored,opp_scored,fine)

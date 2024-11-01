import sqlite3
from bs4 import BeautifulSoup
import requests
import re

def add_player_match(player,match):
    # Connect to the database
    conn = sqlite3.connect('database/database.db') 
    cursor = conn.cursor()

    # Insert a new player into the players table
    cursor.execute('''
    INSERT INTO player_match (player, match)
    VALUES (?, ?)
    ''', (player,match))

    # Commit the changes and close the connection
    conn.commit()
    conn.close()
    print("Match added successfully.")


#Webscrape the player list from DBU webiste
def find_game_lineup(match_id):
    team_lineup_url = "https://www.dbu.dk/resultater/kamp/" + match_id +"/kampinfo"


    #request html code from dbu.dk
    team_lineup_html_request = requests.get(team_lineup_url)
    
    # Parse HTML using BeautifulSoup
    soup = BeautifulSoup(team_lineup_html_request.text, 'html.parser')

    # Find all team lineup information
    team_lineup_info = soup.find_all("div", {"class": "sr--match--team-cards dbu-grid"})
    if not team_lineup_info:
        raise ValueError("Match Not Found")
    
    # Extract text from HTML elements
    team_lineup_text = [info.get_text() for info in team_lineup_info]
    team_lineup_text_string = ""
    for elements in team_lineup_text:
        team_lineup_text_string += elements
    
    team_lineup_text_string = re.sub(r'\n\s*\n', '\n', team_lineup_text_string).strip()

    return team_lineup_text_string

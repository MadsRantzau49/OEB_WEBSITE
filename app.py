from flask import Flask, request, redirect, url_for, render_template
from main import update_finance
from database.sql_runner import run_sql
from append_data.teams import add_team
from append_data.players import add_player
from append_data.match import add_match
app = Flask(__name__)
@app.route('/')
def home():
    return render_template('index.html')

# Route to handle 'Opret Hold' form submission
@app.route('/create_team', methods=['POST'])
def create_team():
    name = request.form['team_name']
    password = request.form['password']
    id = add_team(name,password)
    players = run_sql(f"SELECT dbu_name, mobilepay_name FROM players WHERE team = {id}")
    matches = run_sql(f"SELECT match_url_id FROM matches WHERE team = {id}")
    return render_template('edit_team.html', team_id = id, name = name, players = players, matches = matches )

@app.route('/edit_team', methods=['POST'])
def edit_team():
    try:
        team_id = request.form['team_id']
        season = request.form['season']
        name = run_sql(f"SELECT team_name FROM teams WHERE id = {team_id}")
        players = run_sql(f"SELECT dbu_name, mobilepay_name FROM players WHERE team = {team_id}")
        matches = run_sql(f"SELECT match_url_id FROM matches WHERE team = {team_id} AND season = {season}")
        return render_template('edit_team.html', team_id = team_id, team_name = name[0], players = players, matches = matches, season=season )
    except Exception as e:
        print(f"error\n{e}")
        return "An error occurred", 500

@app.route('/add_player', methods=['POST'])
def add_player_router():
    try:
        team_id = request.form['team_id']
        dbu_name = request.form['player_name']
        mobilepay_name = request.form['mobilepay_name']
        season = request.form['season']
        player_id = add_player(dbu_name,mobilepay_name,team_id)
        name = run_sql(f"SELECT team_name FROM teams WHERE id = {team_id}")
        players = run_sql(f"SELECT dbu_name, mobilepay_name FROM players WHERE team = {team_id}")
        matches = run_sql(f"SELECT match_url_id FROM matches WHERE team = {team_id} AND season = {season}")
        return render_template('edit_team.html', team_id = team_id, team_name = name[0], players = players, matches = matches, season=season )
    except Exception as e:
        print(f"error\n{e}")
        return "An error occurred", 500

@app.route('/add_match', methods=['POST'])
def add_match_router():
    try:
        team_id = request.form['team_id']
        match_url = request.form['match_url']
        season = request.form['season']
        match_id = add_match(match_url,team_id,season)
        name = run_sql(f"SELECT team_name FROM teams WHERE id = {team_id}")
        players = run_sql(f"SELECT dbu_name, mobilepay_name FROM players WHERE team = {team_id}")
        matches = run_sql(f"SELECT match_url_id FROM matches WHERE team = {team_id} AND season = {season}")
        return render_template('edit_team.html', team_id = team_id, team_name = name[0], players = players, matches = matches, season=season )
    except Exception as e:
        print(f"error\n{e}")
        return "An error occurred", 500



# All matches not played yet. 
# match_list = run_sql(f"SELECT id, match_url_id FROM matches WHERE match_played = 0 AND season = {season} AND team = {team}")

app.run(debug=True)

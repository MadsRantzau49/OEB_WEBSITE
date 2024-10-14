from flask import Flask, request, redirect, url_for, render_template
from main import update_finance
from database.sql_runner import run_sql
from append_data.teams import add_team
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
        print("LOOL")
        name = run_sql(f"SELECT team_name FROM teams WHERE id = {team_id}")
        players = run_sql(f"SELECT dbu_name, mobilepay_name FROM players WHERE team = {team_id}")
        matches = run_sql(f"SELECT match_url_id FROM matches WHERE team = {team_id}")
        print(f"id: {team_id}\nname: {name[0][0]}\nplayers: {players}\nmatches: {matches}")
        return render_template('edit_team.html', team_id = team_id, team_name = name[0], players = players, matches = matches )
    except Exception as e:
        print(f"error\n{e}")
        return "An error occurred", 500



# All matches not played yet. 
# match_list = run_sql(f"SELECT id, match_url_id FROM matches WHERE match_played = 0 AND season = {season} AND team = {team}")

app.run(debug=True)

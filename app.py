from flask import Flask, render_template
from controllers.TeamController import team_controller  
from controllers.MatchController import match_controller 
from database.database_setup import initialize_database

app = Flask(__name__)

app.register_blueprint(team_controller)
app.register_blueprint(match_controller)



@app.route('/')
def home():
    return render_template('index.html')

if __name__ == '__main__':
    initialize_database()
    app.run(host='0.0.0.0', port=8080, debug=True)

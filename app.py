from flask import Flask, render_template, jsonify
from Controllers.TeamController import team_controller  
from Controllers.MatchController import match_controller 
from Controllers.PlayerController import player_controller
from Controllers.SeasonController import season_controller
from Controllers.FineController import fine_controller
from Controllers.FinanceController import finance_controller
from Database.database_setup import initialize_database

app = Flask(__name__)

app.register_blueprint(team_controller)
app.register_blueprint(match_controller)
app.register_blueprint(player_controller)
app.register_blueprint(season_controller)
app.register_blueprint(fine_controller)
app.register_blueprint(finance_controller)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/manifest.json/<path>')
def manifest(path):
    print(f"\n\n\n{path}\n\n\n")
    manifest_data = {
        "name": "Essakedøb",
        "short_name": "døb",
        "start_url": "/"+path,  # Dynamic start URL
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": "#000000",
        "icons": [
            {
                "src": "/static/images/rejer.png",
                "sizes": "192x192",
                "type": "image/png"
            },
            {
                "src": "/static/images/rejer.png",
                "sizes": "512x512",
                "type": "image/png"
            }
        ]
    }
    return jsonify(manifest_data)

@app.route('/admin_index')
def admin():
    return render_template('admin_index.html')

if __name__ == '__main__':
    initialize_database()
    app.run(host='0.0.0.0', port=8080, debug=True)


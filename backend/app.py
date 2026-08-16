from flask import Flask, jsonify, request
from werkzeug.exceptions import HTTPException

from .api import api
from .config import Config
from .db import configure_database
from .security import csrf_required, load_current_user


def create_app(config_object=None):
    app = Flask(__name__)
    app.config.from_object(config_object or Config)
    configure_database(app)
    app.register_blueprint(api)

    @app.before_request
    def prepare_request():
        load_current_user()
        return csrf_required()

    @app.after_request
    def add_api_headers(response):
        origin = request.headers.get("Origin")
        if origin and origin == app.config["CORS_ORIGIN"]:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Credentials"] = "true"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, X-CSRF-Token"
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
            response.headers["Vary"] = "Origin"
        return response

    @app.route("/api/v1/<path:_path>", methods=["OPTIONS"])
    def options(_path):
        return ("", 204)

    @app.errorhandler(413)
    def too_large(_error):
        return jsonify({"error": "file_too_large"}), 413

    @app.errorhandler(HTTPException)
    def http_error(error):
        return jsonify({"error": error.name.lower().replace(" ", "_")}), error.code

    @app.errorhandler(Exception)
    def unhandled(error):
        app.logger.exception("Unhandled application error", exc_info=error)
        return jsonify({"error": "internal_server_error"}), 500

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)

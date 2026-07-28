from pathlib import Path
from datetime import timedelta
import os


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "change-this-secret-key")
    DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR / 'app.db'}")
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024
    SESSION_COOKIE_NAME = "oeb_session"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.getenv("SESSION_COOKIE_SECURE", "0") == "1"
    PERMANENT_SESSION_LIFETIME = timedelta(days=int(os.getenv("SESSION_DAYS", "365")))
    SESSION_REFRESH_EACH_REQUEST = True
    CORS_ORIGIN = os.getenv("CORS_ORIGIN", "http://localhost:5173")
    DBU_REQUEST_TIMEOUT = float(os.getenv("DBU_REQUEST_TIMEOUT", "20"))
    DBU_BASE_URL = os.getenv("DBU_BASE_URL", "https://www.dbu.dk")
    AUTO_CREATE_SCHEMA = os.getenv("AUTO_CREATE_SCHEMA", "1") == "1"

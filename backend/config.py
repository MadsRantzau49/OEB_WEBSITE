from pathlib import Path
from datetime import timedelta
import os


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"


def env_float(name, default):
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return float(default)


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
    MOBILEPAY_DRIVE_FOLDER_ID = os.getenv(
        "MOBILEPAY_DRIVE_FOLDER_ID", "1rWyT4SikqoSun-Xe7KRNbmBaT-Dp1Xm1"
    )
    MOBILEPAY_DRIVE_SQUAD_ID = os.getenv("MOBILEPAY_DRIVE_SQUAD_ID", "1")
    MOBILEPAY_DRIVE_CREDENTIALS_FILE = os.getenv(
        "MOBILEPAY_DRIVE_CREDENTIALS_FILE",
        "/run/secrets/google-drive/service-account.json",
    )
    MOBILEPAY_DRIVE_REQUEST_TIMEOUT = env_float("MOBILEPAY_DRIVE_REQUEST_TIMEOUT", 20)
    MOBILEPAY_DRIVE_MAX_FILE_BYTES = 10 * 1024 * 1024
    MOBILEPAY_DRIVE_AUTO_IMPORT = os.getenv("MOBILEPAY_DRIVE_AUTO_IMPORT", "1") == "1"
    MOBILEPAY_DRIVE_POLL_SECONDS = env_float("MOBILEPAY_DRIVE_POLL_SECONDS", 60)
    MOBILEPAY_DRIVE_LOCK_FILE = os.getenv(
        "MOBILEPAY_DRIVE_LOCK_FILE", "/tmp/oeb-mobilepay-drive.lock"
    )
    AUTO_CREATE_SCHEMA = os.getenv("AUTO_CREATE_SCHEMA", "1") == "1"

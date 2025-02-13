from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker
import os

Base = declarative_base()

def get_database_url(db_filename="database.db"):
    """Generate a database URL based on the given filename."""
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    DATABASE_PATH = os.path.join(BASE_DIR, db_filename)
    return f'sqlite:///{DATABASE_PATH}'

def create_engine_and_session(db_filename="database.db"):
    """Create an SQLAlchemy engine and sessionmaker dynamically."""
    DATABASE_URL = get_database_url(db_filename)
    engine = create_engine(DATABASE_URL, echo=False)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    # Enable foreign key constraints for SQLite
    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()

    return engine, SessionLocal

# Create default engine and session with "database.db"
engine, SessionLocal = create_engine_and_session()

def initialize_database(db_filename="database.db"):
    """Initialize the database schema using the specified filename."""
    global engine, SessionLocal  # Ensure changes apply globally
    engine, SessionLocal = create_engine_and_session(db_filename)
    Base.metadata.create_all(bind=engine)

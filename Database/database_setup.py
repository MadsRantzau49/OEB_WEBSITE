from sqlalchemy import create_engine, event
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os

Base = declarative_base()

Base = declarative_base()

BASE_DIR = os.path.abspath(os.path.dirname(__file__))  # Gets the absolute path of the script's directory
DATABASE_PATH = os.path.join(BASE_DIR, "database.db")

DATABASE_URL = f'sqlite:///{DATABASE_PATH}'

engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Enable foreign key constraints for SQLite
@event.listens_for(engine, "connect")
def enable_foreign_keys(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON;")
    cursor.close()

def initialize_database():
    Base.metadata.create_all(bind=engine)

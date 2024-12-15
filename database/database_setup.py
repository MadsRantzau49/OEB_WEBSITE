from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()

DATABASE_URL = 'sqlite:///database/database.db'
engine = create_engine(DATABASE_URL, echo=False)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def initialize_database():
    # Import models inside the function to avoid circular import issues
    from Model.Team import Team
    from Model.Season import Season
    from Model.Player import Player
    from Model.Match import Match
    from Model.Season_Match import Season_Match
    from Model.Player_Match import Player_Match
    from Model.Extra_Fine import Extra_Fine

    # Create all tables in the database
    Base.metadata.create_all(bind=engine)

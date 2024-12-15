from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from database.database_setup import SessionLocal, engine

class RunSQLDB:
    def __init__(self):
        self.database_url = "sqlite:///database/database.db"  # The same path as before, updated for SQLAlchemy
        self.engine = engine
        self.SessionLocal = SessionLocal

    def connect_to_database(self):
        # Create a session to interact with the database
        session = self.SessionLocal()  # This session is equivalent to a cursor in SQLite3
        return session

    def close_database_connection(self, session):
        # Commit and close the session
        try:
            session.commit()
        except SQLAlchemyError as e:
            print(f"An error occurred while committing: {e}")
        finally:
            session.close()

    def search_in_database(self, sql):
        # Use the session to perform raw SQL queries
        session = self.connect_to_database()

        try:
            # Execute raw SQL query
            result = session.execute(sql).fetchall()
        except SQLAlchemyError as e:
            print(f"An error occurred: {e}")
            result = None
        finally:
            self.close_database_connection(session)

        return result

    def update_database(self, sql):
        # Use the session to execute UPDATE statements or other changes
        session = self.connect_to_database()

        try:
            # Execute raw SQL query for an update
            session.execute(sql)
        except SQLAlchemyError as e:
            print(f"An error occurred: {e}")
        finally:
            self.close_database_connection(session)

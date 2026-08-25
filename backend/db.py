from contextlib import contextmanager
import os

from flask import current_app, g
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker


Base = declarative_base()
SessionLocal = None
engine = None


def configure_database(app):
    """Create the engine once per application instance."""
    global SessionLocal, engine

    database_url = app.config["DATABASE_URL"]
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    engine = create_engine(database_url, future=True, pool_pre_ping=True, connect_args=connect_args)

    if database_url.startswith("sqlite"):
        @event.listens_for(engine, "connect")
        def enable_sqlite_foreign_keys(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)

    if database_url.startswith("sqlite"):
        database_path = database_url.removeprefix("sqlite:///")
        database_directory = os.path.dirname(database_path)
        if database_directory:
            os.makedirs(database_directory, exist_ok=True)

    from . import models  # noqa: F401
    if app.config["AUTO_CREATE_SCHEMA"]:
        # Local development and the one-shot init container use this bootstrap.
        # Production web workers wait for that init container instead, avoiding
        # concurrent CREATE TABLE statements during Gunicorn startup.
        Base.metadata.create_all(bind=engine)
        upgrade_schema(engine)

    @app.teardown_appcontext
    def close_database_session(_exception=None):
        database_session = g.pop("database_session", None)
        if database_session is not None:
            database_session.close()


def get_db():
    if "database_session" not in g:
        g.database_session = SessionLocal()
    return g.database_session


def upgrade_schema(database_engine):
    """Apply small additive upgrades for databases created before migrations existed."""
    inspector = inspect(database_engine)
    if "fine_rules" not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns("fine_rules")}
    if "per_minute_amount_cents" not in columns:
        with database_engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE fine_rules ADD COLUMN "
                    "per_minute_amount_cents INTEGER NOT NULL DEFAULT 0"
                )
            )


@contextmanager
def session_scope():
    if SessionLocal is None:
        raise RuntimeError("Database has not been configured")
    database_session = SessionLocal()
    try:
        yield database_session
        database_session.commit()
    except Exception:
        database_session.rollback()
        raise
    finally:
        database_session.close()

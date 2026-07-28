"""Cron entrypoint: sync every configured DBU season without a web request."""

from .app import app
from .db import get_db
from .models import Squad
from .services import sync_squad


def run():
    with app.app_context():
        database_session = get_db()
        for squad in database_session.query(Squad).filter(Squad.active.is_(True)).all():
            report = sync_squad(database_session, squad, timeout=app.config["DBU_REQUEST_TIMEOUT"])
            database_session.commit()
            app.logger.info("DBU sync completed: %s", report)


if __name__ == "__main__":
    run()

"""Poll Holdsport and apply RSVP fines when each configured lead time is reached."""

import time

from .app import app
from .db import get_db
from .holdsport import HoldsportClient
from .models import Squad
from .services import sync_holdsport


client = None


def run():
    global client
    with app.app_context():
        database_session = get_db()
        squad_id = app.config["HOLDSPORT_SQUAD_ID"]
        squad = database_session.get(Squad, squad_id)
        if squad is None or not squad.active:
            app.logger.error("Holdsport squad %s is missing or inactive", squad_id)
            return None
        if client is None:
            client = HoldsportClient(
                app.config["HOLDSPORT_USERNAME"],
                app.config["HOLDSPORT_PASSWORD"],
                team_id=app.config["HOLDSPORT_TEAM_ID"],
                base_url=app.config["HOLDSPORT_BASE_URL"],
                timeout=app.config["HOLDSPORT_REQUEST_TIMEOUT"],
                time_zone=app.config["HOLDSPORT_TIME_ZONE"],
            )
        report = sync_holdsport(
            database_session, squad, app.config, apply_fines=True, client=client
        )
        if "holdsport_sync_failed" in report["errors"]:
            client = None
        database_session.commit()
        app.logger.info("Holdsport sync completed: %s", report)
        return report


def run_forever():
    interval = max(60, app.config["HOLDSPORT_POLL_SECONDS"])
    while True:
        started_at = time.monotonic()
        run()
        elapsed = time.monotonic() - started_at
        time.sleep(max(1, interval - elapsed))


if __name__ == "__main__":
    run_forever()

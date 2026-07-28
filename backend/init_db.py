"""Create the initial schema once before production workers start."""

from .app import app
from .db import get_db
from .models import DbuSource, Season
from .services import deduplicate_mobilepay_transactions
from sqlalchemy import select


if __name__ == "__main__":
    with app.app_context():
        database_session = get_db()
        for season in database_session.scalars(select(Season).where(Season.dbu_url.is_not(None))):
            exists = database_session.scalar(
                select(DbuSource.id).where(
                    DbuSource.season_id == season.id,
                    DbuSource.url == season.dbu_url,
                )
            )
            if not exists:
                database_session.add(
                    DbuSource(season_id=season.id, label="DBU hold 1", url=season.dbu_url)
                )
        removed_duplicates = deduplicate_mobilepay_transactions(database_session)
        database_session.commit()
        app.logger.info("Database schema is ready; removed %s duplicate MobilePay rows", removed_duplicates)

"""Import new MobilePay XLSX files copied into the automatic inbox."""

from hashlib import sha256
import os
from pathlib import Path

from sqlalchemy import select

from .app import app
from .db import get_db
from .models import MobilePayImport, Squad
from .services import process_mobilepay_import


def run():
    inbox = Path(os.getenv("MOBILEPAY_INBOX_PATH", "/inbox"))
    squad_id = int(os.getenv("MOBILEPAY_INBOX_SQUAD_ID", "0") or 0)
    if not inbox.exists():
        return

    with app.app_context():
        database_session = get_db()
        squad = database_session.get(Squad, squad_id) if squad_id else database_session.scalar(
            select(Squad).where(Squad.active.is_(True)).order_by(Squad.id)
        )
        if squad is None:
            raise RuntimeError("No active squad found for the MobilePay inbox")

        for file_path in sorted(inbox.glob("*.xlsx")):
            file_data = file_path.read_bytes()
            file_hash = sha256(file_data).hexdigest()
            if database_session.scalar(
                select(MobilePayImport.id).where(
                    MobilePayImport.squad_id == squad.id,
                    MobilePayImport.file_sha256 == file_hash,
                )
            ):
                continue
            try:
                _mobilepay_import, report = process_mobilepay_import(
                    database_session, squad, file_path.name, file_data
                )
                database_session.commit()
                print(f"Imported {file_path.name}: {report}", flush=True)
            except Exception as error:
                database_session.rollback()
                print(f"Could not import {file_path.name}: {error}", flush=True)


if __name__ == "__main__":
    run()

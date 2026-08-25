"""Poll Google Drive and import the newest MobilePay workbook."""

from datetime import datetime, timedelta, timezone
import time

from .db import get_db
from .google_drive import (
    MobilePayDriveError,
    download_latest_xlsx,
    is_google_drive_configured,
    mobilepay_drive_import_lock,
    service_account_email,
)
from .mobilepay import MobilePayImportError
from .models import MobilePayDriveState, Squad
from .services import commit_mobilepay_import


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def configured_squad_id(config):
    try:
        return int(config.get("MOBILEPAY_DRIVE_SQUAD_ID"))
    except (TypeError, ValueError):
        return None


def poll_seconds(config):
    try:
        return max(int(float(config.get("MOBILEPAY_DRIVE_POLL_SECONDS", 60))), 10)
    except (TypeError, ValueError):
        return 60


def auto_import_enabled(config):
    value = config.get("MOBILEPAY_DRIVE_AUTO_IMPORT", False)
    return value if isinstance(value, bool) else str(value).strip().lower() in {"1", "true", "yes", "on"}


def _state(database_session, squad_id, folder_id):
    state = database_session.get(MobilePayDriveState, squad_id)
    if state is None:
        state = MobilePayDriveState(squad_id=squad_id, folder_id=folder_id)
        database_session.add(state)
    elif state.folder_id != folder_id:
        state.folder_id = folder_id
        state.last_checked_at = None
        state.last_worker_check_at = None
        state.last_success_at = None
        state.last_error = None
        state.latest_file_id = None
        state.latest_filename = None
        state.latest_modified_time = None
    return state


def record_drive_check(database_session, squad_id, folder_id, *, worker=False):
    state = _state(database_session, squad_id, folder_id)
    state.last_checked_at = utc_now()
    if worker:
        state.last_worker_check_at = state.last_checked_at
    return state


def record_drive_success(database_session, squad_id, folder_id, drive_file, *, worker=False):
    state = record_drive_check(database_session, squad_id, folder_id, worker=worker)
    state.last_success_at = state.last_checked_at
    state.last_error = None
    state.latest_file_id = drive_file.file_id
    state.latest_filename = drive_file.filename
    state.latest_modified_time = drive_file.modified_time
    return state


def record_drive_failure(database_session, squad_id, folder_id, error_code, *, worker=False):
    state = record_drive_check(database_session, squad_id, folder_id, worker=worker)
    state.last_error = error_code
    return state


def mobilepay_drive_status(database_session, config, squad_id):
    folder_id = str(config.get("MOBILEPAY_DRIVE_FOLDER_ID") or "").strip()
    credentials_file = config.get("MOBILEPAY_DRIVE_CREDENTIALS_FILE")
    configured = configured_squad_id(config) == squad_id and is_google_drive_configured(
        folder_id, credentials_file
    )
    state = database_session.get(MobilePayDriveState, squad_id)
    if state is not None and state.folder_id != folder_id:
        state = None

    automatic = auto_import_enabled(config)
    interval = poll_seconds(config)
    if not automatic:
        worker_status = "disabled"
    elif state is None or state.last_worker_check_at is None:
        worker_status = "waiting"
    elif utc_now() - state.last_worker_check_at <= timedelta(seconds=max(interval * 3, 120)):
        worker_status = "running"
    else:
        worker_status = "stale"

    def timestamp(value):
        return value.replace(tzinfo=timezone.utc).isoformat().replace("+00:00", "Z") if value else None

    return {
        "configured": configured,
        "automatic": automatic,
        "pollIntervalSeconds": interval,
        "workerStatus": worker_status,
        "serviceAccountEmail": service_account_email(credentials_file),
        "lastCheckedAt": timestamp(state.last_checked_at) if state else None,
        "lastSuccessAt": timestamp(state.last_success_at) if state else None,
        "lastError": state.last_error if state else None,
        "latestFilename": state.latest_filename if state else None,
        "latestModifiedTime": state.latest_modified_time if state else None,
    }


def poll_once(app):
    squad_id = configured_squad_id(app.config)
    folder_id = str(app.config.get("MOBILEPAY_DRIVE_FOLDER_ID") or "").strip()
    if squad_id is None:
        app.logger.error("Google Drive MobilePay import has no valid squad ID")
        return {"error": "mobilepay_drive_not_configured"}

    with app.app_context():
        database_session = get_db()
        squad = database_session.get(Squad, squad_id)
        if squad is None:
            app.logger.error(
                "Google Drive MobilePay import references missing squad %s", squad_id
            )
            return {"error": "mobilepay_drive_not_configured_for_squad"}
        previous_state = database_session.get(MobilePayDriveState, squad_id)
        previous_error = previous_state.last_error if previous_state and previous_state.folder_id == folder_id else None
        known_file_id = previous_state.latest_file_id if previous_state and previous_state.folder_id == folder_id else None
        known_modified_time = previous_state.latest_modified_time if previous_state and previous_state.folder_id == folder_id else None
        record_drive_check(database_session, squad_id, folder_id, worker=True)
        database_session.commit()
        try:
            with mobilepay_drive_import_lock(
                app.config.get("MOBILEPAY_DRIVE_LOCK_FILE", "/tmp/oeb-mobilepay-drive.lock")
            ):
                drive_file = download_latest_xlsx(
                    folder_id=folder_id,
                    credentials_file=app.config.get("MOBILEPAY_DRIVE_CREDENTIALS_FILE"),
                    timeout=app.config.get("MOBILEPAY_DRIVE_REQUEST_TIMEOUT", 20),
                    max_file_bytes=app.config.get(
                        "MOBILEPAY_DRIVE_MAX_FILE_BYTES", app.config["MAX_CONTENT_LENGTH"]
                    ),
                    known_file_id=known_file_id,
                    known_modified_time=known_modified_time,
                )
                if drive_file.data is None:
                    record_drive_success(
                        database_session, squad_id, folder_id, drive_file, worker=True
                    )
                    database_session.commit()
                    return {
                        "report": {
                            "created": 0,
                            "skipped": True,
                            "unmatched": 0,
                            "ambiguous": 0,
                        },
                        "source": drive_file,
                    }
                mobilepay_import, report = commit_mobilepay_import(
                    database_session, squad, drive_file.filename, drive_file.data
                )
                record_drive_success(
                    database_session, squad_id, folder_id, drive_file, worker=True
                )
                database_session.commit()
            if report.get("skipped") is not True:
                app.logger.info(
                    "Imported %s from Google Drive: %s", drive_file.filename, report
                )
            return {"import": mobilepay_import, "report": report, "source": drive_file}
        except MobilePayDriveError as exc:
            database_session.rollback()
            if exc.code == "mobilepay_drive_import_in_progress":
                return {"error": exc.code}
            record_drive_failure(database_session, squad_id, folder_id, exc.code, worker=True)
            database_session.commit()
            if previous_error != exc.code:
                app.logger.warning(
                    "Google Drive MobilePay poll failed: %s", exc.detail or exc.code
                )
            return {"error": exc.code}
        except MobilePayImportError as exc:
            database_session.rollback()
            record_drive_failure(
                database_session, squad_id, folder_id, "mobilepay_import_failed", worker=True
            )
            database_session.commit()
            if previous_error != "mobilepay_import_failed":
                app.logger.warning("Google Drive MobilePay file could not be imported: %s", exc)
            return {"error": "mobilepay_import_failed"}
        except Exception:
            database_session.rollback()
            record_drive_failure(
                database_session, squad_id, folder_id, "mobilepay_import_failed", worker=True
            )
            database_session.commit()
            app.logger.exception("Unexpected Google Drive MobilePay poll failure")
            return {"error": "mobilepay_import_failed"}


def run_forever():
    from .app import app

    if not auto_import_enabled(app.config):
        app.logger.info("Automatic Google Drive MobilePay import is disabled")
        while True:
            time.sleep(3600)

    interval = poll_seconds(app.config)
    app.logger.info("Checking Google Drive for MobilePay files every %s seconds", interval)
    while True:
        try:
            poll_once(app)
        except Exception:
            app.logger.exception("Unexpected Google Drive worker failure")
        time.sleep(interval)


if __name__ == "__main__":
    run_forever()

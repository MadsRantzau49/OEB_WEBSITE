import json
from io import BytesIO

from openpyxl import Workbook

from backend.db import get_db
from backend.google_drive import GoogleDriveFile, MobilePayDriveError, mobilepay_drive_import_lock
from backend.mobilepay_drive_worker import mobilepay_drive_status, poll_once
from backend.models import MobilePayDriveState, MobilePayTransaction
from backend.tests.test_api import make_app, setup_payload


def test_worker_imports_latest_file_and_records_visible_status(tmp_path, monkeypatch):
    app = make_app(tmp_path)
    setup = app.test_client().post("/api/v1/setup", json=setup_payload()).get_json()
    squad_id = setup["squad"]["id"]
    credentials_file = tmp_path / "service-account.json"
    credentials_file.write_text(
        json.dumps(
            {
                "type": "service_account",
                "client_email": "mobilepay@example.test",
                "private_key": "test-key",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        )
    )
    app.config.update(
        MOBILEPAY_DRIVE_FOLDER_ID="folder-123",
        MOBILEPAY_DRIVE_SQUAD_ID=squad_id,
        MOBILEPAY_DRIVE_CREDENTIALS_FILE=str(credentials_file),
        MOBILEPAY_DRIVE_REQUEST_TIMEOUT=9,
        MOBILEPAY_DRIVE_MAX_FILE_BYTES=1024 * 1024,
        MOBILEPAY_DRIVE_LOCK_FILE=str(tmp_path / "mobilepay-drive.lock"),
        MOBILEPAY_DRIVE_AUTO_IMPORT=True,
        MOBILEPAY_DRIVE_POLL_SECONDS=60,
    )

    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Date", "Name", "Type", "Number", "Message", "Amount", "Currency", "Transaction type"])
    sheet.append(["05/05/2026 20:21", "Drive Player", "Transfer", "123", "", 75, "DKK", "Pay in"])
    file_data = BytesIO()
    workbook.save(file_data)
    drive_file = GoogleDriveFile(
        filename="mobilepay-latest.xlsx",
        modified_time="2026-08-16T08:00:00Z",
        data=file_data.getvalue(),
        file_id="drive-file-123",
    )
    download_calls = []

    def fake_download(**options):
        download_calls.append(options)
        if options["known_file_id"] == drive_file.file_id and options["known_modified_time"] == drive_file.modified_time:
            return GoogleDriveFile(
                filename=drive_file.filename,
                modified_time=drive_file.modified_time,
                data=None,
                file_id=drive_file.file_id,
            )
        return drive_file

    monkeypatch.setattr("backend.mobilepay_drive_worker.download_latest_xlsx", fake_download)

    first = poll_once(app)
    second = poll_once(app)

    assert first["report"]["created"] == 1
    assert second["report"]["skipped"] is True
    assert download_calls[0]["known_file_id"] is None
    assert download_calls[1]["known_file_id"] == "drive-file-123"
    with app.app_context():
        database_session = get_db()
        assert database_session.query(MobilePayTransaction).count() == 1
        state = database_session.get(MobilePayDriveState, squad_id)
        assert state.last_worker_check_at is not None
        status = mobilepay_drive_status(database_session, app.config, squad_id)
        assert status["configured"] is True
        assert status["workerStatus"] == "running"
        assert status["latestFilename"] == "mobilepay-latest.xlsx"
        assert status["lastError"] is None

    with mobilepay_drive_import_lock(app.config["MOBILEPAY_DRIVE_LOCK_FILE"]):
        assert poll_once(app) == {"error": "mobilepay_drive_import_in_progress"}
    with app.app_context():
        assert mobilepay_drive_status(get_db(), app.config, squad_id)["lastError"] is None

    def inaccessible_folder(**_options):
        raise MobilePayDriveError("mobilepay_drive_folder_not_found", 404)

    monkeypatch.setattr(
        "backend.mobilepay_drive_worker.download_latest_xlsx", inaccessible_folder
    )
    failed = poll_once(app)
    assert failed == {"error": "mobilepay_drive_folder_not_found"}
    with app.app_context():
        status = mobilepay_drive_status(get_db(), app.config, squad_id)
        assert status["workerStatus"] == "running"
        assert status["lastError"] == "mobilepay_drive_folder_not_found"


def test_worker_does_not_crash_before_the_configured_squad_exists(tmp_path):
    app = make_app(tmp_path)
    app.config.update(
        MOBILEPAY_DRIVE_FOLDER_ID="folder-123",
        MOBILEPAY_DRIVE_SQUAD_ID="999",
    )

    assert poll_once(app) == {"error": "mobilepay_drive_not_configured_for_squad"}

    with app.app_context():
        assert get_db().query(MobilePayDriveState).count() == 0

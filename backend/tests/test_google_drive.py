import json

import pytest
import requests

from backend.google_drive import (
    GoogleDriveClient,
    MobilePayDriveError,
    is_google_drive_configured,
    mobilepay_drive_import_lock,
    service_account_email,
)


class FakeResponse:
    def __init__(self, payload=None, chunks=None, status_code=200, headers=None):
        self.payload = payload
        self.chunks = chunks or []
        self.status_code = status_code
        self.headers = headers or {}
        self.closed = False

    def json(self):
        return self.payload

    def iter_content(self, chunk_size):
        assert chunk_size == 64 * 1024
        for chunk in self.chunks:
            if isinstance(chunk, Exception):
                raise chunk
            yield chunk

    def close(self):
        self.closed = True


class FakeSession:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append((url, kwargs))
        return self.responses.pop(0)


def test_downloads_latest_xlsx_from_configured_folder():
    listing = FakeResponse(
        {
            "files": [
                {
                    "id": "new-file-id",
                    "name": "mobilepay-latest.xlsx",
                    "modifiedTime": "2026-08-16T08:00:00Z",
                    "size": "8",
                },
                {
                    "id": "old-file-id",
                    "name": "mobilepay-old.xlsx",
                    "modifiedTime": "2026-08-15T08:00:00Z",
                    "size": "8",
                },
            ]
        }
    )
    download = FakeResponse(chunks=[b"work", b"book"])
    session = FakeSession(listing, download)

    drive_file = GoogleDriveClient(
        folder_id="folder-123",
        credentials_file="unused-in-test.json",
        timeout=7,
        max_file_bytes=20,
        session=session,
    ).download_latest_xlsx()

    assert drive_file.filename == "mobilepay-latest.xlsx"
    assert drive_file.modified_time == "2026-08-16T08:00:00Z"
    assert drive_file.data == b"workbook"
    assert drive_file.file_id == "new-file-id"
    assert len(session.calls) == 2
    list_url, list_options = session.calls[0]
    assert list_url.endswith("/drive/v3/files")
    assert "'folder-123' in parents" in list_options["params"]["q"]
    assert list_options["params"]["orderBy"] == "modifiedTime desc"
    assert list_options["timeout"] == 7
    download_url, download_options = session.calls[1]
    assert download_url.endswith("/drive/v3/files/new-file-id")
    assert download_options["params"]["alt"] == "media"
    assert download_options["stream"] is True
    assert listing.closed is True
    assert download.closed is True


def test_does_not_download_an_unchanged_latest_file():
    listing = FakeResponse(
        {
            "files": [
                {
                    "id": "same-file-id",
                    "name": "mobilepay.xlsx",
                    "modifiedTime": "2026-08-16T08:00:00Z",
                    "size": "8",
                }
            ]
        }
    )
    session = FakeSession(listing)

    drive_file = GoogleDriveClient(
        folder_id="folder-123",
        credentials_file="unused-in-test.json",
        session=session,
    ).download_latest_xlsx(
        known_file_id="same-file-id",
        known_modified_time="2026-08-16T08:00:00Z",
    )

    assert drive_file.file_id == "same-file-id"
    assert drive_file.data is None
    assert len(session.calls) == 1
    assert listing.closed is True


def test_reports_when_drive_folder_has_no_xlsx_files():
    listing = FakeResponse({"files": []})
    folder = FakeResponse(
        {
            "id": "folder-123",
            "mimeType": "application/vnd.google-apps.folder",
            "trashed": False,
        }
    )
    client = GoogleDriveClient(
        folder_id="folder-123",
        credentials_file="unused-in-test.json",
        session=FakeSession(listing, folder),
    )

    with pytest.raises(MobilePayDriveError) as raised:
        client.download_latest_xlsx()

    assert raised.value.code == "mobilepay_drive_file_not_found"
    assert raised.value.status == 404
    assert listing.closed is True
    assert folder.closed is True


def test_reports_when_configured_folder_is_not_shared():
    listing = FakeResponse({"files": []})
    folder = FakeResponse(status_code=404)
    client = GoogleDriveClient(
        folder_id="folder-123",
        credentials_file="unused-in-test.json",
        session=FakeSession(listing, folder),
    )

    with pytest.raises(MobilePayDriveError) as raised:
        client.download_latest_xlsx()

    assert raised.value.code == "mobilepay_drive_folder_not_found"
    assert raised.value.status == 404
    assert listing.closed is True
    assert folder.closed is True


def test_stops_streaming_when_drive_file_exceeds_limit():
    listing = FakeResponse(
        {
            "files": [
                {
                    "id": "large-file-id",
                    "name": "mobilepay.xlsx",
                    "modifiedTime": "2026-08-16T08:00:00Z",
                }
            ]
        }
    )
    download = FakeResponse(chunks=[b"123", b"456"])
    client = GoogleDriveClient(
        folder_id="folder-123",
        credentials_file="unused-in-test.json",
        max_file_bytes=5,
        session=FakeSession(listing, download),
    )

    with pytest.raises(MobilePayDriveError) as raised:
        client.download_latest_xlsx()

    assert raised.value.code == "file_too_large"
    assert raised.value.status == 413
    assert download.closed is True


def test_maps_drive_permission_errors_to_stable_error():
    listing = FakeResponse(status_code=403)
    client = GoogleDriveClient(
        folder_id="folder-123",
        credentials_file="unused-in-test.json",
        session=FakeSession(listing),
    )

    with pytest.raises(MobilePayDriveError) as raised:
        client.download_latest_xlsx()

    assert raised.value.code == "mobilepay_drive_access_denied"
    assert raised.value.status == 502
    assert listing.closed is True


def test_maps_interrupted_download_to_retryable_error():
    listing = FakeResponse(
        {
            "files": [
                {
                    "id": "file-id",
                    "name": "mobilepay.xlsx",
                    "modifiedTime": "2026-08-16T08:00:00Z",
                }
            ]
        }
    )
    download = FakeResponse(chunks=[b"partial", requests.ReadTimeout("timed out")])
    client = GoogleDriveClient(
        folder_id="folder-123",
        credentials_file="unused-in-test.json",
        session=FakeSession(listing, download),
    )

    with pytest.raises(MobilePayDriveError) as raised:
        client.download_latest_xlsx()

    assert raised.value.code == "mobilepay_drive_unavailable"
    assert download.closed is True


def test_maps_drive_rate_limit_to_retryable_error():
    listing = FakeResponse(
        {"error": {"errors": [{"reason": "rateLimitExceeded"}]}},
        status_code=403,
    )
    client = GoogleDriveClient(
        folder_id="folder-123",
        credentials_file="unused-in-test.json",
        session=FakeSession(listing),
    )

    with pytest.raises(MobilePayDriveError) as raised:
        client.download_latest_xlsx()

    assert raised.value.code == "mobilepay_drive_unavailable"
    assert listing.closed is True


def test_configuration_requires_folder_id_and_credential_file(tmp_path):
    credentials_file = tmp_path / "service-account.json"
    assert is_google_drive_configured("folder-123", credentials_file) is False
    credentials_file.write_text("{}")
    assert is_google_drive_configured("folder-123", credentials_file) is False
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
    assert is_google_drive_configured("folder-123", credentials_file) is True
    assert service_account_email(credentials_file) == "mobilepay@example.test"
    assert is_google_drive_configured("", credentials_file) is False


def test_rejects_a_second_drive_import_while_one_is_running(tmp_path):
    lock_file = tmp_path / "mobilepay-drive.lock"
    with mobilepay_drive_import_lock(lock_file):
        with pytest.raises(MobilePayDriveError) as raised:
            with mobilepay_drive_import_lock(lock_file):
                pass

    assert raised.value.code == "mobilepay_drive_import_in_progress"
    assert raised.value.status == 409

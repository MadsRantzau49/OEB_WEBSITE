from contextlib import contextmanager
from dataclasses import dataclass
import fcntl
import json
from pathlib import Path
import re
from urllib.parse import quote

import requests


DRIVE_API_URL = "https://www.googleapis.com/drive/v3/files"
DRIVE_READONLY_SCOPE = "https://www.googleapis.com/auth/drive.readonly"
XLSX_MIME_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
FOLDER_MIME_TYPE = "application/vnd.google-apps.folder"


class MobilePayDriveError(Exception):
    def __init__(self, code, status=502, detail=None):
        super().__init__(code)
        self.code = code
        self.status = status
        self.detail = detail


@dataclass(frozen=True)
class GoogleDriveFile:
    filename: str
    modified_time: str | None
    data: bytes | None
    file_id: str | None = None


class GoogleDriveClient:
    def __init__(self, folder_id, credentials_file, timeout=20, max_file_bytes=10 * 1024 * 1024, session=None):
        self.folder_id = str(folder_id or "").strip()
        self.credentials_file = str(credentials_file or "").strip()
        self.timeout = float(timeout)
        self.max_file_bytes = int(max_file_bytes)
        self._session = session

    def download_latest_xlsx(self, known_file_id=None, known_modified_time=None):
        if not re.fullmatch(r"[A-Za-z0-9_-]+", self.folder_id):
            raise MobilePayDriveError("mobilepay_drive_not_configured", 503, "Invalid Google Drive folder ID")

        response = self._get(
            DRIVE_API_URL,
            params={
                "q": (
                    f"'{self.folder_id}' in parents and trashed = false "
                    f"and mimeType = '{XLSX_MIME_TYPE}'"
                ),
                "orderBy": "modifiedTime desc",
                "pageSize": 100,
                "fields": "files(id,name,modifiedTime,size)",
                "includeItemsFromAllDrives": "true",
                "supportsAllDrives": "true",
            },
        )
        try:
            self._check_response(response)
            payload = response.json()
        except MobilePayDriveError:
            raise
        except (TypeError, ValueError) as exc:
            raise MobilePayDriveError(
                "mobilepay_drive_unavailable", detail="Google Drive returned invalid JSON"
            ) from exc
        finally:
            response.close()

        files = payload.get("files") if isinstance(payload, dict) else None
        latest = next(
            (
                item
                for item in files or []
                if isinstance(item, dict) and str(item.get("name") or "").lower().endswith(".xlsx")
            ),
            None,
        )
        if latest is None:
            self._assert_folder_accessible()
            raise MobilePayDriveError("mobilepay_drive_file_not_found", 404)

        file_id = str(latest.get("id") or "").strip()
        filename = str(latest.get("name") or "").strip()
        if not file_id or not filename:
            raise MobilePayDriveError(
                "mobilepay_drive_unavailable", detail="Google Drive file metadata is incomplete"
            )

        modified_time = latest.get("modifiedTime")
        if file_id == known_file_id and modified_time == known_modified_time:
            return GoogleDriveFile(
                filename=filename,
                modified_time=modified_time,
                data=None,
                file_id=file_id,
            )

        try:
            declared_size = int(latest["size"])
        except (KeyError, TypeError, ValueError):
            declared_size = None
        if declared_size is not None and declared_size > self.max_file_bytes:
            raise MobilePayDriveError("file_too_large", 413)

        response = self._get(
            f"{DRIVE_API_URL}/{quote(file_id, safe='')}",
            params={"alt": "media", "supportsAllDrives": "true"},
            stream=True,
        )
        try:
            self._check_response(response)
            try:
                content_length = int(response.headers.get("Content-Length", ""))
            except (TypeError, ValueError):
                content_length = None
            if content_length is not None and content_length > self.max_file_bytes:
                raise MobilePayDriveError("file_too_large", 413)

            chunks = []
            downloaded = 0
            for chunk in response.iter_content(chunk_size=64 * 1024):
                if not chunk:
                    continue
                downloaded += len(chunk)
                if downloaded > self.max_file_bytes:
                    raise MobilePayDriveError("file_too_large", 413)
                chunks.append(chunk)
        except MobilePayDriveError:
            raise
        except Exception as exc:
            raise MobilePayDriveError("mobilepay_drive_unavailable", detail=repr(exc)) from exc
        finally:
            response.close()

        return GoogleDriveFile(
            filename=filename,
            modified_time=modified_time,
            data=b"".join(chunks),
            file_id=file_id,
        )

    def _assert_folder_accessible(self):
        response = self._get(
            f"{DRIVE_API_URL}/{quote(self.folder_id, safe='')}",
            params={
                "fields": "id,mimeType,trashed",
                "supportsAllDrives": "true",
            },
        )
        try:
            self._check_response(response, not_found_code="mobilepay_drive_folder_not_found")
            payload = response.json()
        except MobilePayDriveError:
            raise
        except (TypeError, ValueError) as exc:
            raise MobilePayDriveError(
                "mobilepay_drive_unavailable", detail="Google Drive returned invalid folder metadata"
            ) from exc
        finally:
            response.close()
        if not isinstance(payload, dict) or payload.get("mimeType") != FOLDER_MIME_TYPE or payload.get("trashed"):
            raise MobilePayDriveError("mobilepay_drive_folder_not_found", 404)

    def _get(self, url, **kwargs):
        try:
            return self._authorized_session().get(url, timeout=self.timeout, **kwargs)
        except MobilePayDriveError:
            raise
        except Exception as exc:
            raise MobilePayDriveError("mobilepay_drive_unavailable", detail=repr(exc)) from exc

    def _authorized_session(self):
        if self._session is not None:
            return self._session
        if not self.credentials_file or not Path(self.credentials_file).is_file():
            raise MobilePayDriveError(
                "mobilepay_drive_not_configured", 503, "Google service-account file was not found"
            )
        try:
            from google.auth.transport.requests import AuthorizedSession
            from google.oauth2 import service_account
        except ImportError as exc:
            raise MobilePayDriveError(
                "mobilepay_drive_not_configured", 503, "google-auth is not installed"
            ) from exc
        try:
            credentials = service_account.Credentials.from_service_account_file(
                self.credentials_file,
                scopes=[DRIVE_READONLY_SCOPE],
            )
        except Exception as exc:
            raise MobilePayDriveError(
                "mobilepay_drive_not_configured", 503, "Google service-account file is invalid"
            ) from exc
        self._session = AuthorizedSession(credentials)
        return self._session

    @staticmethod
    def _check_response(response, not_found_code="mobilepay_drive_file_not_found"):
        status = response.status_code
        if 200 <= status < 300:
            return
        if status in {401, 403}:
            if status == 403:
                try:
                    payload = response.json()
                    reasons = {
                        item.get("reason")
                        for item in payload.get("error", {}).get("errors", [])
                        if isinstance(item, dict)
                    }
                except (AttributeError, TypeError, ValueError):
                    reasons = set()
                if reasons & {
                    "dailyLimitExceeded",
                    "downloadQuotaExceeded",
                    "rateLimitExceeded",
                    "sharingRateLimitExceeded",
                    "userRateLimitExceeded",
                }:
                    raise MobilePayDriveError(
                        "mobilepay_drive_unavailable", 502, f"Google Drive returned HTTP {status}"
                    )
            raise MobilePayDriveError(
                "mobilepay_drive_access_denied", 502, f"Google Drive returned HTTP {status}"
            )
        if status == 404:
            raise MobilePayDriveError(
                not_found_code, 404, "Google Drive returned HTTP 404"
            )
        raise MobilePayDriveError(
            "mobilepay_drive_unavailable", 502, f"Google Drive returned HTTP {status}"
        )


def _service_account_payload(credentials_file):
    credentials_path = Path(str(credentials_file or ""))
    if not credentials_path.is_file():
        return None
    try:
        payload = json.loads(credentials_path.read_text())
    except (OSError, TypeError, ValueError):
        return None
    return payload if isinstance(payload, dict) else None


def service_account_email(credentials_file):
    payload = _service_account_payload(credentials_file)
    email = payload.get("client_email") if payload else None
    return email.strip() if isinstance(email, str) and email.strip() else None


def is_google_drive_configured(folder_id, credentials_file):
    if not re.fullmatch(r"[A-Za-z0-9_-]+", str(folder_id or "").strip()):
        return False
    payload = _service_account_payload(credentials_file)
    required = ("client_email", "private_key", "token_uri")
    return bool(
        payload
        and payload.get("type") == "service_account"
        and all(isinstance(payload.get(key), str) and payload[key].strip() for key in required)
    )


@contextmanager
def mobilepay_drive_import_lock(lock_file):
    try:
        handle = Path(str(lock_file or "/tmp/oeb-mobilepay-drive.lock")).open("a+")
    except OSError as exc:
        raise MobilePayDriveError("mobilepay_drive_unavailable", detail=repr(exc)) from exc
    try:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise MobilePayDriveError("mobilepay_drive_import_in_progress", 409) from exc
        except OSError as exc:
            raise MobilePayDriveError("mobilepay_drive_unavailable", detail=repr(exc)) from exc
        yield
    finally:
        handle.close()


def download_latest_xlsx(
    folder_id,
    credentials_file,
    timeout=20,
    max_file_bytes=10 * 1024 * 1024,
    known_file_id=None,
    known_modified_time=None,
):
    return GoogleDriveClient(
        folder_id=folder_id,
        credentials_file=credentials_file,
        timeout=timeout,
        max_file_bytes=max_file_bytes,
    ).download_latest_xlsx(
        known_file_id=known_file_id,
        known_modified_time=known_modified_time,
    )

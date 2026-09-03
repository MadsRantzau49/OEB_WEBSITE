from dataclasses import dataclass
from datetime import date, datetime, time
import re
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
import requests


class HoldsportError(RuntimeError):
    pass


@dataclass(frozen=True)
class HoldsportActivityData:
    holdsport_id: str
    title: str
    activity_type: str
    activity_date: date
    starts_at: datetime
    url: str


@dataclass(frozen=True)
class HoldsportParticipantData:
    holdsport_user_id: str
    name: str
    is_coach: bool


@dataclass(frozen=True)
class HoldsportActivityDetails:
    activity_type: str
    start_time: time
    participants: list[HoldsportParticipantData]


def _clean(value):
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _activity_type(item):
    classes = _clean(item.get("className")).casefold()
    if "traening" in classes or "træning" in classes:
        return "Træning"
    if "kamp" in classes:
        return "Kamp"
    return None


def parse_activity_feed(items, time_zone="Europe/Copenhagen"):
    zone = ZoneInfo(time_zone)
    activities = []
    for item in items:
        if item.get("cancelled") is True:
            continue
        activity_type = _activity_type(item)
        if not activity_type:
            continue
        if not item.get("id") or not item.get("start"):
            raise HoldsportError("Holdsport returned a malformed supported activity")
        try:
            starts_at = datetime.fromisoformat(str(item["start"]).replace("Z", "+00:00"))
        except (TypeError, ValueError) as exc:
            raise HoldsportError("Holdsport returned an invalid activity date") from exc
        if starts_at.tzinfo is None:
            starts_at = starts_at.replace(tzinfo=zone)
        local_start = starts_at.astimezone(zone)
        activities.append(
            HoldsportActivityData(
                holdsport_id=str(item["id"]),
                title=_clean(item.get("title")) or f"Holdsport aktivitet {item['id']}",
                activity_type=activity_type,
                activity_date=local_start.date(),
                starts_at=starts_at.astimezone(ZoneInfo("UTC")).replace(tzinfo=None),
                url=f"/activities/{item['id']}",
            )
        )
    return activities


def parse_activity_details(html):
    soup = BeautifulSoup(html, "html.parser")
    event_type_element = soup.select_one(".event_type .info_row_text")
    event_type_text = _clean(event_type_element.get_text(" ", strip=True)) if event_type_element else ""
    activity_type = "Træning" if event_type_text.casefold() == "træning" else "Kamp" if event_type_text.casefold() == "kamp" else None
    time_row = next(
        (
            row
            for row in soup.select(".info_row")
            if (header := row.select_one(".info_row_header"))
            and _clean(header.get_text(" ", strip=True)).casefold() == "tidspunkt"
        ),
        None,
    )
    time_text = _clean(time_row.select_one(".info_row_text").get_text(" ", strip=True)) if time_row and time_row.select_one(".info_row_text") else ""
    time_match = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", time_text)
    if activity_type is None or time_match is None:
        raise HoldsportError("Holdsport activity type or start time could not be found")
    heading = next(
        (
            item
            for item in soup.select(".toggle_collapse_title")
            if _clean(item.get_text(" ", strip=True)).casefold().startswith("ej tilkendegivet")
        ),
        None,
    )
    panel = heading.find_parent(class_="toggle_collapse_wrapper").find_next_sibling(
        class_="panel-collapse"
    ) if heading else None
    if panel is None:
        raise HoldsportError("Holdsport RSVP section could not be found")
    participants = []
    for row in panel.select(".participant_row"):
        row_id = str(row.get("id", ""))
        match = re.fullmatch(r"user_(\d+)", row_id)
        name_element = row.select_one(".participant_name")
        name = _clean(
            row.get("data-name")
            or (name_element.get_text(" ", strip=True) if name_element else "")
        )
        team_role = str(row.get("data-team_role", ""))
        if not match or not name or not re.fullmatch(r"[12]_\d+", team_role):
            raise HoldsportError("Holdsport returned a malformed RSVP participant")
        participants.append(
            HoldsportParticipantData(
                holdsport_user_id=match.group(1),
                name=name,
                is_coach=team_role.startswith("1_"),
            )
        )
    return HoldsportActivityDetails(
        activity_type=activity_type,
        start_time=time(int(time_match.group(1)), int(time_match.group(2))),
        participants=participants,
    )


def parse_no_rsvp_participants(html):
    return parse_activity_details(html).participants


class HoldsportClient:
    def __init__(
        self,
        username,
        password,
        *,
        team_id=None,
        base_url="https://www.holdsport.dk",
        timeout=20,
        time_zone="Europe/Copenhagen",
        session=None,
    ):
        self.username = username
        self.password = password
        self.team_id = str(team_id or "").strip() or None
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.time_zone = time_zone
        self.session = session or requests.Session()
        self.session.headers.update(
            {
                "Accept": "text/html,application/xhtml+xml",
                "User-Agent": "OEB-Holdsport-Integration/1.0",
            }
        )
        self._authenticated = False

    def _get(self, path, **kwargs):
        response = self.session.get(urljoin(f"{self.base_url}/", path.lstrip("/")), timeout=self.timeout, **kwargs)
        response.raise_for_status()
        return response

    def login(self):
        if self._authenticated:
            return
        if not self.username or not self.password:
            raise HoldsportError("Holdsport credentials are not configured")
        login_page = self._get("/")
        soup = BeautifulSoup(login_page.text, "html.parser")
        token = soup.select_one('form[action="/sessions"] input[name="_csrf_token"]')
        if token is None:
            raise HoldsportError("Holdsport login form could not be found")
        response = self.session.post(
            urljoin(f"{self.base_url}/", "sessions"),
            data={
                "_csrf_token": token.get("value", ""),
                "session[username]": self.username,
                "session[password]": self.password,
                "session[remember_me]": "1",
            },
            headers={"Accept": "text/html,application/xhtml+xml"},
            timeout=self.timeout,
        )
        response.raise_for_status()
        authenticated_page = BeautifulSoup(response.text, "html.parser")
        if authenticated_page.select_one('form[action="/sessions"]'):
            raise HoldsportError("Holdsport rejected the configured username or password")
        if not authenticated_page.body or "layout_application" not in (authenticated_page.body.get("class") or []):
            raise HoldsportError("Holdsport login could not be verified")
        if not self.team_id:
            raise HoldsportError("HOLDSPORT_TEAM_ID is required")
        team_link = authenticated_page.select_one(
            f'a[href="/current_team?current_team_id={self.team_id}"]'
        )
        if team_link is None:
            raise HoldsportError("The configured Holdsport team is not available to this account")
        self._get("/current_team", params={"current_team_id": self.team_id})
        activities_page = BeautifulSoup(self._get("/activities").text, "html.parser")
        active_team = activities_page.select_one(
            f'#team-selector input[value="{self.team_id}"][checked]'
        )
        if active_team is None:
            raise HoldsportError("Holdsport did not switch to the configured team")
        self._authenticated = True

    def list_activities(self, start_date, end_date):
        self.login()
        zone = ZoneInfo(self.time_zone)
        start = datetime.combine(start_date, time.min, tzinfo=zone).isoformat()
        end = datetime.combine(end_date, time.min, tzinfo=zone).isoformat()
        response = self._get(
            "/team/activities.json",
            params={"start": start, "end": end},
            headers={"Accept": "application/json"},
        )
        try:
            payload = response.json()
        except ValueError as exc:
            raise HoldsportError("Holdsport returned an invalid activity list") from exc
        if not isinstance(payload, list):
            raise HoldsportError("Holdsport returned an invalid activity list")
        return parse_activity_feed(payload, self.time_zone)

    def activity_details(self, holdsport_id):
        self.login()
        response = self._get(f"/activities/{holdsport_id}")
        if "text/html" not in response.headers.get("Content-Type", ""):
            raise HoldsportError("Holdsport returned an invalid activity page")
        return parse_activity_details(response.text)

    def no_rsvp_participants(self, holdsport_id):
        return self.activity_details(holdsport_id).participants

from datetime import datetime
import re

import requests
from bs4 import BeautifulSoup


class DBUParseError(ValueError):
    """Raised when DBU returns a page without the expected match data."""


class DBUClient:
    def __init__(self, base_url="https://www.dbu.dk", timeout=20):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "OEB fine box/1.0"})

    def _get_soup(self, url):
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        return BeautifulSoup(response.text, "html.parser")

    def _absolute(self, value):
        if value.startswith("http"):
            return value
        return f"{self.base_url}/{value.lstrip('/')}"

    def normalize_match_id(self, value):
        if not value:
            return None
        match = re.search(r"/kamp/([^/?#]+)", str(value))
        return match.group(1) if match else str(value).strip().strip("/")

    def list_season_match_ids(self, season_url):
        soup = self._get_soup(self._absolute(season_url))
        result = []
        seen = set()

        for link in soup.select('a[href*="/resultater/kamp/"]'):
            match_id = self.normalize_match_id(link.get("href"))
            if match_id and match_id not in seen:
                result.append(match_id)
                seen.add(match_id)

        # Future fixtures use clickable rows instead of anchor tags.
        for row in soup.select('tr[onclick*="/resultater/kamp/"]'):
            match_id = self.normalize_match_id(row.get("onclick"))
            if match_id and match_id not in seen:
                result.append(match_id)
                seen.add(match_id)

        if result:
            return result

        # Keep compatibility with the old schedule parser as DBU has used this
        # table shape for older seasons.
        table = soup.find("div", {"id": "teamMatchProgram"})
        if table:
            for row in table.find_all("tr", {"class": "has-hover"}):
                for cell in row.find_all("td"):
                    candidate = self.normalize_match_id(cell.get_text(" ", strip=True))
                    if candidate and "_" in candidate and candidate not in seen:
                        result.append(candidate)
                        seen.add(candidate)
                        break

        if not result:
            raise DBUParseError("No matches found on the DBU season page")
        return result

    def fetch_match(self, match_id, club_name):
        normalized_id = self.normalize_match_id(match_id)
        if not normalized_id:
            raise DBUParseError("Missing DBU match id")
        soup = self._get_soup(f"{self.base_url}/resultater/kamp/{normalized_id}/kampinfo")

        home_node = soup.find("div", {"class": "sr--match--live-score--result--home"})
        away_node = soup.find("div", {"class": "sr--match--live-score--result--away"})
        if not home_node or not away_node:
            raise DBUParseError("DBU match clubs were not found")
        home_name = home_node.find("div", {"class": "teamname"})
        away_name = away_node.find("div", {"class": "teamname"})
        if not home_name or not away_name:
            raise DBUParseError("DBU match club names were not found")

        home_club = home_name.get_text(" ", strip=True).upper()
        away_club = away_name.get_text(" ", strip=True).upper()
        home_score = self._score(soup, "home")
        away_score = self._score(soup, "away")
        is_home = self._is_home(home_club, away_club, club_name)
        lineup = self._lineup(soup, is_home)

        return {
            "dbu_id": normalized_id,
            "home_club": home_club,
            "away_club": away_club,
            "home_score": home_score,
            "away_score": away_score,
            "match_date": self._match_date(soup),
            "lineup": lineup,
        }

    def _score(self, soup, side):
        score_box = soup.find("div", {"class": "sr-match-score"})
        if not score_box:
            return None
        node = score_box.find("div", {"class": side})
        if not node:
            return None
        value = node.get_text(" ", strip=True)
        return int(value) if value.isdigit() else None

    def _is_home(self, home_club, away_club, club_name):
        normalized_club = (club_name or "").strip().upper()
        if normalized_club and normalized_club in home_club:
            return True
        if normalized_club and normalized_club in away_club:
            return False
        raise DBUParseError("Configured club name was not found in the DBU match")

    def _lineup(self, soup, is_home):
        classes = ["dbu-data-table", "dbu-data-table--no-hover", "dbu-data-table-oddeven"]
        classes.append("home-team" if is_home else "away-team")
        table = soup.find("table", class_=lambda value: value and all(item in value for item in classes))
        if not table:
            return []

        names = [span.get_text(" ", strip=True) for span in table.select("span")]
        names = [name for name in names if name]
        # The first span is the club label in the current DBU markup.
        return names[1:] if len(names) > 1 else []

    def _match_date(self, soup):
        candidates = []
        for selector in [".date-time", "time", ".date", ".match-date", ".sr--match--date"]:
            candidates.extend(node.get("datetime") or node.get_text(" ", strip=True) for node in soup.select(selector))
        for value in candidates:
            parsed = self._parse_date(value)
            if parsed:
                return parsed
        return None

    @staticmethod
    def _parse_date(value):
        if not value:
            return None
        text = str(value).strip()
        match = re.search(r"(\d{2})-(\d{2})-(\d{4})(?:.*?(\d{2}):(\d{2}))?", text)
        if match:
            day, month, year, hour, minute = match.groups()
            return datetime(int(year), int(month), int(day), int(hour or 0), int(minute or 0))
        for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%d.%m.%Y %H:%M", "%d.%m.%Y"):
            try:
                return datetime.strptime(text[:19], fmt)
            except ValueError:
                continue
        return None

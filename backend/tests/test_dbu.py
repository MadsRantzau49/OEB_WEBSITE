from bs4 import BeautifulSoup

from backend.dbu import DBUClient


def test_future_fixture_rows_are_discovered_without_links(monkeypatch):
    html = """
    <table><tbody>
      <tr class="has-hover" onclick="MatchProgramMatchClick('/resultater/kamp/355726_502082/kampinfo')">
        <td>355726</td>
      </tr>
      <tr class="has-hover" onclick="MatchProgramMatchClick('/resultater/kamp/355729_502082/kampinfo')">
        <td>355729</td>
      </tr>
    </tbody></table>
    """
    client = DBUClient()
    monkeypatch.setattr(client, "_get_soup", lambda _url: BeautifulSoup(html, "html.parser"))

    assert client.list_season_match_ids("https://www.dbu.dk/future") == ["355726_502082", "355729_502082"]


def test_future_match_has_date_and_clubs_without_score_or_lineup(monkeypatch):
    html = """
    <div class="date-time"><div class="date">fre. 07-08-2026</div><div class="time">Kl. 19:00</div></div>
    <div class="sr--match--live-score--result--home"><div class="teamname">Øster Sundby B32 (1)</div></div>
    <div class="sr--match--live-score--result--away"><div class="teamname">Aalborg Freja</div></div>
    """
    client = DBUClient()
    monkeypatch.setattr(client, "_get_soup", lambda _url: BeautifulSoup(html, "html.parser"))

    match = client.fetch_match("355726_502082", "Øster Sundby")

    assert match["match_date"].isoformat() == "2026-08-07T19:00:00"
    assert match["home_score"] is None
    assert match["away_score"] is None
    assert match["lineup"] == []

from io import BytesIO

from openpyxl import Workbook

from backend.app import create_app
from backend.db import get_db
from backend.services import deduplicate_mobilepay_transactions, find_lineup_player, sync_squad
from backend.models import FineCharge, FineRule, Match, MatchParticipant, MobilePayTransaction, Player, Squad


def make_app(tmp_path):
    class TestConfig:
        SECRET_KEY = "test-secret"
        DATABASE_URL = f"sqlite:///{tmp_path / 'test.db'}"
        CORS_ORIGIN = "http://localhost:5173"
        MAX_CONTENT_LENGTH = 10 * 1024 * 1024
        SESSION_COOKIE_SECURE = False
        SESSION_COOKIE_HTTPONLY = True
        SESSION_COOKIE_SAMESITE = "Lax"
        AUTO_CREATE_SCHEMA = True

    return create_app(TestConfig)


def setup_payload():
    return {
        "clubName": "ØB Klubben",
        "squadName": "Serie 1",
        "dbuClubName": "Øster Sundby Boldklub",
        "dbuSeasonUrl": "https://www.dbu.dk/resultater/hold/4964_485586/kampprogram",
        "seasonName": "2026",
        "seasonStart": "2026-01-01",
        "username": "owner",
        "password": "secret123",
    }


def csrf(response):
    return response.get_json()["csrfToken"]


def test_auth_fines_and_public_dashboard(tmp_path):
    app = make_app(tmp_path)
    owner = app.test_client()
    assert owner.get("/api/v1/setup/status").get_json()["needsSetup"] is True
    setup = owner.post("/api/v1/setup", json=setup_payload())
    assert setup.status_code == 201
    token = csrf(setup)
    squad_id = setup.get_json()["squad"]["id"]

    player_one = owner.post(
        f"/api/v1/squads/{squad_id}/players",
        json={"dbuName": "Player One", "mobilePayName": "Player One"},
        headers={"X-CSRF-Token": token},
    )
    player_two = owner.post(
        f"/api/v1/squads/{squad_id}/players",
        json={"dbuName": "Player Two", "mobilePayName": "Player Two"},
        headers={"X-CSRF-Token": token},
    )
    assert player_one.status_code == 201
    assert player_two.status_code == 201
    first_id = player_one.get_json()["player"]["id"]
    second_id = player_two.get_json()["player"]["id"]

    rule = owner.post(
        f"/api/v1/squads/{squad_id}/fine-rules",
        json={"name": "Manglende sko", "description": "Husk udstyret", "amount": 50},
        headers={"X-CSRF-Token": token},
    )
    assert rule.status_code == 201
    rule_id = rule.get_json()["rule"]["id"]

    member = app.test_client()
    registration = member.post(
        "/api/v1/auth/register",
        json={"username": "player", "password": "player123", "playerId": first_id},
    )
    assert registration.status_code == 201
    member_token = csrf(member.get("/api/v1/auth/me"))
    request_response = member.post(
        f"/api/v1/squads/{squad_id}/fine-requests",
        json={"ruleId": str(rule_id), "playerIds": [second_id]},
        headers={"X-CSRF-Token": member_token},
    )
    assert request_response.status_code == 201
    request_id = request_response.get_json()["request"]["id"]

    approved = owner.post(
        f"/api/v1/squads/{squad_id}/fine-requests/{request_id}/approve",
        json={},
        headers={"X-CSRF-Token": token},
    )
    assert approved.status_code == 200
    assert approved.get_json()["request"]["status"] == "approved"

    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Date", "Name", "Type", "Number", "Message", "Amount", "Currency", "Transaction type"])
    sheet.append(["05/06/2026 20:21", "Player One", "Shop", "17018", "", 50, "DKK", "Pay in"])
    sheet.append(["05/06/2026 20:21", "Club shop", "Shop", "17018", "", -250, "DKK", "Pay out"])
    file_data = BytesIO()
    workbook.save(file_data)
    imported = owner.post(
        f"/api/v1/squads/{squad_id}/mobilepay-imports",
        data={"file": (BytesIO(file_data.getvalue()), "mobilepay.xlsx")},
        content_type="multipart/form-data",
        headers={"X-CSRF-Token": token},
    )
    assert imported.status_code == 201
    assert imported.get_json()["report"]["created"] == 2

    public = app.test_client().get("/api/v1/public/squads/serie-1/dashboard")
    assert public.status_code == 200
    payload = public.get_json()
    assert payload["players"][0]["totalPaid"] == 50
    assert payload["players"][1]["totalFines"] == 50
    assert payload["expenses"][0]["amount"] == -250
    assert payload["balanceSummary"]["boxBalance"] == -200
    assert payload["balanceSummary"]["ifEveryonePays"] == -150

    transactions = owner.get(f"/api/v1/squads/{squad_id}/transactions").get_json()["transactions"]
    expense = next(item for item in transactions if item["transactionType"] == "pay_out")
    assert expense["amount"] == -250
    removed = owner.delete(
        f"/api/v1/squads/{squad_id}/transactions/{expense['id']}",
        headers={"X-CSRF-Token": token},
    )
    assert removed.status_code == 200
    after_removal = app.test_client().get("/api/v1/public/squads/serie-1/dashboard").get_json()
    assert after_removal["expenses"] == []
    assert after_removal["balanceSummary"]["boxBalance"] == 50

    saved_dates = owner.patch(
        f"/api/v1/squads/{squad_id}/seasons/{payload['season']['id']}",
        json={"startDate": "2025-12-01", "endDate": "2026-12-31"},
        headers={"X-CSRF-Token": token},
    )
    assert saved_dates.status_code == 200
    assert saved_dates.get_json()["season"]["startDate"] == "2025-12-01"
    in_period = owner.get(
        f"/api/v1/squads/{squad_id}/transactions?seasonId={payload['season']['id']}"
    ).get_json()["transactions"]
    assert len(in_period) == 1
    owner.patch(
        f"/api/v1/squads/{squad_id}/seasons/{payload['season']['id']}",
        json={"startDate": "2026-06-06", "endDate": "2026-12-31"},
        headers={"X-CSRF-Token": token},
    )
    outside_period = owner.get(
        f"/api/v1/squads/{squad_id}/transactions?seasonId={payload['season']['id']}"
    ).get_json()["transactions"]
    assert outside_period == []
    outside_dashboard = app.test_client().get("/api/v1/public/squads/serie-1/dashboard").get_json()
    assert outside_dashboard["expenses"] == []
    assert outside_dashboard["balanceSummary"]["boxBalance"] == 0


def test_guest_cannot_mutate(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    response = client.post("/api/v1/setup", json=setup_payload())
    squad_id = response.get_json()["squad"]["id"]
    guest = app.test_client()
    denied = guest.post(f"/api/v1/squads/{squad_id}/charges", json={"playerIds": [1], "title": "Nope", "amount": 1})
    assert denied.status_code == 403


def test_owner_can_add_a_second_squad(tmp_path):
    app = make_app(tmp_path)
    client = app.test_client()
    setup = client.post("/api/v1/setup", json=setup_payload())
    response = client.post(
        "/api/v1/squads",
        json={"name": "Serie 2", "dbuClubName": "Øster Sundby", "dbuSeasonUrl": ""},
        headers={"X-CSRF-Token": csrf(setup)},
    )
    assert response.status_code == 201
    assert response.get_json()["squad"]["name"] == "Serie 2"
    assert len(client.get("/api/v1/public/squads").get_json()["squads"]) == 2


def test_empty_case_insensitive_password_and_username(tmp_path):
    app = make_app(tmp_path)
    owner = app.test_client()
    setup = owner.post("/api/v1/setup", json=setup_payload())
    assert setup.status_code == 201
    member = app.test_client()
    registered = member.post(
        "/api/v1/auth/register",
        json={"username": "SimpleUser", "password": ""},
    )
    assert registered.status_code == 201
    member.post("/api/v1/auth/logout")
    logged_in = member.post(
        "/api/v1/auth/login",
        json={"username": "SIMPLEUSER", "password": ""},
    )
    assert logged_in.status_code == 200
    second = app.test_client()
    assert second.post(
        "/api/v1/auth/register",
        json={"username": "MixedPassword", "password": "MiXeD"},
    ).status_code == 201
    assert second.post(
        "/api/v1/auth/login",
        json={"username": "mixedpassword", "password": "mixed"},
    ).status_code == 200


def test_payment_settings_and_multiple_dbu_sources(tmp_path):
    app = make_app(tmp_path)
    owner = app.test_client()
    setup = owner.post("/api/v1/setup", json=setup_payload())
    token = csrf(setup)
    squad = setup.get_json()["squad"]
    season_id = squad["currentSeason"]["id"]
    payment = owner.put(
        f"/api/v1/squads/{squad['id']}/payment-settings",
        json={
            "boxNumber": "1783qn",
            "paymentUrl": "https://qr.mobilepay.dk/box/3f19c727-6610-4b18-900a-79e619db34fe/pay-in",
        },
        headers={"X-CSRF-Token": token},
    )
    assert payment.status_code == 200
    source = owner.post(
        f"/api/v1/squads/{squad['id']}/seasons/{season_id}/dbu-sources",
        json={"label": "Andet seniorhold", "url": "https://www.dbu.dk/resultater/hold/9999_999999/kampprogram"},
        headers={"X-CSRF-Token": token},
    )
    assert source.status_code == 201
    dashboard = owner.get(f"/api/v1/squads/{squad['id']}/dashboard").get_json()
    assert dashboard["payment"]["boxNumber"] == "1783QN"
    assert len(dashboard["dbuSources"]) == 2


def test_mobilepay_rows_can_be_rematched_without_reupload(tmp_path):
    app = make_app(tmp_path)
    owner = app.test_client()
    setup = owner.post("/api/v1/setup", json=setup_payload())
    token = csrf(setup)
    squad = setup.get_json()["squad"]

    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Date", "Name", "Type", "Number", "Message", "Amount", "Currency", "Transaction type"])
    sheet.append(["05/05/2026 20:21", "Late MobilePay Name", "Transfer", "123", "", 75, "DKK", "Pay in"])
    file_data = BytesIO()
    workbook.save(file_data)
    imported = owner.post(
        f"/api/v1/squads/{squad['id']}/mobilepay-imports",
        data={"file": (BytesIO(file_data.getvalue()), "late-player.xlsx")},
        content_type="multipart/form-data",
        headers={"X-CSRF-Token": token},
    )
    assert imported.status_code == 201
    assert imported.get_json()["report"]["unmatched"] == 1

    player = owner.post(
        f"/api/v1/squads/{squad['id']}/players",
        json={"dbuName": "Short DBU Name", "mobilePayName": "Late MobilePay Name"},
        headers={"X-CSRF-Token": token},
    ).get_json()["player"]
    rematched = owner.post(
        f"/api/v1/squads/{squad['id']}/transactions/rematch",
        json={},
        headers={"X-CSRF-Token": token},
    )
    assert rematched.status_code == 200
    assert rematched.get_json()["report"] == {"checked": 1, "matched": 1, "ambiguous": 0, "unmatched": 0}
    transactions = owner.get(
        f"/api/v1/squads/{squad['id']}/transactions?seasonId={squad['currentSeason']['id']}"
    ).get_json()["transactions"]
    assert transactions[0]["allocatedPlayerId"] == player["id"]
    second = owner.post(
        f"/api/v1/squads/{squad['id']}/transactions/rematch",
        json={},
        headers={"X-CSRF-Token": token},
    )
    assert second.get_json()["report"]["checked"] == 0


def test_mobilepay_numeric_identifiers_do_not_create_duplicates(tmp_path):
    app = make_app(tmp_path)
    owner = app.test_client()
    setup = owner.post("/api/v1/setup", json=setup_payload())
    token = csrf(setup)
    squad = setup.get_json()["squad"]

    def workbook_with_number(number):
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(["Date", "Name", "Type", "Number", "Message", "Amount", "Currency", "Transaction type"])
        sheet.append(["05/05/2026 20:21", "Same Payment", "Transfer", number, "", 75, "DKK", "Pay in"])
        file_data = BytesIO()
        workbook.save(file_data)
        return file_data.getvalue()

    first = owner.post(
        f"/api/v1/squads/{squad['id']}/mobilepay-imports",
        data={"file": (BytesIO(workbook_with_number("4512345678.0")), "first.xlsx")},
        content_type="multipart/form-data",
        headers={"X-CSRF-Token": token},
    )
    second = owner.post(
        f"/api/v1/squads/{squad['id']}/mobilepay-imports",
        data={"file": (BytesIO(workbook_with_number("4512345678")), "second.xlsx")},
        content_type="multipart/form-data",
        headers={"X-CSRF-Token": token},
    )
    assert first.get_json()["report"]["created"] == 1
    assert second.get_json()["report"]["created"] == 0
    assert second.get_json()["report"]["skipped"] == 1

    with app.app_context():
        database_session = get_db()
        original = database_session.query(MobilePayTransaction).one()
        database_session.add(
            MobilePayTransaction(
                squad_id=original.squad_id,
                import_id=original.import_id,
                fingerprint="f" * 64,
                transaction_date=original.transaction_date,
                name=original.name,
                transaction_type_name=original.transaction_type_name,
                number="4512345678.0",
                message=original.message,
                amount_cents=original.amount_cents,
                currency=original.currency,
                transaction_type=original.transaction_type,
                allocation_status=original.allocation_status,
            )
        )
        database_session.commit()
        assert deduplicate_mobilepay_transactions(database_session) == 1
        database_session.commit()
        remaining = database_session.query(MobilePayTransaction).one()
        assert remaining.number == "4512345678"


def test_approver_fine_is_applied_immediately(tmp_path):
    app = make_app(tmp_path)
    owner = app.test_client()
    setup = owner.post("/api/v1/setup", json=setup_payload())
    token = csrf(setup)
    squad_id = setup.get_json()["squad"]["id"]
    player = owner.post(
        f"/api/v1/squads/{squad_id}/players",
        json={"dbuName": "Instant Player"},
        headers={"X-CSRF-Token": token},
    ).get_json()["player"]
    rule = owner.post(
        f"/api/v1/squads/{squad_id}/fine-rules",
        json={"name": "Sko", "amount": 25},
        headers={"X-CSRF-Token": token},
    ).get_json()["rule"]
    response = owner.post(
        f"/api/v1/squads/{squad_id}/fine-requests",
        json={"ruleId": str(rule["id"]), "playerIds": [player["id"]]},
        headers={"X-CSRF-Token": token},
    )
    assert response.status_code == 201
    assert response.get_json()["request"]["status"] == "approved"
    custom = owner.post(
        f"/api/v1/squads/{squad_id}/fine-requests",
        json={"title": "Anden bøde", "description": "Frit skrevet", "amount": 17, "playerIds": [player["id"]]},
        headers={"X-CSRF-Token": token},
    )
    assert custom.status_code == 201
    assert custom.get_json()["request"]["status"] == "approved"
    dashboard = owner.get(f"/api/v1/squads/{squad_id}/dashboard").get_json()
    assert dashboard["players"][0]["totalFines"] == 42


def test_dbu_lineup_matches_an_existing_abbreviated_name():
    player = Player(dbu_name="Mads Rantzau", mobilepay_name="Mads Rantzau")

    assert find_lineup_player([player], "Mads Rantzau Nielsen") is player


def test_dbu_sync_creates_idempotent_match_charges(tmp_path, monkeypatch):
    app = make_app(tmp_path)
    owner = app.test_client()
    setup = owner.post("/api/v1/setup", json={**setup_payload(), "dbuClubName": "Club"})
    token = csrf(setup)
    squad_id = setup.get_json()["squad"]["id"]
    player_ids = []
    for name in ("P1", "P2"):
        response = owner.post(
            f"/api/v1/squads/{squad_id}/players",
            json={"dbuName": name},
            headers={"X-CSRF-Token": token},
        )
        assert response.status_code == 201
        player_ids.append(response.get_json()["player"]["id"])
    for rule_type, amount in (("WIN_FINE", 20), ("SCORED_GOAL", 5), ("CONCEDED_GOAL", 2)):
        response = owner.post(
            f"/api/v1/squads/{squad_id}/fine-rules",
            json={"name": rule_type, "type": rule_type, "amount": amount},
            headers={"X-CSRF-Token": token},
        )
        assert response.status_code == 201

    class FakeDBUClient:
        def __init__(self, **_kwargs):
            pass

        def list_season_match_ids(self, _season_url):
            return ["match-1"]

        def fetch_match(self, _match_id, _club_name):
            from datetime import datetime

            return {
                "dbu_id": "match-1",
                "home_club": "Club",
                "away_club": "Visitors",
                "home_score": 2,
                "away_score": 1,
                "match_date": datetime(2026, 6, 5, 20, 21),
                "lineup": ["P1", "P2", "P3 Auto"],
            }

    monkeypatch.setattr("backend.services.DBUClient", FakeDBUClient)
    with app.app_context():
        database_session = get_db()
        squad = database_session.get(Squad, squad_id)
        first_report = sync_squad(database_session, squad)
        database_session.commit()
        rules = database_session.query(FineRule).count()
        match_id = database_session.query(Match.id).scalar()
        player_count = database_session.query(Player).count()
        unmatched = database_session.query(MatchParticipant).filter(MatchParticipant.status == "unmatched").one()
    assert first_report["createdMatches"] == 1
    assert sum(item["chargesCreated"] for season in first_report["seasons"] for item in season["matches"]) == 0
    assert player_count == 2
    assert unmatched.source_name == "P3 Auto"
    assert rules == 3

    created_player = owner.post(
        f"/api/v1/squads/{squad_id}/players",
        json={"dbuName": "P3 Auto"},
        headers={"X-CSRF-Token": token},
    )
    assert created_player.status_code == 201
    with app.app_context():
        database_session = get_db()
        assert database_session.query(FineCharge).filter(FineCharge.match_id == match_id).count() == 3
        squad = database_session.get(Squad, squad_id)
        second_report = sync_squad(database_session, squad)
        database_session.commit()
    assert sum(item["chargesCreated"] for season in second_report["seasons"] for item in season["matches"]) == 0

    corrected = owner.put(
        f"/api/v1/squads/{squad_id}/matches/{match_id}/lineup",
        json={"playerIds": [player_ids[0]]},
        headers={"X-CSRF-Token": token},
    )
    assert corrected.status_code == 200
    washer = owner.put(
        f"/api/v1/squads/{squad_id}/matches/{match_id}/washer",
        json={"playerId": player_ids[1]},
        headers={"X-CSRF-Token": token},
    )
    assert washer.status_code == 200
    with app.app_context():
        database_session = get_db()
        assert database_session.query(FineCharge).filter(FineCharge.match_id == match_id).count() == 1
    dashboard = owner.get(f"/api/v1/squads/{squad_id}/dashboard").get_json()
    assert dashboard["matches"][0]["lineupLocked"] is True
    assert dashboard["matches"][0]["participants"][0]["playerName"] == "P1"
    assert dashboard["matches"][0]["washerName"] == "P2"


def test_manual_match_and_player_deletion_rules(tmp_path):
    app = make_app(tmp_path)
    owner = app.test_client()
    setup = owner.post("/api/v1/setup", json=setup_payload())
    token = csrf(setup)
    squad_id = setup.get_json()["squad"]["id"]
    player = owner.post(
        f"/api/v1/squads/{squad_id}/players",
        json={"dbuName": "Friendly Player"},
        headers={"X-CSRF-Token": token},
    ).get_json()["player"]
    disposable = owner.post(
        f"/api/v1/squads/{squad_id}/players",
        json={"dbuName": "Delete Me"},
        headers={"X-CSRF-Token": token},
    ).get_json()["player"]
    assert owner.delete(
        f"/api/v1/squads/{squad_id}/players/{disposable['id']}",
        headers={"X-CSRF-Token": token},
    ).status_code == 200

    owner.post(
        f"/api/v1/squads/{squad_id}/fine-rules",
        json={"name": "Sejr", "type": "WIN_FINE", "amount": 10},
        headers={"X-CSRF-Token": token},
    )
    manual = owner.post(
        f"/api/v1/squads/{squad_id}/matches",
        json={
            "seasonId": setup.get_json()["squad"]["currentSeason"]["id"],
            "date": "2026-07-12T14:00",
            "homeClub": "Øster Sundby Boldklub",
            "awayClub": "Friends FC",
            "homeScore": 2,
            "awayScore": 1,
        },
        headers={"X-CSRF-Token": token},
    )
    assert manual.status_code == 201
    match_id = manual.get_json()["match"]["id"]
    assert manual.get_json()["match"]["dbuId"] is None
    assert owner.put(
        f"/api/v1/squads/{squad_id}/matches/{match_id}/lineup",
        json={"playerIds": [player["id"]]},
        headers={"X-CSRF-Token": token},
    ).status_code == 200
    with app.app_context():
        assert get_db().query(FineCharge).filter(FineCharge.match_id == match_id).count() == 1
    removed_match_player = owner.delete(
        f"/api/v1/squads/{squad_id}/players/{player['id']}",
        headers={"X-CSRF-Token": token},
    )
    assert removed_match_player.status_code == 200
    assert removed_match_player.get_json()["removedMatchFines"] == 1
    assert owner.delete(
        f"/api/v1/squads/{squad_id}/matches/{match_id}",
        headers={"X-CSRF-Token": token},
    ).status_code == 200
    with app.app_context():
        assert get_db().query(FineCharge).filter(FineCharge.match_id == match_id).count() == 0

    protected = owner.post(
        f"/api/v1/squads/{squad_id}/players",
        json={"dbuName": "Protected Player"},
        headers={"X-CSRF-Token": token},
    ).get_json()["player"]
    custom = owner.post(
        f"/api/v1/squads/{squad_id}/fine-requests",
        json={"title": "Bevar historik", "amount": 5, "playerIds": [protected["id"]]},
        headers={"X-CSRF-Token": token},
    )
    assert custom.status_code == 201
    blocked = owner.delete(
        f"/api/v1/squads/{squad_id}/players/{protected['id']}",
        headers={"X-CSRF-Token": token},
    )
    assert blocked.status_code == 409
    assert blocked.get_json()["error"] == "player_has_financial_history"

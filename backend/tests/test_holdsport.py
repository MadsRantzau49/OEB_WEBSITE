from datetime import date, datetime, time, timezone

from sqlalchemy import select

from backend.db import get_db
from backend.holdsport import (
    HoldsportActivityData,
    HoldsportActivityDetails,
    HoldsportParticipantData,
    parse_activity_feed,
    parse_no_rsvp_participants,
)
from backend.models import (
    FineCharge,
    FineRule,
    HoldsportActivity,
    HoldsportParticipant,
    HoldsportPlayerMapping,
    Player,
    Season,
    Squad,
)
from backend.services import (
    _holdsport_horizon_days,
    _holdsport_is_due,
    _find_holdsport_player,
    fine_holdsport_activity_now,
    reconcile_holdsport_deadline_charges,
    remove_holdsport_activity_fines,
    sync_holdsport,
)
from backend.tests.test_api import csrf, make_app, setup_payload


def test_holdsport_parsers_extract_supported_events_and_no_rsvp_players():
    activities = parse_activity_feed(
        [
            {
                "id": 10,
                "title": " Træning  ",
                "start": "2026-09-08T18:25:00+02:00",
                "className": " traening activity ",
            },
            {
                "id": 11,
                "title": "Kamp",
                "start": "2026-09-09T18:30:00+02:00",
                "className": " kamp activity ",
            },
            {
                "id": 12,
                "title": "Fest",
                "start": "2026-09-10T18:30:00+02:00",
                "className": " social activity ",
            },
            {
                "id": 13,
                "title": "Aflyst træning",
                "start": "2026-09-10T18:30:00+02:00",
                "className": " traening activity ",
                "cancelled": True,
            },
        ]
    )
    assert [(item.holdsport_id, item.activity_type) for item in activities] == [
        ("10", "Træning"),
        ("11", "Kamp"),
    ]
    assert activities[0].activity_date == date(2026, 9, 8)

    participants = parse_no_rsvp_participants(
        """
        <div class="event_type"><div class="info_row_text">Træning</div></div>
        <div class="info_row">
          <div class="info_row_header">Tidspunkt</div>
          <div class="info_row_text">18:30 - 20:00 tirsdag 8. sep</div>
        </div>
        <div class="toggle_collapse_wrapper">
          <div class="toggle_collapse_title">Ej tilkendegivet (2)</div>
        </div>
        <div class="panel-collapse">
          <div class="users_with_no_rsvp">
            <div class="participant_row" id="user_101" data-name="  Mads&nbsp; Rantzau " data-team_role="2_0"></div>
            <div class="coach participant_row" id="user_102" data-name="Coach Name" data-team_role="1_0"></div>
          </div>
        </div>
        """
    )
    assert [(item.holdsport_user_id, item.name, item.is_coach) for item in participants] == [
        ("101", "Mads Rantzau", False),
        ("102", "Coach Name", True),
    ]


def test_holdsport_zero_lead_runs_on_first_poll_and_long_leads_extend_horizon():
    activity = HoldsportActivity(
        starts_at=datetime(2026, 9, 8, 12, 0),
        activity_type="Kamp",
    )
    zero_lead = FineRule(lead_days=0, lead_hours=0, lead_minutes=0)
    long_lead = FineRule(lead_days=45, lead_hours=3, lead_minutes=0)

    assert _holdsport_is_due(activity, zero_lead, datetime(2026, 9, 8, 12, 1))
    positive_lead = FineRule(lead_days=1, lead_hours=0, lead_minutes=0)
    assert not _holdsport_is_due(activity, positive_lead, datetime(2026, 9, 8, 12, 1))
    assert _holdsport_horizon_days([long_lead], 30) == 47


def test_explicitly_cleared_holdsport_name_disables_dbu_fallback():
    opted_out = Player(
        id=1,
        dbu_name="Same Name",
        holdsport_name=None,
        holdsport_auto_match=False,
    )
    automatic = Player(
        id=2,
        dbu_name="Other Name",
        holdsport_name=None,
        holdsport_auto_match=True,
    )

    assert _find_holdsport_player([opted_out], "Same Name") is None
    assert _find_holdsport_player([automatic], "Other Name") is automatic
    assert automatic.holdsport_name == "Other Name"


class FakeHoldsportClient:
    def list_activities(self, _start_date, _end_date):
        return [
            HoldsportActivityData(
                holdsport_id="training-1",
                title="Tirsdagstræning",
                activity_type="Træning",
                activity_date=date(2026, 9, 8),
                starts_at=datetime(2026, 9, 8, 16, 30),
                url="/activities/training-1",
            ),
            HoldsportActivityData(
                holdsport_id="match-1",
                title="ØB - Modstander",
                activity_type="Kamp",
                activity_date=date(2026, 9, 12),
                starts_at=datetime(2026, 9, 12, 12, 0),
                url="/activities/match-1",
            ),
            HoldsportActivityData(
                holdsport_id="match-not-due",
                title="Senere kamp",
                activity_type="Kamp",
                activity_date=date(2026, 9, 13),
                starts_at=datetime(2026, 9, 13, 11, 55),
                url="/activities/match-not-due",
            ),
        ]

    def activity_details(self, holdsport_id):
        return HoldsportActivityDetails(
            activity_type="Træning" if holdsport_id == "training-1" else "Kamp",
            start_time=time(18, 30) if holdsport_id == "training-1" else time(14, 0),
            participants=[
                HoldsportParticipantData("101", "Matched Player", False),
                HoldsportParticipantData("102", "Unknown Player", False),
                HoldsportParticipantData("103", "Coach Name", True),
            ],
        )


class ChangedHoldsportClient(FakeHoldsportClient):
    def activity_details(self, _holdsport_id):
        return HoldsportActivityDetails(
            activity_type="Kamp",
            start_time=time(14, 0),
            participants=[HoldsportParticipantData("101", "Matched Player", False)],
        )


def test_holdsport_sync_applies_due_fines_once_and_skips_coaches_and_unmatched(tmp_path):
    app = make_app(tmp_path)
    owner = app.test_client()
    setup = owner.post("/api/v1/setup", json=setup_payload())
    token = csrf(setup)
    squad_id = setup.get_json()["squad"]["id"]
    owner.post(
        f"/api/v1/squads/{squad_id}/players",
        json={"dbuName": "Matched Player"},
        headers={"X-CSRF-Token": token},
    )
    correction_player = owner.post(
        f"/api/v1/squads/{squad_id}/players",
        json={"dbuName": "Corrected Player"},
        headers={"X-CSRF-Token": token},
    ).get_json()["player"]
    config = {
        "HOLDSPORT_TIME_ZONE": "Europe/Copenhagen",
        "HOLDSPORT_OVERVIEW_DAYS": 30,
        "HOLDSPORT_BASE_URL": "https://www.holdsport.dk",
        "HOLDSPORT_TEAM_ID": "242139",
        "HOLDSPORT_REFRESH_SECONDS": 3600,
    }

    with app.app_context():
        database_session = get_db()
        squad = database_session.get(Squad, squad_id)
        database_session.add_all(
            [FineRule(
                squad_id=squad_id,
                name="Holdsport træning Ej tilkendegivet",
                amount_cents=2500,
                rule_type="HOLDSPORT_TRAINING_NO_RSVP",
                lead_days=1,
            ), FineRule(
                squad_id=squad_id,
                name="Holdsport kamp Ej tilkendegivet",
                amount_cents=4000,
                rule_type="HOLDSPORT_MATCH_NO_RSVP",
                lead_days=5,
            )]
        )
        database_session.commit()

        first = sync_holdsport(
            database_session,
            squad,
            config,
            now=datetime(2026, 9, 7, 16, 31, tzinfo=timezone.utc),
            client=FakeHoldsportClient(),
        )
        database_session.commit()
        second = sync_holdsport(
            database_session,
            squad,
            config,
            now=datetime(2026, 9, 7, 16, 31, tzinfo=timezone.utc),
            client=FakeHoldsportClient(),
        )
        database_session.commit()

        charges = list(database_session.scalars(select(FineCharge).where(FineCharge.source == "holdsport")))
        player = database_session.scalar(select(Player).where(Player.dbu_name == "Matched Player"))
        later_match = database_session.scalar(
            select(HoldsportActivity).where(HoldsportActivity.holdsport_id == "match-not-due")
        )

    assert first["chargesCreated"] == 2
    assert second["chargesCreated"] == 0
    assert first["unmatched"] == 3
    assert first["coaches"] == 3
    assert len(charges) == 2
    assert {charge.player_id for charge in charges} == {player.id}
    assert {charge.amount_cents for charge in charges} == {2500, 4000}
    assert {charge.source_key for charge in charges} == {
        "holdsport:training-1:user:101",
        "holdsport:match-1:user:101",
    }
    assert later_match.starts_at == datetime(2026, 9, 13, 12, 0)
    assert later_match.feed_starts_at == datetime(2026, 9, 13, 11, 55)

    cleared_original_name = owner.patch(
        f"/api/v1/squads/{squad_id}/players/{player.id}",
        json={"holdsportName": ""},
        headers={"X-CSRF-Token": token},
    )
    assert cleared_original_name.status_code == 200
    transferred_by_name = owner.patch(
        f"/api/v1/squads/{squad_id}/players/{correction_player['id']}",
        json={"holdsportName": "Matched Player"},
        headers={"X-CSRF-Token": token},
    )
    assert transferred_by_name.status_code == 200
    added_after_capture = owner.post(
        f"/api/v1/squads/{squad_id}/players",
        json={"dbuName": "Unknown Player"},
        headers={"X-CSRF-Token": token},
    )
    assert added_after_capture.status_code == 201
    assert added_after_capture.get_json()["player"]["holdsportName"] == "Unknown Player"

    with app.app_context():
        database_session = get_db()
        corrected_charges = list(
            database_session.scalars(select(FineCharge).where(FineCharge.source == "holdsport"))
        )
        later_match = database_session.scalar(
            select(HoldsportActivity).where(HoldsportActivity.holdsport_id == "match-not-due")
        )
        manual = fine_holdsport_activity_now(
            database_session,
            database_session.get(Squad, squad_id),
            later_match,
            config,
            client=FakeHoldsportClient(),
            now=datetime(2026, 9, 7, 17, 0, tzinfo=timezone.utc),
        )
        database_session.commit()
        all_charges = list(
            database_session.scalars(select(FineCharge).where(FineCharge.source == "holdsport"))
        )
        retriggered = fine_holdsport_activity_now(
            database_session,
            database_session.get(Squad, squad_id),
            later_match,
            config,
            client=ChangedHoldsportClient(),
            now=datetime(2026, 9, 7, 17, 5, tzinfo=timezone.utc),
            replace=True,
        )
        database_session.commit()
        after_retrigger = list(
            database_session.scalars(select(FineCharge).where(FineCharge.source == "holdsport"))
        )
        removed = remove_holdsport_activity_fines(
            database_session,
            database_session.get(Squad, squad_id),
            later_match,
        )
        after_remove_reconcile = reconcile_holdsport_deadline_charges(
            database_session,
            database_session.get(Squad, squad_id),
            [later_match.id],
        )
        database_session.commit()
        after_remove = list(
            database_session.scalars(select(FineCharge).where(FineCharge.source == "holdsport"))
        )
    assert len(corrected_charges) == 4
    assert sum(charge.player_id == correction_player["id"] for charge in corrected_charges) == 2
    assert sum(charge.player_id == added_after_capture.get_json()["player"]["id"] for charge in corrected_charges) == 2
    assert manual["chargesCreated"] == 2
    assert len(all_charges) == 6
    assert retriggered["chargesDeleted"] == 2
    assert retriggered["chargesCreated"] == 1
    assert len(after_retrigger) == 5
    assert removed["chargesDeleted"] == 1
    assert after_remove_reconcile["chargesCreated"] == 0
    assert len(after_remove) == 4


def test_manual_future_event_uses_current_season_when_event_is_outside_dates(tmp_path):
    app = make_app(tmp_path)
    owner = app.test_client()
    setup = owner.post("/api/v1/setup", json=setup_payload())
    squad_id = setup.get_json()["squad"]["id"]

    with app.app_context():
        database_session = get_db()
        squad = database_session.get(Squad, squad_id)
        season = database_session.scalar(select(Season).where(Season.squad_id == squad_id))
        season.end_date = date(2026, 6, 30)
        player = Player(
            squad_id=squad_id,
            dbu_name="Matched Player",
            holdsport_name="Matched Player",
        )
        activity = HoldsportActivity(
            squad_id=squad_id,
            holdsport_id="training-1",
            title="Fremtidig træning",
            activity_type="Træning",
            activity_date=date(2026, 9, 8),
            starts_at=datetime(2026, 9, 8, 16, 30),
            url="https://www.holdsport.dk/activities/training-1",
        )
        database_session.add_all([
            player,
            activity,
            FineRule(
                squad_id=squad_id,
                name="Træning uden svar",
                amount_cents=2500,
                rule_type="HOLDSPORT_TRAINING_NO_RSVP",
            ),
        ])
        database_session.flush()

        report = fine_holdsport_activity_now(
            database_session,
            squad,
            activity,
            {"HOLDSPORT_TIME_ZONE": "Europe/Copenhagen"},
            client=FakeHoldsportClient(),
            now=datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc),
        )
        database_session.commit()

        charge = database_session.scalar(
            select(FineCharge).where(FineCharge.source == "holdsport")
        )
        assert report["chargesCreated"] == 1
        assert activity.season_id == season.id
        assert charge.season_id == season.id


def test_admin_can_map_unmatched_name_and_see_and_remove_its_fine(tmp_path):
    app = make_app(tmp_path)
    owner = app.test_client()
    setup = owner.post("/api/v1/setup", json=setup_payload())
    token = csrf(setup)
    squad_id = setup.get_json()["squad"]["id"]
    player_id = owner.post(
        f"/api/v1/squads/{squad_id}/players",
        json={"dbuName": "Different DBU Name"},
        headers={"X-CSRF-Token": token},
    ).get_json()["player"]["id"]

    with app.app_context():
        database_session = get_db()
        season = database_session.scalar(select(Season).where(Season.squad_id == squad_id))
        activity = HoldsportActivity(
            squad_id=squad_id,
            season_id=season.id,
            holdsport_id="mapping-event",
            title="Træning",
            activity_type="Træning",
            activity_date=date(2026, 9, 8),
            starts_at=datetime(2026, 9, 8, 16, 30),
            url="https://www.holdsport.dk/activities/mapping-event",
            deadline_captured_at=datetime(2026, 9, 7, 16, 30),
        )
        database_session.add_all([
            activity,
            FineRule(
                squad_id=squad_id,
                name="Ikke svaret",
                amount_cents=3000,
                rule_type="HOLDSPORT_TRAINING_NO_RSVP",
            ),
        ])
        database_session.flush()
        database_session.add_all([
            HoldsportPlayerMapping(
                squad_id=squad_id,
                holdsport_user_id="unmatched-1",
                source_name="Holdsport Alias",
            ),
            HoldsportPlayerMapping(
                squad_id=squad_id,
                holdsport_user_id="unmatched-2",
                source_name="Holdsport Alias",
            ),
            HoldsportParticipant(
                activity_id=activity.id,
                holdsport_user_id="unmatched-1",
                source_name="Holdsport Alias",
                is_coach=False,
            ),
            HoldsportParticipant(
                activity_id=activity.id,
                holdsport_user_id="unmatched-2",
                source_name="Holdsport Alias",
                is_coach=False,
            ),
        ])
        database_session.commit()
        activity_id = activity.id

    mapped = owner.put(
        f"/api/v1/squads/{squad_id}/holdsport/activities/{activity_id}/participants/unmatched-1/player",
        json={"playerId": player_id},
        headers={"X-CSRF-Token": token},
    )
    assert mapped.status_code == 200, mapped.get_json()
    mapped_participants = {
        participant["holdsportUserId"]: participant
        for participant in mapped.get_json()["holdsport"]["activities"][0]["participants"]
    }
    mapped_participant = mapped_participants["unmatched-1"]
    assert mapped.get_json()["report"]["chargesCreated"] == 1
    assert mapped_participant["playerName"] == "Different DBU Name"
    assert mapped_participant["fine"]["title"] == "Ikke svaret"
    assert mapped_participant["fine"]["amount"] == 30
    assert mapped_participant["fine"]["playerName"] == "Different DBU Name"
    assert mapped_participants["unmatched-2"]["playerId"] is None
    assert mapped_participants["unmatched-2"]["fine"] is None

    roster_edit = owner.patch(
        f"/api/v1/squads/{squad_id}/players/{player_id}",
        json={"holdsportName": "A different name"},
        headers={"X-CSRF-Token": token},
    )
    assert roster_edit.status_code == 200
    after_roster_edit = owner.get(f"/api/v1/squads/{squad_id}/holdsport").get_json()
    stable_participant = next(
        participant
        for participant in after_roster_edit["activities"][0]["participants"]
        if participant["holdsportUserId"] == "unmatched-1"
    )
    assert stable_participant["playerId"] == player_id
    assert stable_participant["fine"]["playerId"] == player_id

    removed = owner.delete(
        f"/api/v1/squads/{squad_id}/holdsport/activities/{activity_id}/fines",
        headers={"X-CSRF-Token": token},
    )
    assert removed.status_code == 200
    assert removed.get_json()["report"]["chargesDeleted"] == 1
    removed_participant = next(
        participant
        for participant in removed.get_json()["holdsport"]["activities"][0]["participants"]
        if participant["holdsportUserId"] == "unmatched-1"
    )
    assert removed_participant["fine"] is None


def test_holdsport_admin_requires_dedicated_permission(tmp_path):
    app = make_app(tmp_path)
    owner = app.test_client()
    setup = owner.post("/api/v1/setup", json=setup_payload())
    token = csrf(setup)
    squad_id = setup.get_json()["squad"]["id"]
    training_rule = owner.post(
        f"/api/v1/squads/{squad_id}/fine-rules",
        json={
            "name": "Træning uden svar",
            "amount": 20,
            "type": "HOLDSPORT_TRAINING_NO_RSVP",
            "leadDays": 2,
            "leadHours": 3,
            "leadMinutes": 15,
        },
        headers={"X-CSRF-Token": token},
    )
    match_rule = owner.post(
        f"/api/v1/squads/{squad_id}/fine-rules",
        json={
            "name": "Kamp uden svar",
            "amount": 40,
            "type": "HOLDSPORT_MATCH_NO_RSVP",
            "leadDays": 4,
            "leadHours": 0,
            "leadMinutes": 30,
        },
        headers={"X-CSRF-Token": token},
    )
    player = owner.post(
        f"/api/v1/squads/{squad_id}/players",
        json={
            "dbuName": "DBU Player",
            "mobilePayName": "MobilePay Player",
            "holdsportName": "Holdsport Player",
        },
        headers={"X-CSRF-Token": token},
    )
    assert training_rule.status_code == 201
    assert training_rule.get_json()["rule"]["leadHours"] == 3
    assert match_rule.status_code == 201
    assert match_rule.get_json()["rule"]["leadDays"] == 4
    assert player.get_json()["player"]["holdsportName"] == "Holdsport Player"
    response = owner.get(f"/api/v1/squads/{squad_id}/holdsport")
    assert response.status_code == 200
    assert response.get_json()["configured"] is False
    assert response.get_json()["fineRules"]["training"]["leadMinutes"] == 15
    assert response.get_json()["fineRules"]["match"]["leadMinutes"] == 30

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from urllib.parse import urljoin
from zoneinfo import ZoneInfo

from sqlalchemy import and_, delete, func, or_, select, text
from sqlalchemy.exc import IntegrityError

from .dbu import DBUClient, DBUParseError
from .holdsport import HoldsportClient
from .mobilepay import normalize_identifier, normalize_text, parse_mobilepay_file, transaction_fingerprint
from .models import (
    DbuSource,
    FineCharge,
    FineRequest,
    FineRule,
    HiddenMobilePayTransaction,
    HoldsportActivity,
    HoldsportParticipant,
    HoldsportPlayerMapping,
    HoldsportSyncState,
    Match,
    MatchLineupLock,
    MatchLineupPlayer,
    MatchParticipant,
    MobilePayImport,
    MobilePayTransaction,
    Player,
    Season,
    Squad,
    User,
    UserSquadPermission,
    fine_request_recipients,
)
from .serializers import decimal_to_cents


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def latest_season(database_session, squad_id):
    return database_session.scalar(
        select(Season).where(Season.squad_id == squad_id, Season.active.is_(True)).order_by(Season.id.desc())
    )


def season_for_squad(database_session, squad_id, season_id=None):
    if season_id:
        try:
            season_id = int(season_id)
        except (TypeError, ValueError):
            return None
        return database_session.scalar(select(Season).where(Season.id == season_id, Season.squad_id == squad_id))
    return latest_season(database_session, squad_id)


def parse_amount_input(data, required=True, *, amount_key="amount", cents_key="amountCents"):
    if cents_key in data:
        return int(data[cents_key])
    if amount_key not in data and not required:
        return 0
    if amount_key not in data:
        message = "Amount is required" if amount_key == "amount" else f"{amount_key} is required"
        raise ValueError(message)
    return decimal_to_cents(data[amount_key])


def create_fine_charge(
    database_session,
    *,
    squad_id,
    season_id,
    player_id,
    source,
    title,
    description,
    amount_cents,
    source_key=None,
    match_id=None,
    fine_request_id=None,
    charge_date=None,
):
    player = database_session.scalar(select(Player).where(Player.id == player_id, Player.squad_id == squad_id))
    if player is None:
        raise ValueError("Player does not belong to this squad")
    season = database_session.scalar(select(Season).where(Season.id == season_id, Season.squad_id == squad_id))
    if season is None:
        raise ValueError("Season does not belong to this squad")
    if source_key:
        existing = database_session.scalar(select(FineCharge).where(FineCharge.source_key == source_key))
        if existing:
            return existing, False
    charge = FineCharge(
        squad_id=squad_id,
        season_id=season_id,
        player_id=player_id,
        match_id=match_id,
        fine_request_id=fine_request_id,
        source=source,
        source_key=source_key,
        title=title.strip(),
        description=(description or "").strip(),
        amount_cents=max(0, int(amount_cents)),
        charge_date=charge_date or date.today(),
    )
    database_session.add(charge)
    database_session.flush()
    return charge, True


def calculate_match_charge(rules, match, squad):
    if match.home_score is None or match.away_score is None:
        return None
    amounts = {rule.rule_type: rule.amount_cents for rule in rules if rule.active}
    is_home = squad.dbu_club_name.casefold() in (match.home_club or "").casefold()
    if not is_home and squad.dbu_club_name.casefold() not in (match.away_club or "").casefold():
        return None
    own_score = match.home_score if is_home else match.away_score
    opponent_score = match.away_score if is_home else match.home_score
    result_type = "WIN_FINE" if own_score > opponent_score else "DRAW_FINE" if own_score == opponent_score else "LOSE_FINE"
    return (
        own_score * amounts.get("SCORED_GOAL", 0)
        + opponent_score * amounts.get("CONCEDED_GOAL", 0)
        + amounts.get(result_type, 0)
    )


def effective_match_players(database_session, match):
    """Return the corrected lineup when locked, otherwise the mapped DBU lineup."""
    if database_session.get(MatchLineupLock, match.id):
        return list(
            database_session.scalars(
                select(Player)
                .join(MatchLineupPlayer, MatchLineupPlayer.player_id == Player.id)
                .where(MatchLineupPlayer.match_id == match.id)
                .order_by(Player.dbu_name)
            )
        )
    return list(
        database_session.scalars(
            select(Player)
            .join(MatchParticipant, MatchParticipant.player_id == Player.id)
            .where(MatchParticipant.match_id == match.id, MatchParticipant.status == "confirmed")
            .distinct()
            .order_by(Player.dbu_name)
        )
    )


def reconcile_match_charges(database_session, match, squad):
    """Make generated match charges exactly match the effective lineup and score."""
    players = effective_match_players(database_session, match)
    has_unmatched = database_session.get(MatchLineupLock, match.id) is None and database_session.scalar(
        select(MatchParticipant.id).where(
            MatchParticipant.match_id == match.id,
            MatchParticipant.status != "confirmed",
        ).limit(1)
    ) is not None
    existing = list(
        database_session.scalars(
            select(FineCharge).where(FineCharge.match_id == match.id, FineCharge.source == "match")
        )
    )
    if not players:
        for charge in existing:
            database_session.delete(charge)
        match.status = "needs_review"
        database_session.flush()
        return {"created": 0, "updated": 0, "removed": len(existing)}
    if match.home_score is None or match.away_score is None:
        for charge in existing:
            database_session.delete(charge)
        match.status = "needs_review"
        database_session.flush()
        return {"created": 0, "updated": 0, "removed": len(existing)}

    rules = list(database_session.scalars(select(FineRule).where(FineRule.squad_id == squad.id)))
    amount_cents = calculate_match_charge(rules, match, squad)
    if amount_cents is None:
        match.status = "needs_review"
        match.sync_error = "Configured DBU club name does not match either match club"
        return {"created": 0, "updated": 0, "removed": 0}
    if amount_cents <= 0:
        for charge in existing:
            database_session.delete(charge)
        match.status = "needs_review" if has_unmatched else "complete"
        match.sync_error = None
        database_session.flush()
        return {"created": 0, "updated": 0, "removed": len(existing)}

    desired_ids = {player.id for player in players}
    existing_by_player = {charge.player_id: charge for charge in existing}
    removed = 0
    for charge in existing:
        if charge.player_id not in desired_ids:
            database_session.delete(charge)
            removed += 1

    charge_date = match.match_date.date() if match.match_date else date.today()
    title = f"Kamp: {match.home_club or '?'} - {match.away_club or '?'}"
    description = (
        f"Kampbøde for {match.home_club or '?'} {match.home_score}-{match.away_score} "
        f"{match.away_club or '?'}"
    )
    created = updated = 0
    for player in players:
        charge = existing_by_player.get(player.id)
        if charge:
            if (
                charge.title != title
                or charge.description != description
                or charge.amount_cents != amount_cents
                or charge.charge_date != charge_date
            ):
                charge.title = title
                charge.description = description
                charge.amount_cents = amount_cents
                charge.charge_date = charge_date
                updated += 1
        else:
            create_fine_charge(
                database_session,
                squad_id=squad.id,
                season_id=match.season_id,
                player_id=player.id,
                match_id=match.id,
                source="match",
                source_key=f"match:{match.id}:player:{player.id}",
                title=title,
                description=description,
                amount_cents=amount_cents,
                charge_date=charge_date,
            )
            created += 1
    match.status = "needs_review" if has_unmatched else "complete"
    match.sync_error = None
    database_session.flush()
    return {"created": created, "updated": updated, "removed": removed}


def set_match_lineup(database_session, match, squad, player_ids, user_id):
    unique_ids = {int(player_id) for player_id in player_ids}
    players = list(
        database_session.scalars(
            select(Player).where(Player.squad_id == squad.id, Player.id.in_(unique_ids), Player.active.is_(True))
        )
    ) if unique_ids else []
    if len(players) != len(unique_ids):
        raise ValueError("One or more players do not belong to this squad")
    database_session.execute(delete(MatchLineupPlayer).where(MatchLineupPlayer.match_id == match.id))
    database_session.add_all(
        [MatchLineupPlayer(match_id=match.id, player_id=player.id) for player in players]
    )
    lock = database_session.get(MatchLineupLock, match.id)
    if lock is None:
        database_session.add(MatchLineupLock(match_id=match.id, locked_by_user_id=user_id))
    else:
        lock.locked_by_user_id = user_id
        lock.updated_at = utc_now()
    database_session.flush()
    return reconcile_match_charges(database_session, match, squad)


def clear_match_lineup_lock(database_session, match, squad):
    database_session.execute(delete(MatchLineupPlayer).where(MatchLineupPlayer.match_id == match.id))
    database_session.execute(delete(MatchLineupLock).where(MatchLineupLock.match_id == match.id))
    database_session.flush()
    return reconcile_match_charges(database_session, match, squad)


def find_lineup_player(players, source_name):
    source = normalize_text(source_name)
    exact = [
        player for player in players
        if source in {normalize_text(player.dbu_name), normalize_text(player.mobilepay_name)}
    ]
    if len(exact) == 1:
        return exact[0]
    contained = []
    for player in players:
        aliases = [normalize_text(player.dbu_name), normalize_text(player.mobilepay_name)]
        if any(alias and len(alias) >= 5 and (alias in source or source in alias) for alias in aliases):
            contained.append(player)
    return contained[0] if len(contained) == 1 else None


def map_player_to_existing_lineups(database_session, player, squad):
    """Resolve previously scraped DBU names immediately when a player is added."""
    participants = list(
        database_session.scalars(
            select(MatchParticipant)
            .join(Match, Match.id == MatchParticipant.match_id)
            .join(Season, Season.id == Match.season_id)
            .where(Season.squad_id == squad.id, MatchParticipant.player_id.is_(None))
        )
    )
    affected_match_ids = set()
    for participant in participants:
        if find_lineup_player([player], participant.source_name):
            participant.player_id = player.id
            participant.status = "confirmed"
            affected_match_ids.add(participant.match_id)
    database_session.flush()
    for match_id in affected_match_ids:
        match = database_session.get(Match, match_id)
        reconcile_match_charges(database_session, match, squad)
    database_session.flush()
    return len(affected_match_ids)


def _season_on_date(database_session, squad_id, activity_date):
    return database_session.scalar(
        select(Season)
        .where(
            Season.squad_id == squad_id,
            Season.active.is_(True),
            Season.start_date <= activity_date,
            or_(Season.end_date.is_(None), Season.end_date >= activity_date),
        )
        .order_by(Season.start_date.desc())
    )


def _holdsport_rule_type(activity_type):
    return (
        "HOLDSPORT_TRAINING_NO_RSVP"
        if activity_type == "Træning"
        else "HOLDSPORT_MATCH_NO_RSVP"
    )


def _holdsport_due_at(activity, rule):
    if activity.deadline_at is not None:
        return activity.deadline_at
    return activity.starts_at - timedelta(
        days=rule.lead_days,
        hours=rule.lead_hours,
        minutes=rule.lead_minutes,
    )


def _holdsport_is_due(activity, rule, now_utc):
    lead_seconds = (
        rule.lead_days * 86400
        + rule.lead_hours * 3600
        + rule.lead_minutes * 60
    )
    latest = activity.starts_at + timedelta(hours=6) if lead_seconds == 0 else activity.starts_at
    return _holdsport_due_at(activity, rule) <= now_utc < latest


def _holdsport_horizon_days(rules, configured_days):
    longest_lead_seconds = max(
        (
            rule.lead_days * 86400
            + rule.lead_hours * 3600
            + rule.lead_minutes * 60
            for rule in rules
        ),
        default=0,
    )
    return max(5, int(configured_days), longest_lead_seconds // 86400 + 2)


def _find_holdsport_player(players, source_name, mapping=None):
    source = normalize_text(source_name)
    if mapping and mapping.manual:
        return next(
            (player for player in players if player.id == mapping.player_id),
            None,
        )
    if mapping and mapping.player_id:
        mapped_player = next((player for player in players if player.id == mapping.player_id), None)
        if mapped_player:
            return mapped_player
    holdsport_matches = [
        player
        for player in players
        if normalize_text(player.holdsport_name) == source
    ]
    if len(holdsport_matches) == 1:
        return holdsport_matches[0]
    dbu_matches = [
        player
        for player in players
        if player.holdsport_auto_match
        and not player.holdsport_name
        and normalize_text(player.dbu_name) == source
    ]
    if len(dbu_matches) == 1:
        dbu_matches[0].holdsport_name = source_name
        return dbu_matches[0]
    return None


def reconcile_holdsport_deadline_charges(
    database_session, squad, activity_ids=None, rules=None
):
    report = {"chargesCreated": 0, "errors": []}
    if rules is None:
        rules = {
            rule.rule_type: rule
            for rule in database_session.scalars(
                select(FineRule).where(
                    FineRule.squad_id == squad.id,
                    FineRule.rule_type.in_(
                        {"HOLDSPORT_TRAINING_NO_RSVP", "HOLDSPORT_MATCH_NO_RSVP"}
                    ),
                    FineRule.active.is_(True),
                )
            )
        }
    activity_query = select(HoldsportActivity).where(
        HoldsportActivity.squad_id == squad.id,
        HoldsportActivity.deadline_captured_at.is_not(None),
    )
    if activity_ids is not None:
        activity_query = activity_query.where(HoldsportActivity.id.in_(activity_ids))
    activities = list(
        database_session.scalars(activity_query)
    )
    for activity in activities:
        rule_type = _holdsport_rule_type(activity.activity_type)
        rule = rules.get(rule_type)
        if rule is None:
            error_code = (
                "holdsport_training_fine_rule_missing"
                if activity.activity_type == "Træning"
                else "holdsport_match_fine_rule_missing"
            )
            if error_code not in report["errors"]:
                report["errors"].append(error_code)
            continue
        season = (
            database_session.get(Season, activity.season_id)
            if activity.season_id
            else _season_on_date(database_session, squad.id, activity.activity_date)
        )
        if season is None:
            if "holdsport_season_missing" not in report["errors"]:
                report["errors"].append("holdsport_season_missing")
            continue
        activity.season_id = season.id
        participants = database_session.scalars(
            select(HoldsportParticipant).where(
                HoldsportParticipant.activity_id == activity.id,
                HoldsportParticipant.is_coach.is_(False),
                HoldsportParticipant.player_id.is_not(None),
                HoldsportParticipant.fine_processed_at.is_(None),
            )
        )
        for participant in participants:
            _, created = create_fine_charge(
                database_session,
                squad_id=squad.id,
                season_id=season.id,
                player_id=participant.player_id,
                source="holdsport",
                source_key=f"holdsport:{activity.holdsport_id}:user:{participant.holdsport_user_id}",
                title=rule.name,
                description=(
                    f"Manglende svar på Holdsport til {activity.activity_type.lower()} "
                    f"den {activity.activity_date.strftime('%d-%m-%Y')}."
                ),
                amount_cents=rule.amount_cents,
                charge_date=activity.activity_date,
            )
            participant.fine_processed_at = utc_now()
            report["chargesCreated"] += int(created)
    return report


def _replace_holdsport_participants(database_session, activity, fetched_participants, players, squad_id):
    database_session.execute(
        delete(HoldsportParticipant).where(HoldsportParticipant.activity_id == activity.id)
    )
    result = []
    for item_participant in fetched_participants:
        mapping = database_session.scalar(
            select(HoldsportPlayerMapping).where(
                HoldsportPlayerMapping.squad_id == squad_id,
                HoldsportPlayerMapping.holdsport_user_id == item_participant.holdsport_user_id,
            )
        )
        player = _find_holdsport_player(players, item_participant.name, mapping)
        if mapping is None:
            mapping = HoldsportPlayerMapping(
                squad_id=squad_id,
                holdsport_user_id=item_participant.holdsport_user_id,
                source_name=item_participant.name,
            )
            database_session.add(mapping)
        mapping.source_name = item_participant.name
        mapping.player_id = player.id if player else None
        participant = HoldsportParticipant(
            activity_id=activity.id,
            holdsport_user_id=item_participant.holdsport_user_id,
            source_name=item_participant.name,
            player_id=mapping.player_id,
            is_coach=item_participant.is_coach,
        )
        database_session.add(participant)
        result.append(participant)
    return result


def rematch_holdsport_player(database_session, player, squad, allow_dbu_fallback=True):
    """Apply a player's Holdsport name to current and captured RSVP rows."""
    _acquire_holdsport_lock(database_session, squad.id, wait=True)
    mappings = list(
        database_session.scalars(
            select(HoldsportPlayerMapping).where(HoldsportPlayerMapping.squad_id == squad.id)
        )
    )
    use_dbu_fallback = allow_dbu_fallback and player.holdsport_auto_match
    normalized_name = normalize_text(
        player.holdsport_name or (player.dbu_name if use_dbu_fallback else "")
    )
    matched_user_ids = []
    unmatched_user_ids = []
    for mapping in mappings:
        if mapping.manual:
            continue
        if normalized_name and normalize_text(mapping.source_name) == normalized_name:
            if not player.holdsport_name and use_dbu_fallback:
                player.holdsport_name = mapping.source_name
            mapping.player_id = player.id
            matched_user_ids.append(mapping.holdsport_user_id)
        elif mapping.player_id == player.id:
            mapping.player_id = None
            unmatched_user_ids.append(mapping.holdsport_user_id)
    activity_ids = select(HoldsportActivity.id).where(HoldsportActivity.squad_id == squad.id)
    if matched_user_ids:
        database_session.execute(
            HoldsportParticipant.__table__.update()
            .where(HoldsportParticipant.activity_id.in_(activity_ids))
            .where(HoldsportParticipant.holdsport_user_id.in_(matched_user_ids))
            .values(player_id=player.id)
        )
        for holdsport_user_id in matched_user_ids:
            charges = database_session.scalars(
                select(FineCharge).where(
                    FineCharge.squad_id == squad.id,
                    FineCharge.source == "holdsport",
                    FineCharge.source_key.like(
                        f"holdsport:%:user:{holdsport_user_id}"
                    ),
                )
            )
            for charge in charges:
                charge.player_id = player.id
    if unmatched_user_ids:
        database_session.execute(
            HoldsportParticipant.__table__.update()
            .where(HoldsportParticipant.activity_id.in_(activity_ids))
            .where(HoldsportParticipant.holdsport_user_id.in_(unmatched_user_ids))
            .values(player_id=None)
        )
    database_session.flush()
    return reconcile_holdsport_deadline_charges(database_session, squad)


def sync_holdsport(
    database_session,
    squad,
    config,
    *,
    now=None,
    client=None,
    apply_fines=True,
    refresh_all=False,
):
    """Refresh Holdsport data and process activities whose configured lead time is due."""
    zone = ZoneInfo(config.get("HOLDSPORT_TIME_ZONE", "Europe/Copenhagen"))
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now_utc = now.astimezone(timezone.utc).replace(tzinfo=None)
    today = now.astimezone(zone).date()
    state = database_session.get(HoldsportSyncState, squad.id)
    if state is None:
        state = HoldsportSyncState(squad_id=squad.id)
        database_session.add(state)
    state.team_id = str(config.get("HOLDSPORT_TEAM_ID") or "").strip() or None
    state.last_checked_at = utc_now()
    report = {
        "squadId": squad.id,
        "activities": 0,
        "noRsvp": 0,
        "matched": 0,
        "unmatched": 0,
        "coaches": 0,
        "chargesCreated": 0,
        "errors": [],
    }
    if database_session.get_bind().dialect.name == "postgresql":
        acquired = database_session.scalar(
            text("SELECT pg_try_advisory_xact_lock(:lock_id)"),
            {"lock_id": 4_832_011_000 + squad.id},
        )
        if not acquired:
            report["errors"].append("holdsport_sync_in_progress")
            return report
    try:
        client = client or HoldsportClient(
            config.get("HOLDSPORT_USERNAME", ""),
            config.get("HOLDSPORT_PASSWORD", ""),
            team_id=config.get("HOLDSPORT_TEAM_ID"),
            base_url=config.get("HOLDSPORT_BASE_URL", "https://www.holdsport.dk"),
            timeout=config.get("HOLDSPORT_REQUEST_TIMEOUT", 20),
            time_zone=config.get("HOLDSPORT_TIME_ZONE", "Europe/Copenhagen"),
        )
        rules = {
            rule.rule_type: rule
            for rule in database_session.scalars(
                select(FineRule).where(
                    FineRule.squad_id == squad.id,
                    FineRule.rule_type.in_(
                        {"HOLDSPORT_TRAINING_NO_RSVP", "HOLDSPORT_MATCH_NO_RSVP"}
                    ),
                    FineRule.active.is_(True),
                )
            )
        }
        overview_days = _holdsport_horizon_days(
            rules.values(), config.get("HOLDSPORT_OVERVIEW_DAYS", 30)
        )
        end_date = today + timedelta(days=overview_days + 1)
        activity_data = client.list_activities(today, end_date)
        existing_activities = {
            activity.holdsport_id: activity
            for activity in database_session.scalars(
                select(HoldsportActivity).where(HoldsportActivity.squad_id == squad.id)
            )
        }
        refresh_after = now_utc - timedelta(
            seconds=max(60, int(config.get("HOLDSPORT_REFRESH_SECONDS", 3600)))
        )
        detail_ids = set()
        for item in activity_data:
            activity = existing_activities.get(item.holdsport_id)
            if activity is None or refresh_all or activity.details_synced_at is None:
                detail_ids.add(item.holdsport_id)
                continue
            if activity.deadline_captured_at is not None:
                continue
            if activity.feed_starts_at != item.starts_at:
                detail_ids.add(item.holdsport_id)
                continue
            rule = rules.get(_holdsport_rule_type(activity.activity_type))
            is_due = rule is not None and _holdsport_is_due(activity, rule, now_utc)
            if is_due or activity.details_synced_at <= refresh_after:
                detail_ids.add(item.holdsport_id)
        details_by_id = {
            item.holdsport_id: client.activity_details(item.holdsport_id)
            for item in activity_data
            if item.holdsport_id in detail_ids
        }
        players = list(
            database_session.scalars(
                select(Player).where(Player.squad_id == squad.id, Player.active.is_(True))
            )
        )
        for item in activity_data:
            activity = existing_activities.get(item.holdsport_id)
            if activity is None:
                activity = HoldsportActivity(squad_id=squad.id, holdsport_id=item.holdsport_id)
                database_session.add(activity)
                existing_activities[item.holdsport_id] = activity
            preserve_deadline_snapshot = activity.deadline_captured_at is not None
            activity.title = item.title
            if not preserve_deadline_snapshot:
                activity.activity_type = item.activity_type
                activity.activity_date = item.activity_date
                activity.feed_starts_at = item.starts_at
                details = details_by_id.get(item.holdsport_id)
                if details:
                    if details.activity_type != item.activity_type:
                        raise ValueError("Holdsport activity type did not match its calendar entry")
                    local_start = datetime.combine(item.activity_date, details.start_time, tzinfo=zone)
                    activity.starts_at = local_start.astimezone(timezone.utc).replace(tzinfo=None)
                    activity.details_synced_at = now_utc
                elif activity.starts_at is None:
                    activity.starts_at = item.starts_at
            activity.url = urljoin(f"{config.get('HOLDSPORT_BASE_URL', 'https://www.holdsport.dk').rstrip('/')}/", item.url.lstrip("/"))
            activity.last_synced_at = utc_now()
            database_session.flush()

            if preserve_deadline_snapshot:
                stored_participants = list(
                    database_session.scalars(
                        select(HoldsportParticipant).where(HoldsportParticipant.activity_id == activity.id)
                    )
                )
                report["noRsvp"] += len(stored_participants)
                report["coaches"] += sum(participant.is_coach for participant in stored_participants)
                report["matched"] += sum(
                    not participant.is_coach and participant.player_id is not None
                    for participant in stored_participants
                )
                report["unmatched"] += sum(
                    not participant.is_coach and participant.player_id is None
                    for participant in stored_participants
                )
                report["activities"] += 1
                continue

            details = details_by_id.get(item.holdsport_id)
            if details:
                stored_participants = _replace_holdsport_participants(
                    database_session,
                    activity,
                    details.participants,
                    players,
                    squad.id,
                )
            else:
                stored_participants = list(
                    database_session.scalars(
                        select(HoldsportParticipant).where(
                            HoldsportParticipant.activity_id == activity.id
                        )
                    )
                )
            for participant in stored_participants:
                report["noRsvp"] += 1
                if participant.is_coach:
                    report["coaches"] += 1
                elif participant.player_id:
                    report["matched"] += 1
                else:
                    report["unmatched"] += 1

            rule = rules.get(_holdsport_rule_type(activity.activity_type))
            due_at = _holdsport_due_at(activity, rule) if rule else None
            if apply_fines and details and rule and _holdsport_is_due(activity, rule, now_utc):
                season = _season_on_date(database_session, squad.id, activity.activity_date)
                if season is None:
                    if "holdsport_season_missing" not in report["errors"]:
                        report["errors"].append("holdsport_season_missing")
                else:
                    activity.season_id = season.id
                    activity.deadline_captured_at = utc_now()
                    activity.deadline_at = due_at
            report["activities"] += 1

        seen_holdsport_ids = {item.holdsport_id for item in activity_data}
        stale_activities = list(
            database_session.scalars(
                select(HoldsportActivity).where(
                    HoldsportActivity.squad_id == squad.id,
                    or_(
                        HoldsportActivity.activity_date < today - timedelta(days=14),
                        and_(
                            HoldsportActivity.activity_date >= today,
                            HoldsportActivity.activity_date < end_date,
                            HoldsportActivity.deadline_captured_at.is_(None),
                            HoldsportActivity.holdsport_id.not_in(seen_holdsport_ids),
                        ),
                    ),
                )
            )
        )
        for stale_activity in stale_activities:
            has_unprocessed_players = database_session.scalar(
                select(HoldsportParticipant.id).where(
                    HoldsportParticipant.activity_id == stale_activity.id,
                    HoldsportParticipant.is_coach.is_(False),
                    HoldsportParticipant.fine_processed_at.is_(None),
                ).limit(1)
            ) is not None
            if stale_activity.deadline_captured_at is not None and has_unprocessed_players:
                continue
            database_session.delete(stale_activity)

        if apply_fines:
            database_session.flush()
            fine_report = reconcile_holdsport_deadline_charges(database_session, squad)
            report["chargesCreated"] += fine_report["chargesCreated"]
            report["errors"].extend(fine_report["errors"])

        state.last_success_at = utc_now()
        state.last_error = None
        state.activities_count = report["activities"]
        state.no_rsvp_count = report["noRsvp"]
        state.charges_created = report["chargesCreated"]
    except Exception as exc:
        state.last_error = str(exc)[:1000]
        report["errors"].append("holdsport_sync_failed")
        report["message"] = state.last_error
    database_session.flush()
    return report


def _acquire_holdsport_lock(database_session, squad_id, wait=False):
    if database_session.get_bind().dialect.name != "postgresql":
        return
    if wait:
        database_session.execute(
            text("SELECT pg_advisory_xact_lock(:lock_id)"),
            {"lock_id": 4_832_011_000 + squad_id},
        )
        return
    acquired = database_session.scalar(
        text("SELECT pg_try_advisory_xact_lock(:lock_id)"),
        {"lock_id": 4_832_011_000 + squad_id},
    )
    if not acquired:
        raise ValueError("holdsport_sync_in_progress")


def _delete_holdsport_activity_charges(database_session, squad, activity):
    result = database_session.execute(
        delete(FineCharge).where(
            FineCharge.squad_id == squad.id,
            FineCharge.source == "holdsport",
            FineCharge.source_key.startswith(
                f"holdsport:{activity.holdsport_id}:user:",
                autoescape=True,
            ),
        )
    )
    return result.rowcount or 0


def remove_holdsport_activity_fines(database_session, squad, activity):
    _acquire_holdsport_lock(database_session, squad.id)
    charges_deleted = _delete_holdsport_activity_charges(
        database_session, squad, activity
    )
    database_session.execute(
        HoldsportParticipant.__table__.update()
        .where(HoldsportParticipant.activity_id == activity.id)
        .values(fine_processed_at=utc_now())
    )
    database_session.flush()
    return {"chargesDeleted": charges_deleted, "chargesCreated": 0, "errors": []}


def assign_holdsport_participant(database_session, squad, participant, player):
    _acquire_holdsport_lock(database_session, squad.id)
    if participant.is_coach:
        raise ValueError("holdsport_coach_cannot_be_mapped")
    mapping = database_session.scalar(
        select(HoldsportPlayerMapping).where(
            HoldsportPlayerMapping.squad_id == squad.id,
            HoldsportPlayerMapping.holdsport_user_id == participant.holdsport_user_id,
        )
    )
    if mapping is None:
        mapping = HoldsportPlayerMapping(
            squad_id=squad.id,
            holdsport_user_id=participant.holdsport_user_id,
            source_name=participant.source_name,
        )
        database_session.add(mapping)
    mapping.source_name = participant.source_name
    mapping.player_id = player.id
    mapping.manual = True
    participant.player_id = player.id
    activity_ids = select(HoldsportActivity.id).where(HoldsportActivity.squad_id == squad.id)
    database_session.execute(
        HoldsportParticipant.__table__.update()
        .where(HoldsportParticipant.activity_id.in_(activity_ids))
        .where(HoldsportParticipant.holdsport_user_id == participant.holdsport_user_id)
        .values(player_id=player.id)
    )
    for charge in database_session.scalars(
        select(FineCharge).where(
            FineCharge.squad_id == squad.id,
            FineCharge.source == "holdsport",
            FineCharge.source_key.endswith(
                f":user:{participant.holdsport_user_id}", autoescape=True
            ),
        )
    ):
        charge.player_id = player.id
    database_session.flush()
    return reconcile_holdsport_deadline_charges(database_session, squad)


def fine_holdsport_activity_now(
    database_session,
    squad,
    activity,
    config,
    client=None,
    now=None,
    replace=False,
):
    _acquire_holdsport_lock(database_session, squad.id)
    rule = database_session.scalar(
        select(FineRule).where(
            FineRule.squad_id == squad.id,
            FineRule.rule_type == _holdsport_rule_type(activity.activity_type),
            FineRule.active.is_(True),
        )
    )
    if rule is None:
        raise ValueError(
            "holdsport_training_fine_rule_missing"
            if activity.activity_type == "Træning"
            else "holdsport_match_fine_rule_missing"
        )
    season = database_session.get(Season, activity.season_id) if activity.season_id else None
    if season is None:
        season = _season_on_date(database_session, squad.id, activity.activity_date)
    if season is None:
        season = latest_season(database_session, squad.id)
    if season is None:
        raise ValueError("holdsport_season_missing")
    activity.season_id = season.id
    if activity.deadline_captured_at is not None and not replace:
        return reconcile_holdsport_deadline_charges(database_session, squad, [activity.id])
    client = client or HoldsportClient(
        config.get("HOLDSPORT_USERNAME", ""),
        config.get("HOLDSPORT_PASSWORD", ""),
        team_id=config.get("HOLDSPORT_TEAM_ID"),
        base_url=config.get("HOLDSPORT_BASE_URL", "https://www.holdsport.dk"),
        timeout=config.get("HOLDSPORT_REQUEST_TIMEOUT", 20),
        time_zone=config.get("HOLDSPORT_TIME_ZONE", "Europe/Copenhagen"),
    )
    details = client.activity_details(activity.holdsport_id)
    if details.activity_type != activity.activity_type:
        raise ValueError("holdsport_activity_type_changed")
    players = list(
        database_session.scalars(
            select(Player).where(Player.squad_id == squad.id, Player.active.is_(True))
        )
    )
    charges_deleted = (
        _delete_holdsport_activity_charges(database_session, squad, activity)
        if replace
        else 0
    )
    _replace_holdsport_participants(
        database_session, activity, details.participants, players, squad.id
    )
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    now_utc = now.astimezone(timezone.utc).replace(tzinfo=None)
    activity.deadline_captured_at = now_utc
    activity.deadline_at = now_utc
    activity.details_synced_at = now_utc
    database_session.flush()
    report = reconcile_holdsport_deadline_charges(
        database_session,
        squad,
        [activity.id],
        {_holdsport_rule_type(activity.activity_type): rule},
    )
    report["chargesDeleted"] = charges_deleted
    return report


def sync_match(database_session, match, squad, client):
    if not match.dbu_id:
        return {"matchId": match.id, "status": "manual", "chargesCreated": 0}
    try:
        data = client.fetch_match(match.dbu_id, squad.dbu_club_name)
    except (DBUParseError, Exception) as error:
        match.status = "needs_review"
        match.sync_error = str(error)
        match.last_synced_at = utc_now()
        database_session.flush()
        return {"matchId": match.id, "status": "needs_review", "error": str(error), "chargesCreated": 0}

    match.home_club = data["home_club"]
    match.away_club = data["away_club"]
    match.home_score = data["home_score"]
    match.away_score = data["away_score"]
    match.match_date = data["match_date"]
    match.last_synced_at = utc_now()
    match.sync_error = None

    lineup_locked = database_session.get(MatchLineupLock, match.id) is not None
    resolved = []
    if not lineup_locked:
        existing_participants = {
            participant.source_name: participant
            for participant in database_session.scalars(select(MatchParticipant).where(MatchParticipant.match_id == match.id))
        }
        squad_players = list(
            database_session.scalars(select(Player).where(Player.squad_id == squad.id, Player.active.is_(True)))
        )
        for source_name in data["lineup"]:
            player = find_lineup_player(squad_players, source_name)
            participant = existing_participants.get(source_name)
            if participant is None:
                participant = MatchParticipant(match_id=match.id, source_name=source_name)
                database_session.add(participant)
            participant.player_id = player.id if player else None
            participant.status = "confirmed" if player else "unmatched"
            resolved.append(participant)

        # Never erase the last known lineup after a failed or empty scrape.
        if data["lineup"]:
            current_names = set(data["lineup"])
            for participant in existing_participants.values():
                if participant.source_name not in current_names:
                    database_session.delete(participant)

    database_session.flush()

    unresolved = [participant.source_name for participant in resolved if participant.status != "confirmed"]
    lineup_needs_review = not lineup_locked and (not resolved or bool(unresolved))
    has_complete_result = match.home_score is not None and match.away_score is not None
    result = reconcile_match_charges(database_session, match, squad)
    if not has_complete_result or lineup_needs_review:
        match.status = "needs_review"
        database_session.flush()
    report = {
        "matchId": match.id,
        "status": match.status,
        "chargesCreated": result["created"],
        "chargesUpdated": result["updated"],
        "chargesRemoved": result["removed"],
    }
    if not has_complete_result or lineup_needs_review:
        report["unresolved"] = unresolved
    return report


def refresh_match(database_session, match, squad, timeout=20):
    """Force one match to refresh and reconcile its generated fines."""
    if match.dbu_id:
        return sync_match(database_session, match, squad, DBUClient(timeout=timeout))

    result = reconcile_match_charges(database_session, match, squad)
    return {
        "matchId": match.id,
        "status": match.status,
        "chargesCreated": result["created"],
        "chargesUpdated": result["updated"],
        "chargesRemoved": result["removed"],
    }


def sync_squad(database_session, squad, timeout=20, season_id=None, full=False):
    client = DBUClient(timeout=timeout)
    season_query = select(Season).where(Season.squad_id == squad.id, Season.active.is_(True))
    if season_id is not None:
        season_query = season_query.where(Season.id == season_id)
    seasons = list(database_session.scalars(season_query))
    report = {"squadId": squad.id, "seasons": [], "createdMatches": 0, "updatedMatches": 0, "skippedMatches": 0, "errors": []}
    for season in seasons:
        season_report = {"seasonId": season.id, "matches": []}
        sources = list(
            database_session.scalars(
                select(DbuSource).where(DbuSource.season_id == season.id, DbuSource.active.is_(True))
            )
        )
        source_urls = [source.url for source in sources]
        if season.dbu_url and season.dbu_url not in source_urls:
            source_urls.append(season.dbu_url)
        match_ids = []
        for source_url in source_urls:
            try:
                for match_id in client.list_season_match_ids(source_url):
                    if match_id not in match_ids:
                        match_ids.append(match_id)
            except Exception as error:
                message = f"{source_url}: {error}"
                season_report.setdefault("errors", []).append(message)
                report["errors"].append(message)

        for dbu_id in match_ids:
            match = database_session.scalar(
                select(Match).where(Match.season_id == season.id, Match.dbu_id == dbu_id)
            )
            if match is None:
                match = Match(season_id=season.id, dbu_id=dbu_id)
                database_session.add(match)
                database_session.flush()
                report["createdMatches"] += 1
            else:
                should_update = (
                    full
                    or match.status != "complete"
                    or match.last_synced_at is None
                    or match.home_score is None
                    or match.away_score is None
                )
                if not should_update:
                    report["skippedMatches"] += 1
                    continue
                report["updatedMatches"] += 1
            result = sync_match(database_session, match, squad, client)
            season_report["matches"].append(result)
        report["seasons"].append(season_report)
    database_session.flush()
    return report


def reset_dbu_matches(database_session, squad, season_id, timeout=20):
    match_ids = list(
        database_session.scalars(
            select(Match.id).where(Match.season_id == season_id, Match.dbu_id.is_not(None))
        )
    )
    if match_ids:
        database_session.execute(
            delete(FineCharge).where(FineCharge.match_id.in_(match_ids), FineCharge.source == "match")
        )
        database_session.execute(delete(Match).where(Match.id.in_(match_ids)))
        database_session.flush()
    report = sync_squad(database_session, squad, timeout=timeout, season_id=season_id, full=True)
    report["deletedMatches"] = len(match_ids)
    return report


def mobilepay_alias_index(players):
    aliases = defaultdict(set)
    for player in players:
        for alias in (player.mobilepay_name, player.dbu_name):
            normalized = normalize_text(alias)
            if normalized:
                aliases[normalized].add(player)
    return aliases


def mobilepay_candidates(aliases, name, message):
    candidates = set()
    candidates |= aliases.get(normalize_text(name), set())
    candidates |= aliases.get(normalize_text(message), set())
    return candidates


def stored_transaction_fingerprint(transaction):
    return transaction_fingerprint(
        {
            "date": transaction.transaction_date,
            "name": transaction.name,
            "number": transaction.number,
            "message": transaction.message,
            "amount_cents": transaction.amount_cents,
            "currency": transaction.currency,
            "transaction_type": transaction.transaction_type,
        }
    )


def deduplicate_mobilepay_transactions(database_session):
    """Merge legacy duplicates caused by Excel changing numeric IDs to text."""
    transactions = list(database_session.scalars(select(MobilePayTransaction).order_by(MobilePayTransaction.id)))
    groups = defaultdict(list)
    for transaction in transactions:
        groups[(transaction.squad_id, stored_transaction_fingerprint(transaction))].append(transaction)

    removed = 0
    for (_squad_id, fingerprint), duplicates in groups.items():
        if len(duplicates) < 2:
            continue
        keeper = max(duplicates, key=lambda item: (item.allocated_player_id is not None, item.id))
        hidden_rows = [
            hidden
            for item in duplicates
            if (hidden := database_session.get(HiddenMobilePayTransaction, item.id)) is not None
        ]
        keeper_hidden = database_session.get(HiddenMobilePayTransaction, keeper.id)
        if hidden_rows and keeper_hidden is None:
            source = min(hidden_rows, key=lambda item: item.hidden_at)
            database_session.add(
                HiddenMobilePayTransaction(
                    transaction_id=keeper.id,
                    hidden_by_user_id=source.hidden_by_user_id,
                    hidden_at=source.hidden_at,
                )
            )
        for duplicate in duplicates:
            if duplicate.id != keeper.id:
                database_session.delete(duplicate)
                removed += 1
        database_session.flush()
        keeper.number = normalize_identifier(keeper.number)
        keeper.message = normalize_identifier(keeper.message)
        keeper.fingerprint = fingerprint
        database_session.flush()
    return removed


def rematch_mobilepay_transactions(database_session, squad):
    players = list(database_session.scalars(select(Player).where(Player.squad_id == squad.id, Player.active.is_(True))))
    aliases = mobilepay_alias_index(players)
    hidden_ids = select(HiddenMobilePayTransaction.transaction_id)
    transactions = list(
        database_session.scalars(
            select(MobilePayTransaction).where(
                MobilePayTransaction.squad_id == squad.id,
                MobilePayTransaction.transaction_type == "pay_in",
                MobilePayTransaction.allocated_player_id.is_(None),
                MobilePayTransaction.id.not_in(hidden_ids),
            )
        )
    )
    matched = ambiguous = unmatched = 0
    for transaction in transactions:
        candidates = mobilepay_candidates(aliases, transaction.name, transaction.message)
        if len(candidates) == 1:
            transaction.allocated_player_id = next(iter(candidates)).id
            transaction.allocation_status = "matched"
            matched += 1
        elif len(candidates) > 1:
            transaction.allocation_status = "ambiguous"
            ambiguous += 1
        else:
            transaction.allocation_status = "unmatched"
            unmatched += 1
    database_session.flush()
    return {"checked": len(transactions), "matched": matched, "ambiguous": ambiguous, "unmatched": unmatched}


def process_mobilepay_import(database_session, squad, filename, file_data):
    import hashlib

    file_hash = hashlib.sha256(file_data).hexdigest()
    existing = database_session.scalar(
        select(MobilePayImport).where(MobilePayImport.squad_id == squad.id, MobilePayImport.file_sha256 == file_hash)
    )
    if existing:
        return existing, {"created": 0, "skipped": True, "unmatched": 0, "ambiguous": 0}

    rows = parse_mobilepay_file(file_data)
    mobilepay_import = MobilePayImport(
        squad_id=squad.id,
        filename=filename,
        file_sha256=file_hash,
        raw_file=file_data,
        rows_count=len(rows),
        status="processed",
    )
    database_session.add(mobilepay_import)
    database_session.flush()

    players = list(database_session.scalars(select(Player).where(Player.squad_id == squad.id, Player.active.is_(True))))
    aliases = mobilepay_alias_index(players)

    existing_transactions = list(
        database_session.scalars(select(MobilePayTransaction).where(MobilePayTransaction.squad_id == squad.id))
    )
    existing_fingerprints = {stored_transaction_fingerprint(item) for item in existing_transactions}
    created = skipped = unmatched = ambiguous = 0
    for row in rows:
        if row["fingerprint"] in existing_fingerprints:
            skipped += 1
            continue
        candidates = set()
        if row["transaction_type"] == "pay_in":
            candidates = mobilepay_candidates(aliases, row["name"], row["message"])
        allocation_status = "matched" if len(candidates) == 1 else "ambiguous" if len(candidates) > 1 else "unmatched"
        allocated = next(iter(candidates)).id if len(candidates) == 1 else None
        transaction = MobilePayTransaction(
            squad_id=squad.id,
            import_id=mobilepay_import.id,
            fingerprint=row["fingerprint"],
            transaction_date=row["date"],
            name=row["name"],
            transaction_type_name=row["transaction_type_name"],
            number=row["number"],
            message=row["message"],
            amount_cents=row["amount_cents"],
            currency=row["currency"],
            transaction_type=row["transaction_type"],
            allocation_status=allocation_status,
            allocated_player_id=allocated,
        )
        database_session.add(transaction)
        existing_fingerprints.add(row["fingerprint"])
        created += 1
        unmatched += int(allocation_status == "unmatched")
        ambiguous += int(allocation_status == "ambiguous")

    database_session.flush()
    return mobilepay_import, {"created": created, "skipped": skipped, "unmatched": unmatched, "ambiguous": ambiguous}


def commit_mobilepay_import(database_session, squad, filename, file_data):
    """Commit an import, retrying when another worker inserted the same file first."""
    for attempt in range(2):
        try:
            mobilepay_import, report = process_mobilepay_import(
                database_session, squad, filename, file_data
            )
            database_session.commit()
            return mobilepay_import, report
        except IntegrityError:
            database_session.rollback()
            if attempt == 1:
                raise

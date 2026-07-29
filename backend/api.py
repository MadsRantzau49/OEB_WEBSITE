from datetime import date, datetime, time, timezone
import re
from urllib.parse import urlparse

from flask import Blueprint, jsonify, request, session
from sqlalchemy import and_, delete, func, or_, select

from .db import get_db
from .models import (
    Club,
    DbuSource,
    FineCharge,
    FineRequest,
    FineRule,
    HiddenMobilePayTransaction,
    Match,
    MatchLineupLock,
    MatchLineupPlayer,
    MatchParticipant,
    MobilePayTransaction,
    Player,
    Season,
    Squad,
    SquadPaymentSetting,
    User,
    UserSquadPermission,
    fine_request_recipients,
)
from .permissions import PERMISSIONS, has_permission, permission_error
from .security import (
    clear_login,
    hash_password,
    load_current_user,
    set_login,
    user_required,
    verify_password,
)
from .serializers import (
    charge_json,
    iso,
    match_json,
    money,
    player_json,
    rule_json,
    season_json,
    squad_json,
    transaction_json,
    user_json,
)
from .services import (
    clear_match_lineup_lock,
    create_fine_charge,
    effective_match_players,
    latest_season,
    map_player_to_existing_lineups,
    parse_amount_input,
    process_mobilepay_import,
    rematch_mobilepay_transactions,
    reset_dbu_matches,
    season_for_squad,
    set_match_lineup,
    sync_squad,
)


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


api = Blueprint("api", __name__, url_prefix="/api/v1")


def error(message, status=400, **extra):
    payload = {"error": message}
    payload.update(extra)
    return jsonify(payload), status


def body():
    return request.get_json(silent=True) or {}


def slugify(value):
    value = re.sub(r"[^a-z0-9æøå]+", "-", value.casefold()).strip("-")
    return value or "squad"


def parse_date(value, field_name, required=False):
    if not value and not required:
        return None
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be an ISO date") from exc


def parse_datetime(value, field_name, required=False):
    if not value and not required:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be an ISO date and time") from exc
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def default_season_start(season_name):
    match = re.search(r"(20\d{2})", str(season_name or ""))
    year = int(match.group(1)) if match else date.today().year
    return date(year, 1, 1)


def dbu_urls(data):
    values = data.get("dbuSeasonUrls")
    if values is None:
        values = [data.get("dbuSeasonUrl") or data.get("dbuUrl")]
    if isinstance(values, str):
        values = values.splitlines()
    result = []
    for value in values or []:
        url = str(value or "").strip()
        if not url:
            continue
        parsed = urlparse(url)
        if parsed.scheme != "https" or not parsed.hostname or not (
            parsed.hostname == "dbu.dk" or parsed.hostname.endswith(".dbu.dk")
        ):
            raise ValueError("DBU links must be https links from dbu.dk")
        if url not in result:
            result.append(url)
    return result


def add_dbu_sources(database_session, season, urls):
    for index, url in enumerate(urls, start=1):
        if not database_session.scalar(
            select(DbuSource.id).where(DbuSource.season_id == season.id, DbuSource.url == url)
        ):
            database_session.add(DbuSource(season_id=season.id, label=f"DBU hold {index}", url=url))


def require_squad(database_session, squad_id):
    squad = database_session.get(Squad, squad_id)
    if squad is None or not squad.active:
        return None, error("squad_not_found", 404)
    return squad, None


def require_match(database_session, squad_id, match_id):
    match = database_session.scalar(
        select(Match)
        .join(Season, Season.id == Match.season_id)
        .where(Match.id == match_id, Season.squad_id == squad_id)
    )
    if match is None:
        return None, error("match_not_found", 404)
    return match, None


def permissions_for_user(database_session, user):
    if user.is_owner:
        return [{"squadId": squad.id, "permission": permission} for squad in database_session.scalars(select(Squad)) for permission in PERMISSIONS]
    rows = database_session.scalars(
        select(UserSquadPermission).where(UserSquadPermission.user_id == user.id)
    )
    return [{"squadId": row.squad_id, "permission": row.permission} for row in rows]


def current_user_json(database_session, user):
    payload = user_json(user, permissions_for_user(database_session, user))
    player = database_session.get(Player, user.player_id) if user.player_id else None
    payload["playerSquadId"] = player.squad_id if player else None
    return payload


def _players_for_request(database_session, request_id):
    return list(
        database_session.scalars(
            select(Player)
            .join(fine_request_recipients, fine_request_recipients.c.player_id == Player.id)
            .where(fine_request_recipients.c.request_id == request_id)
        )
    )


def fine_request_json(database_session, fine_request):
    requester = database_session.get(User, fine_request.requested_by_user_id) if fine_request.requested_by_user_id else None
    reviewer = database_session.get(User, fine_request.reviewed_by_user_id) if fine_request.reviewed_by_user_id else None
    recipients = _players_for_request(database_session, fine_request.id)
    return {
        "id": fine_request.id,
        "squadId": fine_request.squad_id,
        "seasonId": fine_request.season_id,
        "ruleId": fine_request.rule_id,
        "title": fine_request.title,
        "description": fine_request.description,
        "amount": money(fine_request.amount_cents),
        "amountCents": fine_request.amount_cents,
        "status": fine_request.status,
        "reviewNote": fine_request.review_note,
        "requester": requester.username if requester else "Deleted user",
        "reviewer": reviewer.username if reviewer else None,
        "recipients": [{"id": player.id, "name": player.dbu_name} for player in recipients],
        "createdAt": iso(fine_request.created_at),
        "reviewedAt": iso(fine_request.reviewed_at),
    }


def dashboard_json(database_session, squad, season, include_matches=True, include_account_status=False):
    players = list(
        database_session.scalars(
            select(Player).where(Player.squad_id == squad.id, Player.active.is_(True)).order_by(Player.dbu_name)
        )
    )
    account_player_ids = set()
    if include_account_status:
        account_player_ids = set(
            database_session.scalars(
                select(User.player_id).where(User.player_id.in_([player.id for player in players]))
            )
        )
    charges = list(
        database_session.scalars(
            select(FineCharge).where(FineCharge.squad_id == squad.id, FineCharge.season_id == season.id).order_by(FineCharge.charge_date.desc(), FineCharge.id.desc())
        )
    )
    start_at = datetime.combine(season.start_date, time.min)
    end_at = datetime.combine(season.end_date, time.max) if season.end_date else None
    all_transaction_query = select(MobilePayTransaction).where(
        MobilePayTransaction.squad_id == squad.id,
        MobilePayTransaction.transaction_date >= start_at,
    )
    if end_at:
        all_transaction_query = all_transaction_query.where(MobilePayTransaction.transaction_date <= end_at)
    season_transactions = list(
        database_session.scalars(all_transaction_query.order_by(MobilePayTransaction.transaction_date.desc()))
    )
    hidden_transaction_ids = set(
        database_session.scalars(select(HiddenMobilePayTransaction.transaction_id))
    )
    season_transactions = [
        item for item in season_transactions if item.id not in hidden_transaction_ids
    ]
    transactions = [
        item for item in season_transactions
        if item.transaction_type == "pay_in" and item.allocated_player_id is not None
    ]
    charges_by_player = {}
    charges_list_by_player = {}
    for charge in charges:
        charges_by_player[charge.player_id] = charges_by_player.get(charge.player_id, 0) + charge.amount_cents
        charges_list_by_player.setdefault(charge.player_id, []).append(charge)
    payments_by_player = {}
    payments_list_by_player = {}
    for transaction in transactions:
        payments_by_player[transaction.allocated_player_id] = payments_by_player.get(transaction.allocated_player_id, 0) + transaction.amount_cents
        payments_list_by_player.setdefault(transaction.allocated_player_id, []).append(transaction)

    washes = dict(
        database_session.execute(
            select(Match.clothes_washer_id, func.count(Match.id))
            .where(Match.season_id == season.id, Match.clothes_washer_id.is_not(None))
            .group_by(Match.clothes_washer_id)
        ).all()
    )
    player_payload = []
    for player in players:
        payload = {
            **player_json(
                player,
                charges_by_player.get(player.id, 0),
                payments_by_player.get(player.id, 0),
                washes.get(player.id, 0),
            ),
            "fines": [charge_json(charge, player.dbu_name) for charge in charges_list_by_player.get(player.id, [])],
            "payments": [transaction_json(transaction, player.dbu_name) for transaction in payments_list_by_player.get(player.id, [])],
        }
        if include_account_status:
            payload["hasAccount"] = player.id in account_player_ids
        player_payload.append(payload)

    matches = list(
        database_session.scalars(
            select(Match)
            .where(Match.season_id == season.id)
            .order_by(Match.match_date.is_(None), Match.match_date, Match.id)
        )
    ) if include_matches else []
    match_payload = []
    for match in matches:
        lineup_locked = database_session.get(MatchLineupLock, match.id) is not None
        if lineup_locked:
            participant_payload = [
                {"id": None, "name": player.dbu_name, "playerId": player.id, "playerName": player.dbu_name, "status": "manual"}
                for player in effective_match_players(database_session, match)
            ]
        else:
            participant_payload = []
            participants = database_session.scalars(
                select(MatchParticipant).where(MatchParticipant.match_id == match.id).order_by(MatchParticipant.source_name)
            )
            for participant in participants:
                player = database_session.get(Player, participant.player_id) if participant.player_id else None
                participant_payload.append(
                    {"id": participant.id, "name": participant.source_name, "playerId": participant.player_id, "playerName": player.dbu_name if player else None, "status": participant.status}
                )
        washer = database_session.get(Player, match.clothes_washer_id) if match.clothes_washer_id else None
        match_payload.append(match_json(match, participant_payload, washer.dbu_name if washer else None, lineup_locked))

    rules = list(database_session.scalars(select(FineRule).where(FineRule.squad_id == squad.id, FineRule.active.is_(True), FineRule.rule_type != "MATCH_FINE").order_by(FineRule.name)))
    seasons = list(database_session.scalars(select(Season).where(Season.squad_id == squad.id, Season.active.is_(True)).order_by(Season.id.desc())))
    total_fines = sum(charges_by_player.values())
    total_paid = sum(payments_by_player.values())
    outstanding = sum(
        max(charges_by_player.get(player.id, 0) - payments_by_player.get(player.id, 0), 0)
        for player in players
    )
    player_credit = sum(
        max(payments_by_player.get(player.id, 0) - charges_by_player.get(player.id, 0), 0)
        for player in players
    )
    cash_balance = sum(item.amount_cents for item in season_transactions)
    payment_setting = database_session.get(SquadPaymentSetting, squad.id)
    sources = list(
        database_session.scalars(
            select(DbuSource).where(DbuSource.season_id == season.id, DbuSource.active.is_(True)).order_by(DbuSource.id)
        )
    )
    return {
        "squad": squad_json(squad, season),
        "season": season_json(season),
        "seasons": [season_json(item) for item in seasons],
        "players": player_payload,
        "matches": match_payload,
        "rules": [rule_json(rule) for rule in rules],
        "expenses": [
            transaction_json(item)
            for item in season_transactions
            if item.transaction_type == "pay_out"
        ],
        "balanceSummary": {
            "boxBalance": money(cash_balance),
            "ifEveryonePays": money(cash_balance + outstanding),
            "outstanding": money(outstanding),
            "playerCredit": money(player_credit),
            "totalFines": money(total_fines),
            "totalPaid": money(total_paid),
            "debtors": sum(1 for player in players if charges_by_player.get(player.id, 0) > payments_by_player.get(player.id, 0)),
        },
        "payment": {
            "boxNumber": payment_setting.box_number if payment_setting else None,
            "paymentUrl": payment_setting.payment_url if payment_setting else None,
        },
        "dbuSources": [
            {"id": source.id, "label": source.label, "url": source.url}
            for source in sources
        ],
        "lastSync": iso(max((match.last_synced_at for match in matches if match.last_synced_at), default=None)),
    }


@api.get("/health")
def health():
    return jsonify({"status": "ok"})


@api.get("/setup/status")
def setup_status():
    database_session = get_db()
    club = database_session.scalar(select(Club).order_by(Club.id))
    squads = list(database_session.scalars(select(Squad).where(Squad.active.is_(True)).order_by(Squad.name)))
    return jsonify(
        {
            "needsSetup": database_session.scalar(select(func.count(User.id))) == 0,
            "clubName": club.name if club else None,
            "squads": [squad_json(squad, latest_season(database_session, squad.id)) for squad in squads],
        }
    )


@api.post("/setup")
def setup():
    database_session = get_db()
    if database_session.scalar(select(func.count(User.id))) != 0:
        return error("setup_already_completed", 409)
    data = body()
    username = str(data.get("username", "")).strip().casefold()
    password = str(data.get("password", ""))
    club_name = str(data.get("clubName", "")).strip()
    squad_name = str(data.get("squadName", "")).strip()
    if len(username) < 3 or not club_name or not squad_name:
        return error("club_name_squad_name_and_username_are_required")
    try:
        source_urls = dbu_urls(data)
    except ValueError as exc:
        return error(str(exc))
    club = Club(name=club_name)
    database_session.add(club)
    database_session.flush()
    squad = Squad(
        club_id=club.id,
        name=squad_name,
        slug=slugify(squad_name),
        dbu_club_name=str(data.get("dbuClubName", squad_name)).strip() or squad_name,
        dbu_season_url=source_urls[0] if source_urls else None,
    )
    database_session.add(squad)
    database_session.flush()
    try:
        start_date = parse_date(data.get("seasonStart"), "seasonStart") or default_season_start(data.get("seasonName"))
        end_date = parse_date(data.get("seasonEnd"), "seasonEnd")
    except ValueError as exc:
        return error(str(exc))
    season = Season(
        squad_id=squad.id,
        name=str(data.get("seasonName", "2026")).strip() or "2026",
        dbu_url=source_urls[0] if source_urls else None,
        start_date=start_date,
        end_date=end_date,
    )
    database_session.add(season)
    database_session.flush()
    add_dbu_sources(database_session, season, source_urls)
    box_number = str(data.get("mobilePayBoxNumber", "")).strip() or None
    payment_url = str(data.get("mobilePayUrl", "")).strip() or None
    if box_number or payment_url:
        database_session.add(
            SquadPaymentSetting(squad_id=squad.id, box_number=box_number, payment_url=payment_url)
        )
    database_session.add(User(username=username, password_hash=hash_password(password), is_owner=True))
    database_session.commit()
    user = database_session.scalar(select(User).where(User.username == username))
    set_login(user)
    return jsonify({"user": current_user_json(database_session, user), "csrfToken": session.get("csrf_token"), "squad": squad_json(squad, season)}), 201


@api.get("/public/squads")
def public_squads():
    database_session = get_db()
    squads = list(database_session.scalars(select(Squad).where(Squad.active.is_(True)).order_by(Squad.name)))
    return jsonify({"squads": [squad_json(squad, latest_season(database_session, squad.id)) for squad in squads]})


@api.post("/squads")
@user_required
def create_squad():
    database_session = get_db()
    user = load_current_user()
    if not user.is_owner:
        return error("permission_denied", 403)
    data = body()
    name = str(data.get("name", "")).strip()
    dbu_club_name = str(data.get("dbuClubName", "")).strip()
    if not name or not dbu_club_name:
        return error("squad_name_and_dbu_club_name_are_required")
    try:
        source_urls = dbu_urls(data)
    except ValueError as exc:
        return error(str(exc))
    club = database_session.scalar(select(Club).order_by(Club.id))
    if club is None:
        return error("club_not_found", 404)
    slug = slugify(name)
    if database_session.scalar(select(Squad).where(Squad.slug == slug)):
        return error("squad_name_already_exists", 409)
    squad = Squad(
        club_id=club.id,
        name=name,
        slug=slug,
        dbu_club_name=dbu_club_name,
        dbu_season_url=source_urls[0] if source_urls else None,
    )
    database_session.add(squad)
    database_session.flush()
    try:
        start_date = parse_date(data.get("seasonStart"), "seasonStart") or default_season_start(data.get("seasonName"))
        end_date = parse_date(data.get("seasonEnd"), "seasonEnd")
    except ValueError as exc:
        database_session.rollback()
        return error(str(exc))
    season = Season(
        squad_id=squad.id,
        name=str(data.get("seasonName", str(start_date.year))).strip() or str(start_date.year),
        dbu_url=source_urls[0] if source_urls else None,
        start_date=start_date,
        end_date=end_date,
    )
    database_session.add(season)
    database_session.flush()
    add_dbu_sources(database_session, season, source_urls)
    database_session.commit()
    return jsonify({"squad": squad_json(squad, season)}), 201


@api.get("/public/squads/<slug>/dashboard")
def public_dashboard(slug):
    database_session = get_db()
    squad = database_session.scalar(select(Squad).where(Squad.slug == slug, Squad.active.is_(True)))
    if squad is None:
        return error("squad_not_found", 404)
    season = season_for_squad(database_session, squad.id, request.args.get("seasonId", type=int))
    if season is None:
        return error("season_not_found", 404)
    return jsonify(dashboard_json(database_session, squad, season, include_matches=False))


@api.get("/public/squads/<slug>/players")
def public_players(slug):
    database_session = get_db()
    squad = database_session.scalar(select(Squad).where(Squad.slug == slug, Squad.active.is_(True)))
    if squad is None:
        return error("squad_not_found", 404)
    players = database_session.scalars(select(Player).where(Player.squad_id == squad.id, Player.active.is_(True)).order_by(Player.dbu_name))
    return jsonify({"players": [player_json(player) for player in players]})


@api.post("/auth/register")
def register():
    database_session = get_db()
    if database_session.scalar(select(func.count(User.id))) == 0:
        return error("setup_required", 409)
    data = body()
    username = str(data.get("username", "")).strip().casefold()
    password = str(data.get("password", ""))
    if not re.fullmatch(r"[A-Za-z0-9_.-]{3,80}", username):
        return error("username_must_be_3_to_80_simple_characters")
    if database_session.scalar(select(User).where(func.lower(User.username) == username)):
        return error("username_already_exists", 409)
    player_id = data.get("playerId")
    if player_id:
        player = database_session.get(Player, int(player_id))
        if player is None or not player.active:
            return error("player_not_found", 404)
        if database_session.scalar(select(User).where(User.player_id == player.id)):
            return error("player_already_has_account", 409)
    user = User(username=username, password_hash=hash_password(password), player_id=int(player_id) if player_id else None)
    database_session.add(user)
    database_session.commit()
    set_login(user)
    return jsonify({"user": current_user_json(database_session, user)}), 201


@api.post("/auth/login")
def login():
    database_session = get_db()
    data = body()
    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))
    user = database_session.scalar(select(User).where(func.lower(User.username) == username.casefold()))
    if user is None or not verify_password(user.password_hash, password) or not user.is_active:
        return error("invalid_username_or_password", 401)
    user.password_hash = hash_password(password)
    database_session.commit()
    set_login(user)
    return jsonify({"user": current_user_json(database_session, user)})


@api.post("/auth/logout")
def logout():
    clear_login()
    return jsonify({"ok": True})


@api.get("/auth/me")
@user_required
def me():
    database_session = get_db()
    return jsonify({"user": current_user_json(database_session, load_current_user()), "csrfToken": session.get("csrf_token")})


@api.get("/squads/<int:squad_id>/dashboard")
@user_required
def authenticated_dashboard(squad_id):
    database_session = get_db()
    squad, squad_error = require_squad(database_session, squad_id)
    if squad_error:
        return squad_error
    season = season_for_squad(database_session, squad_id, request.args.get("seasonId", type=int))
    if season is None:
        return error("season_not_found", 404)
    user = load_current_user()
    can_manage_roster = has_permission(database_session, user, squad_id, "manage_roster")
    include_matches = can_manage_roster or any(
        has_permission(database_session, user, squad_id, permission)
        for permission in ("manage_matches", "manage_dbu_sync")
    )
    return jsonify(
        dashboard_json(
            database_session,
            squad,
            season,
            include_matches=include_matches,
            include_account_status=can_manage_roster,
        )
    )


@api.get("/squads/<int:squad_id>/fine-requests")
@user_required
def list_fine_requests(squad_id):
    database_session = get_db()
    squad, squad_error = require_squad(database_session, squad_id)
    if squad_error:
        return squad_error
    user = load_current_user()
    can_review = has_permission(database_session, user, squad_id, "approve_fine_requests")
    query = select(FineRequest).where(FineRequest.squad_id == squad_id)
    if not can_review:
        request_ids = select(fine_request_recipients.c.request_id).where(fine_request_recipients.c.player_id == user.player_id) if user.player_id else select(FineRequest.id).where(FineRequest.requested_by_user_id == user.id)
        query = query.where(or_(FineRequest.requested_by_user_id == user.id, FineRequest.id.in_(request_ids)))
    requests = database_session.scalars(query.order_by(FineRequest.created_at.desc()))
    return jsonify({"requests": [fine_request_json(database_session, item) for item in requests]})


@api.post("/squads/<int:squad_id>/fine-requests")
@user_required
def create_fine_request(squad_id):
    database_session = get_db()
    squad, squad_error = require_squad(database_session, squad_id)
    if squad_error:
        return squad_error
    data = body()
    season = season_for_squad(database_session, squad_id, data.get("seasonId"))
    if season is None:
        return error("season_not_found", 404)
    recipient_ids = data.get("playerIds") or ([data.get("playerId")] if data.get("playerId") else [])
    recipient_ids = [int(item) for item in recipient_ids if item is not None]
    players = list(database_session.scalars(select(Player).where(Player.squad_id == squad_id, Player.id.in_(recipient_ids), Player.active.is_(True)))) if recipient_ids else []
    if not players or len(players) != len(set(recipient_ids)):
        return error("select_at_least_one_valid_player")
    rule = None
    if data.get("ruleId"):
        try:
            rule_id = int(data["ruleId"])
        except (TypeError, ValueError):
            return error("fine_rule_not_found", 404)
        rule = database_session.scalar(
            select(FineRule).where(FineRule.id == rule_id, FineRule.squad_id == squad_id)
        )
        if rule is None:
            return error("fine_rule_not_found", 404)
    try:
        amount_cents = rule.amount_cents if rule else parse_amount_input(data)
    except (ValueError, TypeError) as exc:
        return error(str(exc))
    title = (rule.name if rule else str(data.get("title", "")).strip())
    description = rule.description if rule else str(data.get("description", "")).strip()
    if not title:
        return error("title_is_required")
    user = load_current_user()
    fine_request = FineRequest(
        squad_id=squad_id,
        season_id=season.id,
        requested_by_user_id=user.id,
        rule_id=rule.id if rule else None,
        title=title,
        description=description,
        amount_cents=max(0, amount_cents),
    )
    database_session.add(fine_request)
    database_session.flush()
    database_session.execute(fine_request_recipients.insert(), [{"request_id": fine_request.id, "player_id": player.id} for player in players])
    if has_permission(database_session, user, squad_id, "approve_fine_requests"):
        for player in players:
            create_fine_charge(
                database_session,
                squad_id=squad_id,
                season_id=season.id,
                player_id=player.id,
                source="request",
                source_key=f"request:{fine_request.id}:player:{player.id}",
                fine_request_id=fine_request.id,
                title=fine_request.title,
                description=fine_request.description,
                amount_cents=fine_request.amount_cents,
            )
        fine_request.status = "approved"
        fine_request.reviewed_by_user_id = user.id
        fine_request.reviewed_at = utc_now()
    database_session.commit()
    return jsonify({"request": fine_request_json(database_session, fine_request)}), 201


@api.post("/squads/<int:squad_id>/fine-requests/<int:request_id>/approve")
@user_required
def approve_fine_request(squad_id, request_id):
    database_session = get_db()
    permission = permission_error(database_session, load_current_user(), squad_id, "approve_fine_requests")
    if permission:
        return permission
    fine_request = database_session.scalar(select(FineRequest).where(FineRequest.id == request_id, FineRequest.squad_id == squad_id))
    if fine_request is None:
        return error("fine_request_not_found", 404)
    if fine_request.status != "pending":
        return error("fine_request_already_reviewed", 409)
    recipients = _players_for_request(database_session, fine_request.id)
    user = load_current_user()
    for player in recipients:
        create_fine_charge(
            database_session,
            squad_id=squad_id,
            season_id=fine_request.season_id,
            player_id=player.id,
            source="request",
            source_key=f"request:{fine_request.id}:player:{player.id}",
            fine_request_id=fine_request.id,
            title=fine_request.title,
            description=fine_request.description,
            amount_cents=fine_request.amount_cents,
        )
    fine_request.status = "approved"
    fine_request.reviewed_by_user_id = user.id
    fine_request.reviewed_at = utc_now()
    fine_request.review_note = str(body().get("note", "")).strip() or None
    database_session.commit()
    return jsonify({"request": fine_request_json(database_session, fine_request)})


@api.post("/squads/<int:squad_id>/fine-requests/<int:request_id>/reject")
@user_required
def reject_fine_request(squad_id, request_id):
    database_session = get_db()
    permission = permission_error(database_session, load_current_user(), squad_id, "approve_fine_requests")
    if permission:
        return permission
    fine_request = database_session.scalar(select(FineRequest).where(FineRequest.id == request_id, FineRequest.squad_id == squad_id))
    if fine_request is None:
        return error("fine_request_not_found", 404)
    if fine_request.status != "pending":
        return error("fine_request_already_reviewed", 409)
    user = load_current_user()
    fine_request.status = "rejected"
    fine_request.reviewed_by_user_id = user.id
    fine_request.reviewed_at = utc_now()
    fine_request.review_note = str(body().get("note", "")).strip() or None
    database_session.commit()
    return jsonify({"request": fine_request_json(database_session, fine_request)})


@api.post("/squads/<int:squad_id>/charges")
@user_required
def create_direct_charges(squad_id):
    database_session = get_db()
    permission = permission_error(database_session, load_current_user(), squad_id, "issue_fines")
    if permission:
        return permission
    data = body()
    season = season_for_squad(database_session, squad_id, data.get("seasonId"))
    if season is None:
        return error("season_not_found", 404)
    player_ids = data.get("playerIds") or ([data.get("playerId")] if data.get("playerId") else [])
    try:
        amount_cents = parse_amount_input(data)
    except (ValueError, TypeError) as exc:
        return error(str(exc))
    if not data.get("title") or not player_ids:
        return error("title_and_players_are_required")
    created = []
    for player_id in player_ids:
        charge, _ = create_fine_charge(
            database_session,
            squad_id=squad_id,
            season_id=season.id,
            player_id=int(player_id),
            source="manual",
            title=str(data["title"]),
            description=str(data.get("description", "")),
            amount_cents=amount_cents,
        )
        created.append(charge)
    database_session.commit()
    return jsonify({"charges": [charge_json(charge) for charge in created]}), 201


def can_manage_charges(database_session, user, squad_id):
    return has_permission(database_session, user, squad_id, "issue_fines") or has_permission(
        database_session, user, squad_id, "approve_fine_requests"
    )


@api.patch("/squads/<int:squad_id>/charges/<int:charge_id>")
@user_required
def update_charge(squad_id, charge_id):
    database_session = get_db()
    if not can_manage_charges(database_session, load_current_user(), squad_id):
        return error("permission_denied", 403)
    charge = database_session.scalar(
        select(FineCharge).where(FineCharge.id == charge_id, FineCharge.squad_id == squad_id)
    )
    if charge is None:
        return error("fine_charge_not_found", 404)
    data = body()
    if "title" in data:
        title = str(data["title"] or "").strip()
        if not title:
            return error("title_is_required")
        charge.title = title
    if "description" in data:
        charge.description = str(data["description"] or "").strip()
    if "amount" in data or "amountCents" in data:
        try:
            charge.amount_cents = max(0, parse_amount_input(data))
        except (ValueError, TypeError) as exc:
            return error(str(exc))
    database_session.commit()
    return jsonify({"charge": charge_json(charge)})


@api.delete("/squads/<int:squad_id>/charges/<int:charge_id>")
@user_required
def delete_charge(squad_id, charge_id):
    database_session = get_db()
    if not can_manage_charges(database_session, load_current_user(), squad_id):
        return error("permission_denied", 403)
    charge = database_session.scalar(
        select(FineCharge).where(FineCharge.id == charge_id, FineCharge.squad_id == squad_id)
    )
    if charge is None:
        return error("fine_charge_not_found", 404)
    database_session.delete(charge)
    database_session.commit()
    return jsonify({"deleted": True})


@api.get("/squads/<int:squad_id>/fine-rules")
@user_required
def get_fine_rules(squad_id):
    database_session = get_db()
    squad, squad_error = require_squad(database_session, squad_id)
    if squad_error:
        return squad_error
    rules = database_session.scalars(select(FineRule).where(FineRule.squad_id == squad_id).order_by(FineRule.name))
    return jsonify({"rules": [rule_json(rule) for rule in rules]})


@api.post("/squads/<int:squad_id>/fine-rules")
@user_required
def create_fine_rule(squad_id):
    database_session = get_db()
    permission = permission_error(database_session, load_current_user(), squad_id, "manage_fine_rules")
    if permission:
        return permission
    data = body()
    try:
        amount_cents = parse_amount_input(data)
    except (ValueError, TypeError) as exc:
        return error(str(exc))
    name = str(data.get("name", "")).strip()
    if not name:
        return error("name_is_required")
    rule_type = str(data.get("type", "TEAM_FINE"))
    automatic_types = {"WIN_FINE", "DRAW_FINE", "LOSE_FINE", "SCORED_GOAL", "CONCEDED_GOAL"}
    if rule_type in automatic_types and database_session.scalar(
        select(FineRule).where(FineRule.squad_id == squad_id, FineRule.rule_type == rule_type, FineRule.active.is_(True))
    ):
        return error("only_one_automatic_rule_of_each_type_is_allowed")
    rule = FineRule(
        squad_id=squad_id,
        name=name,
        description=str(data.get("description", "")),
        amount_cents=max(0, amount_cents),
        rule_type=rule_type,
    )
    database_session.add(rule)
    database_session.commit()
    return jsonify({"rule": rule_json(rule)}), 201


@api.patch("/squads/<int:squad_id>/fine-rules/<int:rule_id>")
@user_required
def update_fine_rule(squad_id, rule_id):
    database_session = get_db()
    permission = permission_error(database_session, load_current_user(), squad_id, "manage_fine_rules")
    if permission:
        return permission
    rule = database_session.scalar(select(FineRule).where(FineRule.id == rule_id, FineRule.squad_id == squad_id))
    if rule is None:
        return error("fine_rule_not_found", 404)
    data = body()
    if "name" in data:
        rule.name = str(data["name"]).strip()
    if "description" in data:
        rule.description = str(data["description"])
    if "amount" in data or "amountCents" in data:
        try:
            rule.amount_cents = max(0, parse_amount_input(data))
        except (ValueError, TypeError) as exc:
            return error(str(exc))
    if "active" in data:
        rule.active = bool(data["active"])
    database_session.commit()
    return jsonify({"rule": rule_json(rule)})


@api.delete("/squads/<int:squad_id>/fine-rules/<int:rule_id>")
@user_required
def delete_fine_rule(squad_id, rule_id):
    database_session = get_db()
    permission = permission_error(database_session, load_current_user(), squad_id, "manage_fine_rules")
    if permission:
        return permission
    rule = database_session.scalar(
        select(FineRule).where(FineRule.id == rule_id, FineRule.squad_id == squad_id)
    )
    if rule is None:
        return error("fine_rule_not_found", 404)
    database_session.delete(rule)
    database_session.commit()
    return jsonify({"deleted": True})


@api.get("/squads/<int:squad_id>/players")
@user_required
def get_players(squad_id):
    database_session = get_db()
    squad, squad_error = require_squad(database_session, squad_id)
    if squad_error:
        return squad_error
    players = database_session.scalars(select(Player).where(Player.squad_id == squad_id).order_by(Player.dbu_name))
    return jsonify({"players": [player_json(player) for player in players]})


@api.post("/squads/<int:squad_id>/players")
@user_required
def create_player(squad_id):
    database_session = get_db()
    permission = permission_error(database_session, load_current_user(), squad_id, "manage_roster")
    if permission:
        return permission
    data = body()
    dbu_name = str(data.get("dbuName", "")).strip()
    if not dbu_name:
        return error("dbu_name_is_required")
    if database_session.scalar(
        select(Player.id).where(Player.squad_id == squad_id, func.lower(Player.dbu_name) == dbu_name.casefold())
    ):
        return error("player_already_exists", 409)
    player = Player(squad_id=squad_id, dbu_name=dbu_name, mobilepay_name=str(data.get("mobilePayName", "")).strip() or None)
    database_session.add(player)
    database_session.flush()
    map_player_to_existing_lineups(database_session, player, database_session.get(Squad, squad_id))
    database_session.commit()
    return jsonify({"player": player_json(player)}), 201


@api.patch("/squads/<int:squad_id>/players/<int:player_id>")
@user_required
def update_player(squad_id, player_id):
    database_session = get_db()
    permission = permission_error(database_session, load_current_user(), squad_id, "manage_roster")
    if permission:
        return permission
    player = database_session.scalar(select(Player).where(Player.id == player_id, Player.squad_id == squad_id))
    if player is None:
        return error("player_not_found", 404)
    data = body()
    if "dbuName" in data:
        dbu_name = str(data["dbuName"]).strip()
        if not dbu_name:
            return error("dbu_name_is_required")
        duplicate = database_session.scalar(
            select(Player.id).where(
                Player.squad_id == squad_id,
                Player.id != player.id,
                func.lower(Player.dbu_name) == dbu_name.casefold(),
            )
        )
        if duplicate:
            return error("player_already_exists", 409)
        player.dbu_name = dbu_name
    if "mobilePayName" in data:
        player.mobilepay_name = str(data["mobilePayName"]).strip() or None
    if "active" in data:
        player.active = bool(data["active"])
    if player.active:
        map_player_to_existing_lineups(database_session, player, database_session.get(Squad, squad_id))
    database_session.commit()
    return jsonify({"player": player_json(player)})


@api.delete("/squads/<int:squad_id>/players/<int:player_id>/account")
@user_required
def delete_player_account(squad_id, player_id):
    database_session = get_db()
    permission = permission_error(database_session, load_current_user(), squad_id, "manage_roster")
    if permission:
        return permission
    player = database_session.scalar(select(Player).where(Player.id == player_id, Player.squad_id == squad_id))
    if player is None:
        return error("player_not_found", 404)
    account = database_session.scalar(select(User).where(User.player_id == player.id))
    if account is None:
        return error("player_account_not_found", 404)
    if account.is_owner:
        return error("owner_account_cannot_be_deleted", 409)
    database_session.delete(account)
    database_session.commit()
    return jsonify({"ok": True})


@api.delete("/squads/<int:squad_id>/players/<int:player_id>")
@user_required
def delete_player(squad_id, player_id):
    database_session = get_db()
    permission = permission_error(database_session, load_current_user(), squad_id, "manage_roster")
    if permission:
        return permission
    player = database_session.scalar(select(Player).where(Player.id == player_id, Player.squad_id == squad_id))
    if player is None:
        return error("player_not_found", 404)

    account = database_session.scalar(select(User).where(User.player_id == player.id))
    if account is not None and account.is_owner:
        return error("owner_account_cannot_be_deleted", 409)

    participants = list(
        database_session.scalars(select(MatchParticipant).where(MatchParticipant.player_id == player.id))
    )
    affected_match_ids = {participant.match_id for participant in participants}
    affected_match_ids.update(
        database_session.scalars(
            select(MatchLineupPlayer.match_id).where(MatchLineupPlayer.player_id == player.id)
        )
    )
    affected_match_ids.update(
        database_session.scalars(select(Match.id).where(Match.clothes_washer_id == player.id))
    )
    for participant in participants:
        participant.player_id = None
        participant.status = "unmatched"
    removed_fines = database_session.scalar(
        select(func.count(FineCharge.id)).where(FineCharge.player_id == player.id)
    ) or 0
    removed_match_fines = database_session.scalar(
        select(func.count(FineCharge.id)).where(FineCharge.player_id == player.id, FineCharge.source == "match")
    ) or 0
    fine_request_ids = list(
        database_session.scalars(
            select(fine_request_recipients.c.request_id).where(
                fine_request_recipients.c.player_id == player.id
            )
        )
    )
    database_session.execute(
        delete(FineCharge).where(FineCharge.player_id == player.id)
    )
    database_session.execute(
        delete(fine_request_recipients).where(fine_request_recipients.c.player_id == player.id)
    )
    orphaned_request_ids = [
        request_id
        for request_id in fine_request_ids
        if database_session.scalar(
            select(fine_request_recipients.c.request_id).where(
                fine_request_recipients.c.request_id == request_id
            ).limit(1)
        ) is None
    ]
    if orphaned_request_ids:
        database_session.execute(delete(FineRequest).where(FineRequest.id.in_(orphaned_request_ids)))
    payments = list(
        database_session.scalars(
            select(MobilePayTransaction).where(MobilePayTransaction.allocated_player_id == player.id)
        )
    )
    for payment in payments:
        payment.allocated_player_id = None
        payment.allocation_status = "unmatched"
    database_session.execute(delete(MatchLineupPlayer).where(MatchLineupPlayer.player_id == player.id))
    for match_id in affected_match_ids:
        match = database_session.get(Match, match_id)
        if match:
            match.status = "needs_review"
    if account is not None:
        database_session.delete(account)
    database_session.delete(player)
    database_session.commit()
    return jsonify(
        {
            "ok": True,
            "deletedAccount": account is not None,
            "removedFines": removed_fines,
            "removedFineRequests": len(orphaned_request_ids),
            "removedMatchFines": removed_match_fines,
            "unassignedPayments": len(payments),
        }
    )


@api.post("/squads/<int:squad_id>/mobilepay-imports")
@user_required
def upload_mobilepay(squad_id):
    database_session = get_db()
    permission = permission_error(database_session, load_current_user(), squad_id, "manage_finance")
    if permission:
        return permission
    squad, squad_error = require_squad(database_session, squad_id)
    if squad_error:
        return squad_error
    upload = request.files.get("file") or request.files.get("mobilepay_transaction_file")
    if upload is None or not upload.filename.lower().endswith(".xlsx"):
        return error("an_xlsx_file_is_required")
    try:
        mobilepay_import, report = process_mobilepay_import(database_session, squad, upload.filename, upload.read())
        database_session.commit()
    except Exception as exc:
        database_session.rollback()
        return error(str(exc))
    return jsonify({"import": {"id": mobilepay_import.id, "filename": mobilepay_import.filename, "rows": mobilepay_import.rows_count, "status": mobilepay_import.status}, "report": report}), 201


@api.get("/squads/<int:squad_id>/transactions")
@user_required
def get_transactions(squad_id):
    database_session = get_db()
    permission = permission_error(database_session, load_current_user(), squad_id, "manage_finance")
    if permission:
        return permission
    season = season_for_squad(database_session, squad_id, request.args.get("seasonId", type=int))
    if season is None:
        return error("season_not_found", 404)
    status = request.args.get("status")
    hidden_ids = select(HiddenMobilePayTransaction.transaction_id)
    query = select(MobilePayTransaction).where(
        MobilePayTransaction.squad_id == squad_id,
        MobilePayTransaction.id.not_in(hidden_ids),
        MobilePayTransaction.transaction_date >= datetime.combine(season.start_date, time.min),
    )
    if season.end_date:
        query = query.where(MobilePayTransaction.transaction_date <= datetime.combine(season.end_date, time.max))
    if status:
        query = query.where(MobilePayTransaction.allocation_status == status)
    transactions = database_session.scalars(query.order_by(MobilePayTransaction.transaction_date.desc()))
    result = []
    for transaction in transactions:
        player = database_session.get(Player, transaction.allocated_player_id) if transaction.allocated_player_id else None
        result.append(transaction_json(transaction, player.dbu_name if player else None))
    return jsonify({"transactions": result})


@api.post("/squads/<int:squad_id>/transactions/rematch")
@user_required
def rematch_transactions(squad_id):
    database_session = get_db()
    permission = permission_error(database_session, load_current_user(), squad_id, "manage_finance")
    if permission:
        return permission
    squad, squad_error = require_squad(database_session, squad_id)
    if squad_error:
        return squad_error
    report = rematch_mobilepay_transactions(database_session, squad)
    database_session.commit()
    return jsonify({"report": report})


@api.delete("/squads/<int:squad_id>/transactions/<int:transaction_id>")
@user_required
def hide_transaction(squad_id, transaction_id):
    database_session = get_db()
    permission = permission_error(database_session, load_current_user(), squad_id, "manage_finance")
    if permission:
        return permission
    transaction = database_session.scalar(
        select(MobilePayTransaction).where(
            MobilePayTransaction.id == transaction_id,
            MobilePayTransaction.squad_id == squad_id,
        )
    )
    if transaction is None:
        return error("transaction_not_found", 404)
    hidden = database_session.get(HiddenMobilePayTransaction, transaction.id)
    if hidden is None:
        database_session.add(
            HiddenMobilePayTransaction(
                transaction_id=transaction.id,
                hidden_by_user_id=load_current_user().id,
            )
        )
    database_session.commit()
    return jsonify({"ok": True})


@api.post("/squads/<int:squad_id>/transactions/<int:transaction_id>/assign")
@user_required
def assign_transaction(squad_id, transaction_id):
    database_session = get_db()
    permission = permission_error(database_session, load_current_user(), squad_id, "manage_finance")
    if permission:
        return permission
    transaction = database_session.scalar(select(MobilePayTransaction).where(MobilePayTransaction.id == transaction_id, MobilePayTransaction.squad_id == squad_id))
    if transaction is None:
        return error("transaction_not_found", 404)
    player_id = body().get("playerId")
    if player_id is None:
        transaction.allocated_player_id = None
        transaction.allocation_status = "unmatched"
    else:
        player = database_session.scalar(select(Player).where(Player.id == int(player_id), Player.squad_id == squad_id, Player.active.is_(True)))
        if player is None:
            return error("player_not_found", 404)
        transaction.allocated_player_id = player.id
        transaction.allocation_status = "matched"
    database_session.commit()
    player = database_session.get(Player, transaction.allocated_player_id) if transaction.allocated_player_id else None
    return jsonify({"transaction": transaction_json(transaction, player.dbu_name if player else None)})


@api.put("/squads/<int:squad_id>/payment-settings")
@user_required
def update_payment_settings(squad_id):
    database_session = get_db()
    permission = permission_error(database_session, load_current_user(), squad_id, "manage_finance")
    if permission:
        return permission
    squad, squad_error = require_squad(database_session, squad_id)
    if squad_error:
        return squad_error
    data = body()
    box_number = str(data.get("boxNumber", "")).strip().upper() or None
    payment_url = str(data.get("paymentUrl", "")).strip() or None
    if payment_url:
        parsed = urlparse(payment_url)
        if parsed.scheme != "https" or parsed.hostname != "qr.mobilepay.dk" or "/box/" not in parsed.path or not parsed.path.endswith("/pay-in"):
            return error("Use the MobilePay Box share link ending in /pay-in")
    setting = database_session.get(SquadPaymentSetting, squad_id)
    if setting is None:
        setting = SquadPaymentSetting(squad_id=squad_id)
        database_session.add(setting)
    setting.box_number = box_number
    setting.payment_url = payment_url
    database_session.commit()
    return jsonify({"payment": {"boxNumber": box_number, "paymentUrl": payment_url}})


@api.post("/squads/<int:squad_id>/seasons/<int:season_id>/dbu-sources")
@user_required
def create_dbu_source(squad_id, season_id):
    database_session = get_db()
    permission = permission_error(database_session, load_current_user(), squad_id, "manage_dbu_sync")
    if permission:
        return permission
    season = season_for_squad(database_session, squad_id, season_id)
    if season is None:
        return error("season_not_found", 404)
    try:
        urls = dbu_urls({"dbuSeasonUrls": [body().get("url")]})
    except ValueError as exc:
        return error(str(exc))
    if not urls:
        return error("dbu_url_is_required")
    existing = database_session.scalar(
        select(DbuSource).where(DbuSource.season_id == season.id, DbuSource.url == urls[0])
    )
    if existing:
        return error("dbu_source_already_exists", 409)
    source = DbuSource(
        season_id=season.id,
        label=str(body().get("label", "DBU hold")).strip() or "DBU hold",
        url=urls[0],
    )
    database_session.add(source)
    if not season.dbu_url:
        season.dbu_url = source.url
    database_session.commit()
    return jsonify({"source": {"id": source.id, "label": source.label, "url": source.url}}), 201


@api.delete("/squads/<int:squad_id>/seasons/<int:season_id>/dbu-sources/<int:source_id>")
@user_required
def remove_dbu_source(squad_id, season_id, source_id):
    database_session = get_db()
    permission = permission_error(database_session, load_current_user(), squad_id, "manage_dbu_sync")
    if permission:
        return permission
    season = season_for_squad(database_session, squad_id, season_id)
    if season is None:
        return error("season_not_found", 404)
    source = database_session.scalar(
        select(DbuSource).where(DbuSource.id == source_id, DbuSource.season_id == season.id)
    )
    if source is None:
        return error("dbu_source_not_found", 404)
    removed_url = source.url
    database_session.delete(source)
    database_session.flush()
    if season.dbu_url == removed_url:
        replacement = database_session.scalar(
            select(DbuSource).where(DbuSource.season_id == season.id, DbuSource.active.is_(True)).order_by(DbuSource.id)
        )
        season.dbu_url = replacement.url if replacement else None
    database_session.commit()
    return jsonify({"ok": True})


@api.post("/squads/<int:squad_id>/matches")
@user_required
def create_manual_match(squad_id):
    database_session = get_db()
    permission = permission_error(database_session, load_current_user(), squad_id, "manage_matches")
    if permission:
        return permission
    squad, squad_error = require_squad(database_session, squad_id)
    if squad_error:
        return squad_error
    data = body()
    season = season_for_squad(database_session, squad_id, data.get("seasonId"))
    if season is None:
        return error("season_not_found", 404)
    home_club = str(data.get("homeClub", "")).strip()
    away_club = str(data.get("awayClub", "")).strip()
    if not home_club or not away_club:
        return error("home_and_away_club_are_required")
    try:
        match_date = parse_datetime(data.get("date"), "date", required=True)
    except ValueError as exc:
        return error(str(exc))
    if data.get("homeScore") in (None, "") or data.get("awayScore") in (None, ""):
        return error("both_scores_are_required")
    try:
        home_score = int(data["homeScore"])
        away_score = int(data["awayScore"])
    except (TypeError, ValueError):
        return error("scores_must_be_whole_numbers")
    if home_score < 0 or away_score < 0:
        return error("scores_cannot_be_negative")

    match = Match(
        season_id=season.id,
        dbu_id=None,
        match_date=match_date,
        home_club=home_club,
        away_club=away_club,
        home_score=home_score,
        away_score=away_score,
        status="needs_review",
    )
    database_session.add(match)
    database_session.flush()
    player_ids = data.get("playerIds") or []
    if player_ids:
        try:
            set_match_lineup(database_session, match, squad, player_ids, load_current_user().id)
        except (TypeError, ValueError) as exc:
            database_session.rollback()
            return error(str(exc))
    database_session.commit()
    return jsonify({"match": match_json(match, lineup_locked=bool(player_ids))}), 201


@api.delete("/squads/<int:squad_id>/matches/<int:match_id>")
@user_required
def delete_manual_match(squad_id, match_id):
    database_session = get_db()
    permission = permission_error(database_session, load_current_user(), squad_id, "manage_matches")
    if permission:
        return permission
    match, match_error = require_match(database_session, squad_id, match_id)
    if match_error:
        return match_error
    if match.dbu_id:
        return error("dbu_matches_are_managed_by_dbu", 409)
    database_session.execute(delete(FineCharge).where(FineCharge.match_id == match.id, FineCharge.source == "match"))
    database_session.delete(match)
    database_session.commit()
    return jsonify({"ok": True})


@api.put("/squads/<int:squad_id>/matches/<int:match_id>/lineup")
@user_required
def update_match_lineup(squad_id, match_id):
    database_session = get_db()
    permission = permission_error(database_session, load_current_user(), squad_id, "manage_matches")
    if permission:
        return permission
    squad, squad_error = require_squad(database_session, squad_id)
    if squad_error:
        return squad_error
    match, match_error = require_match(database_session, squad_id, match_id)
    if match_error:
        return match_error
    try:
        report = set_match_lineup(
            database_session,
            match,
            squad,
            body().get("playerIds", []),
            load_current_user().id,
        )
    except (TypeError, ValueError) as exc:
        database_session.rollback()
        return error(str(exc))
    database_session.commit()
    return jsonify({"ok": True, "report": report})


@api.delete("/squads/<int:squad_id>/matches/<int:match_id>/lineup")
@user_required
def reset_match_lineup(squad_id, match_id):
    database_session = get_db()
    permission = permission_error(database_session, load_current_user(), squad_id, "manage_matches")
    if permission:
        return permission
    squad, squad_error = require_squad(database_session, squad_id)
    if squad_error:
        return squad_error
    match, match_error = require_match(database_session, squad_id, match_id)
    if match_error:
        return match_error
    report = clear_match_lineup_lock(database_session, match, squad)
    database_session.commit()
    return jsonify({"ok": True, "report": report})


@api.put("/squads/<int:squad_id>/matches/<int:match_id>/washer")
@user_required
def update_match_washer(squad_id, match_id):
    database_session = get_db()
    permission = permission_error(database_session, load_current_user(), squad_id, "manage_matches")
    if permission:
        return permission
    match, match_error = require_match(database_session, squad_id, match_id)
    if match_error:
        return match_error
    washer_id = body().get("playerId")
    if washer_id in (None, ""):
        match.clothes_washer_id = None
    else:
        try:
            washer_id = int(washer_id)
        except (TypeError, ValueError):
            return error("player_not_found", 404)
        player = database_session.scalar(
            select(Player).where(Player.id == washer_id, Player.squad_id == squad_id, Player.active.is_(True))
        )
        if player is None:
            return error("player_not_found", 404)
        match.clothes_washer_id = player.id
    database_session.commit()
    return jsonify({"ok": True, "washerId": match.clothes_washer_id})


@api.post("/squads/<int:squad_id>/sync")
@user_required
def sync_squad_api(squad_id):
    database_session = get_db()
    permission = permission_error(database_session, load_current_user(), squad_id, "manage_dbu_sync")
    if permission:
        return permission
    squad, squad_error = require_squad(database_session, squad_id)
    if squad_error:
        return squad_error
    season_id = body().get("seasonId")
    if season_id is not None:
        season = season_for_squad(database_session, squad_id, season_id)
        if season is None:
            return error("season_not_found", 404)
        season_id = season.id
    report = sync_squad(database_session, squad, timeout=20, season_id=season_id)
    database_session.commit()
    return jsonify({"report": report})


@api.post("/squads/<int:squad_id>/sync/reset")
@user_required
def reset_squad_dbu_api(squad_id):
    database_session = get_db()
    permission = permission_error(database_session, load_current_user(), squad_id, "manage_dbu_sync")
    if permission:
        return permission
    squad, squad_error = require_squad(database_session, squad_id)
    if squad_error:
        return squad_error
    season = season_for_squad(database_session, squad_id, body().get("seasonId"))
    if season is None:
        return error("season_not_found", 404)
    report = reset_dbu_matches(database_session, squad, season.id, timeout=20)
    database_session.commit()
    return jsonify({"report": report})


@api.get("/squads/<int:squad_id>/permissions")
@user_required
def get_permissions(squad_id):
    database_session = get_db()
    permission = permission_error(database_session, load_current_user(), squad_id, "manage_permissions")
    if permission:
        return permission
    users = list(database_session.scalars(select(User).order_by(User.username)))
    rows = list(database_session.scalars(select(UserSquadPermission).where(UserSquadPermission.squad_id == squad_id)))
    grants = {(row.user_id, row.permission) for row in rows}
    return jsonify(
        {
            "permissions": PERMISSIONS,
            "users": [
                {
                    "id": user.id,
                    "username": user.username,
                    "playerId": user.player_id,
                    "isOwner": bool(user.is_owner),
                    "permissions": [permission_name for permission_name in PERMISSIONS if (user.id, permission_name) in grants],
                }
                for user in users
            ],
        }
    )


@api.put("/squads/<int:squad_id>/permissions/<int:user_id>")
@user_required
def update_permissions(squad_id, user_id):
    database_session = get_db()
    permission = permission_error(database_session, load_current_user(), squad_id, "manage_permissions")
    if permission:
        return permission
    user = database_session.get(User, user_id)
    if user is None:
        return error("user_not_found", 404)
    requested = set(body().get("permissions", []))
    invalid = requested - PERMISSIONS.keys()
    if invalid:
        return error("unknown_permission", unknown=list(invalid))
    database_session.execute(delete(UserSquadPermission).where(UserSquadPermission.squad_id == squad_id, UserSquadPermission.user_id == user_id))
    database_session.add_all(
        [UserSquadPermission(user_id=user_id, squad_id=squad_id, permission=item) for item in requested]
    )
    database_session.commit()
    return jsonify({"ok": True, "permissions": sorted(requested)})


@api.delete("/users/<int:user_id>")
@user_required
def delete_user_account(user_id):
    database_session = get_db()
    actor = load_current_user()
    if not actor.is_owner:
        return error("permission_denied", 403)
    user = database_session.get(User, user_id)
    if user is None:
        return error("user_not_found", 404)
    if user.is_owner:
        return error("owner_account_cannot_be_deleted", 409)
    database_session.delete(user)
    database_session.commit()
    return jsonify({"ok": True})


@api.post("/squads/<int:squad_id>/seasons")
@user_required
def create_season(squad_id):
    database_session = get_db()
    permission = permission_error(database_session, load_current_user(), squad_id, "manage_matches")
    if permission:
        return permission
    data = body()
    try:
        start_date = parse_date(data.get("startDate"), "startDate", required=True)
        end_date = parse_date(data.get("endDate"), "endDate")
        source_urls = dbu_urls(data)
    except ValueError as exc:
        return error(str(exc))
    if end_date and end_date < start_date:
        return error("end_date_must_be_after_start_date")
    season = Season(squad_id=squad_id, name=str(data.get("name", "")).strip(), dbu_url=source_urls[0] if source_urls else None, start_date=start_date, end_date=end_date)
    if not season.name:
        return error("season_name_is_required")
    database_session.add(season)
    database_session.flush()
    add_dbu_sources(database_session, season, source_urls)
    database_session.commit()
    return jsonify({"season": season_json(season)}), 201


@api.patch("/squads/<int:squad_id>/seasons/<int:season_id>")
@user_required
def update_season(squad_id, season_id):
    database_session = get_db()
    user = load_current_user()
    if not (
        has_permission(database_session, user, squad_id, "manage_matches")
        or has_permission(database_session, user, squad_id, "manage_finance")
    ):
        return error("permission_denied", 403)
    season = season_for_squad(database_session, squad_id, season_id)
    if season is None:
        return error("season_not_found", 404)
    data = body()
    try:
        start_date = parse_date(data.get("startDate"), "startDate", required=True)
        end_date = parse_date(data.get("endDate"), "endDate")
    except ValueError as exc:
        return error(str(exc))
    if end_date and end_date < start_date:
        return error("end_date_must_be_after_start_date")
    season.start_date = start_date
    season.end_date = end_date
    if str(data.get("name", "")).strip():
        season.name = str(data["name"]).strip()
    database_session.commit()
    return jsonify({"season": season_json(season)})

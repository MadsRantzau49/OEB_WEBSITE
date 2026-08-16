from datetime import date, datetime
from decimal import Decimal


def iso(value):
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def money(cents):
    return round((cents or 0) / 100, 2)


def user_json(user, permissions=None):
    return {
        "id": user.id,
        "username": user.username,
        "isOwner": bool(user.is_owner),
        "playerId": user.player_id,
        "permissions": permissions or [],
    }


def squad_json(squad, season=None):
    return {
        "id": squad.id,
        "name": squad.name,
        "slug": squad.slug,
        "dbuClubName": squad.dbu_club_name,
        "dbuSeasonUrl": squad.dbu_season_url,
        "currentSeason": season_json(season) if season else None,
    }


def season_json(season):
    return {
        "id": season.id,
        "squadId": season.squad_id,
        "name": season.name,
        "dbuUrl": season.dbu_url,
        "startDate": iso(season.start_date),
        "endDate": iso(season.end_date),
        "active": bool(season.active),
    }


def player_json(player, total_fines=0, total_paid=0, washes=0):
    return {
        "id": player.id,
        "squadId": player.squad_id,
        "name": player.dbu_name,
        "dbuName": player.dbu_name,
        "mobilePayName": player.mobilepay_name,
        "active": bool(player.active),
        "totalFines": money(total_fines),
        "totalPaid": money(total_paid),
        "balance": money(total_paid - total_fines),
        "washes": washes,
    }


def rule_json(rule):
    return {
        "id": rule.id,
        "name": rule.name,
        "description": rule.description,
        "amount": money(rule.amount_cents),
        "amountCents": rule.amount_cents,
        "type": rule.rule_type,
        "active": bool(rule.active),
    }


def charge_json(charge, player_name=None):
    return {
        "id": charge.id,
        "playerId": charge.player_id,
        "playerName": player_name,
        "seasonId": charge.season_id,
        "matchId": charge.match_id,
        "source": charge.source,
        "title": charge.title,
        "description": charge.description,
        "amount": money(charge.amount_cents),
        "amountCents": charge.amount_cents,
        "date": iso(charge.charge_date),
    }


def transaction_json(transaction, player_name=None):
    return {
        "id": transaction.id,
        "date": iso(transaction.transaction_date),
        "name": transaction.name,
        "type": transaction.transaction_type_name,
        "number": transaction.number,
        "message": transaction.message,
        "amount": money(transaction.amount_cents),
        "amountCents": transaction.amount_cents,
        "currency": transaction.currency,
        "transactionType": transaction.transaction_type,
        "allocationStatus": transaction.allocation_status,
        "allocatedPlayerId": transaction.allocated_player_id,
        "allocatedPlayerName": player_name,
    }


def match_json(match, participants=None, washer_name=None, lineup_locked=False):
    return {
        "id": match.id,
        "dbuId": match.dbu_id,
        "date": iso(match.match_date),
        "homeClub": match.home_club,
        "awayClub": match.away_club,
        "homeScore": match.home_score,
        "awayScore": match.away_score,
        "status": match.status,
        "syncError": match.sync_error,
        "lastSyncedAt": iso(match.last_synced_at),
        "washerId": match.clothes_washer_id,
        "washerName": washer_name,
        "lineupLocked": lineup_locked,
        "participants": participants or [],
    }


def decimal_to_cents(value):
    if value is None or value == "":
        return 0
    decimal_value = Decimal(str(value).replace(",", "."))
    return int(decimal_value * 100)

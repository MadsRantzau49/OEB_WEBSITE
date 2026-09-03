from datetime import date, datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Table,
    Text,
    UniqueConstraint,
)

from .db import Base


def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


fine_request_recipients = Table(
    "fine_request_recipients",
    Base.metadata,
    Column("request_id", ForeignKey("fine_requests.id", ondelete="CASCADE"), primary_key=True),
    Column("player_id", ForeignKey("players.id", ondelete="CASCADE"), primary_key=True),
)


class Club(Base):
    __tablename__ = "clubs"

    id = Column(Integer, primary_key=True)
    name = Column(String(120), nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)


class Squad(Base):
    __tablename__ = "squads"
    __table_args__ = (UniqueConstraint("club_id", "name", name="uq_squad_club_name"),)

    id = Column(Integer, primary_key=True)
    club_id = Column(Integer, ForeignKey("clubs.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    slug = Column(String(120), nullable=False, unique=True, index=True)
    dbu_club_name = Column(String(255), nullable=False)
    dbu_season_url = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    active = Column(Boolean, default=True, nullable=False)


class SquadPaymentSetting(Base):
    __tablename__ = "squad_payment_settings"

    squad_id = Column(Integer, ForeignKey("squads.id", ondelete="CASCADE"), primary_key=True)
    box_number = Column(String(20), nullable=True)
    payment_url = Column(String(500), nullable=True)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class Player(Base):
    __tablename__ = "players"
    __table_args__ = (UniqueConstraint("squad_id", "dbu_name", name="uq_player_squad_dbu_name"),)

    id = Column(Integer, primary_key=True)
    squad_id = Column(Integer, ForeignKey("squads.id", ondelete="CASCADE"), nullable=False, index=True)
    dbu_name = Column(String(255), nullable=False)
    mobilepay_name = Column(String(255), nullable=True)
    holdsport_name = Column(String(255), nullable=True)
    holdsport_auto_match = Column(Boolean, nullable=False, default=True)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(80), nullable=False, unique=True, index=True)
    password_hash = Column(String(255), nullable=False)
    player_id = Column(Integer, ForeignKey("players.id", ondelete="SET NULL"), nullable=True, unique=True)
    is_owner = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)


class UserSquadPermission(Base):
    __tablename__ = "user_squad_permissions"
    __table_args__ = (UniqueConstraint("user_id", "squad_id", "permission", name="uq_user_squad_permission"),)

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    squad_id = Column(Integer, ForeignKey("squads.id", ondelete="CASCADE"), nullable=False, index=True)
    permission = Column(String(80), nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)


class Season(Base):
    __tablename__ = "seasons"
    __table_args__ = (UniqueConstraint("squad_id", "name", name="uq_season_squad_name"),)

    id = Column(Integer, primary_key=True)
    squad_id = Column(Integer, ForeignKey("squads.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    dbu_url = Column(String(500), nullable=True)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)


class DbuSource(Base):
    __tablename__ = "dbu_sources"
    __table_args__ = (UniqueConstraint("season_id", "url", name="uq_dbu_source_season_url"),)

    id = Column(Integer, primary_key=True)
    season_id = Column(Integer, ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False, index=True)
    label = Column(String(120), nullable=False, default="DBU hold")
    url = Column(String(500), nullable=False)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)


class FineRule(Base):
    __tablename__ = "fine_rules"
    __table_args__ = (UniqueConstraint("squad_id", "name", name="uq_fine_rule_squad_name"),)

    id = Column(Integer, primary_key=True)
    squad_id = Column(Integer, ForeignKey("squads.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    description = Column(Text, nullable=False, default="")
    amount_cents = Column(Integer, nullable=False, default=0)
    per_minute_amount_cents = Column(Integer, nullable=False, default=0)
    lead_days = Column(Integer, nullable=False, default=0)
    lead_hours = Column(Integer, nullable=False, default=0)
    lead_minutes = Column(Integer, nullable=False, default=0)
    rule_type = Column(String(40), nullable=False, default="TEAM_FINE")
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class Match(Base):
    __tablename__ = "matches"
    __table_args__ = (UniqueConstraint("season_id", "dbu_id", name="uq_match_season_dbu_id"),)

    id = Column(Integer, primary_key=True)
    season_id = Column(Integer, ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False, index=True)
    dbu_id = Column(String(120), nullable=True)
    match_date = Column(DateTime, nullable=True)
    home_club = Column(String(255), nullable=True)
    away_club = Column(String(255), nullable=True)
    home_score = Column(Integer, nullable=True)
    away_score = Column(Integer, nullable=True)
    status = Column(String(30), nullable=False, default="pending")
    sync_error = Column(Text, nullable=True)
    last_synced_at = Column(DateTime, nullable=True)
    clothes_washer_id = Column(Integer, ForeignKey("players.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)


class MatchParticipant(Base):
    __tablename__ = "match_participants"
    __table_args__ = (
        UniqueConstraint("match_id", "source_name", name="uq_match_participant_source_name"),
        Index("ix_match_participant_match_status", "match_id", "status"),
    )

    id = Column(Integer, primary_key=True)
    match_id = Column(Integer, ForeignKey("matches.id", ondelete="CASCADE"), nullable=False, index=True)
    player_id = Column(Integer, ForeignKey("players.id", ondelete="SET NULL"), nullable=True, index=True)
    source_name = Column(String(255), nullable=False)
    status = Column(String(30), nullable=False, default="pending")
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class MatchLineupLock(Base):
    __tablename__ = "match_lineup_locks"

    match_id = Column(Integer, ForeignKey("matches.id", ondelete="CASCADE"), primary_key=True)
    locked_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class MatchLineupPlayer(Base):
    __tablename__ = "match_lineup_players"

    match_id = Column(Integer, ForeignKey("matches.id", ondelete="CASCADE"), primary_key=True)
    player_id = Column(Integer, ForeignKey("players.id", ondelete="CASCADE"), primary_key=True)


class FineRequest(Base):
    __tablename__ = "fine_requests"

    id = Column(Integer, primary_key=True)
    squad_id = Column(Integer, ForeignKey("squads.id", ondelete="CASCADE"), nullable=False, index=True)
    season_id = Column(Integer, ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False)
    requested_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    rule_id = Column(Integer, ForeignKey("fine_rules.id", ondelete="SET NULL"), nullable=True)
    title = Column(String(120), nullable=False)
    description = Column(Text, nullable=False, default="")
    amount_cents = Column(Integer, nullable=False, default=0)
    status = Column(String(30), nullable=False, default="pending", index=True)
    review_note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    reviewed_at = Column(DateTime, nullable=True)


class FineCharge(Base):
    __tablename__ = "fine_charges"
    __table_args__ = (
        UniqueConstraint("source_key", name="uq_fine_charge_source_key"),
        Index("ix_fine_charge_player_season", "player_id", "season_id"),
    )

    id = Column(Integer, primary_key=True)
    squad_id = Column(Integer, ForeignKey("squads.id", ondelete="CASCADE"), nullable=False, index=True)
    season_id = Column(Integer, ForeignKey("seasons.id", ondelete="CASCADE"), nullable=False)
    player_id = Column(Integer, ForeignKey("players.id", ondelete="CASCADE"), nullable=False, index=True)
    match_id = Column(Integer, ForeignKey("matches.id", ondelete="SET NULL"), nullable=True)
    fine_request_id = Column(Integer, ForeignKey("fine_requests.id", ondelete="SET NULL"), nullable=True)
    source = Column(String(40), nullable=False)
    source_key = Column(String(180), nullable=True)
    title = Column(String(120), nullable=False)
    description = Column(Text, nullable=False, default="")
    amount_cents = Column(Integer, nullable=False)
    charge_date = Column(Date, default=date.today, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)


class HoldsportSyncState(Base):
    __tablename__ = "holdsport_sync_states"

    squad_id = Column(Integer, ForeignKey("squads.id", ondelete="CASCADE"), primary_key=True)
    team_id = Column(String(80), nullable=True)
    last_checked_at = Column(DateTime, nullable=True)
    last_success_at = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)
    activities_count = Column(Integer, nullable=False, default=0)
    no_rsvp_count = Column(Integer, nullable=False, default=0)
    charges_created = Column(Integer, nullable=False, default=0)


class HoldsportActivity(Base):
    __tablename__ = "holdsport_activities"
    __table_args__ = (
        UniqueConstraint("squad_id", "holdsport_id", name="uq_holdsport_activity_squad_id"),
        Index("ix_holdsport_activity_squad_date", "squad_id", "activity_date"),
    )

    id = Column(Integer, primary_key=True)
    squad_id = Column(Integer, ForeignKey("squads.id", ondelete="CASCADE"), nullable=False, index=True)
    season_id = Column(Integer, ForeignKey("seasons.id", ondelete="SET NULL"), nullable=True)
    holdsport_id = Column(String(80), nullable=False)
    title = Column(String(500), nullable=False)
    activity_type = Column(String(30), nullable=False)
    activity_date = Column(Date, nullable=False)
    starts_at = Column(DateTime, nullable=False)
    feed_starts_at = Column(DateTime, nullable=True)
    url = Column(String(500), nullable=False)
    last_synced_at = Column(DateTime, default=utc_now, nullable=False)
    details_synced_at = Column(DateTime, nullable=True)
    deadline_captured_at = Column(DateTime, nullable=True)
    deadline_date = Column(Date, nullable=True)
    deadline_at = Column(DateTime, nullable=True)


class HoldsportPlayerMapping(Base):
    __tablename__ = "holdsport_player_mappings"
    __table_args__ = (
        UniqueConstraint("squad_id", "holdsport_user_id", name="uq_holdsport_mapping_squad_user"),
    )

    id = Column(Integer, primary_key=True)
    squad_id = Column(Integer, ForeignKey("squads.id", ondelete="CASCADE"), nullable=False, index=True)
    holdsport_user_id = Column(String(80), nullable=False)
    source_name = Column(String(255), nullable=False)
    player_id = Column(Integer, ForeignKey("players.id", ondelete="SET NULL"), nullable=True, index=True)
    manual = Column(Boolean, nullable=False, default=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)


class HoldsportParticipant(Base):
    __tablename__ = "holdsport_participants"
    __table_args__ = (
        UniqueConstraint("activity_id", "holdsport_user_id", name="uq_holdsport_participant_activity_user"),
    )

    id = Column(Integer, primary_key=True)
    activity_id = Column(Integer, ForeignKey("holdsport_activities.id", ondelete="CASCADE"), nullable=False, index=True)
    holdsport_user_id = Column(String(80), nullable=False)
    source_name = Column(String(255), nullable=False)
    player_id = Column(Integer, ForeignKey("players.id", ondelete="SET NULL"), nullable=True, index=True)
    is_coach = Column(Boolean, nullable=False, default=False)
    fine_processed_at = Column(DateTime, nullable=True)


class MobilePayImport(Base):
    __tablename__ = "mobilepay_imports"
    __table_args__ = (UniqueConstraint("squad_id", "file_sha256", name="uq_mobilepay_import_squad_hash"),)

    id = Column(Integer, primary_key=True)
    squad_id = Column(Integer, ForeignKey("squads.id", ondelete="CASCADE"), nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    file_sha256 = Column(String(64), nullable=False)
    raw_file = Column(LargeBinary, nullable=False)
    status = Column(String(30), nullable=False, default="processed")
    rows_count = Column(Integer, nullable=False, default=0)
    message = Column(Text, nullable=True)
    uploaded_at = Column(DateTime, default=utc_now, nullable=False)


class MobilePayDriveState(Base):
    __tablename__ = "mobilepay_drive_states"

    squad_id = Column(Integer, ForeignKey("squads.id", ondelete="CASCADE"), primary_key=True)
    folder_id = Column(String(255), nullable=False)
    last_checked_at = Column(DateTime, nullable=True)
    last_worker_check_at = Column(DateTime, nullable=True)
    last_success_at = Column(DateTime, nullable=True)
    last_error = Column(String(80), nullable=True)
    latest_file_id = Column(String(255), nullable=True)
    latest_filename = Column(String(255), nullable=True)
    latest_modified_time = Column(String(64), nullable=True)


class MobilePayTransaction(Base):
    __tablename__ = "mobilepay_transactions"
    __table_args__ = (
        UniqueConstraint("squad_id", "fingerprint", name="uq_mobilepay_transaction_fingerprint"),
        Index("ix_mobilepay_transaction_squad_type", "squad_id", "transaction_type"),
    )

    id = Column(Integer, primary_key=True)
    squad_id = Column(Integer, ForeignKey("squads.id", ondelete="CASCADE"), nullable=False, index=True)
    import_id = Column(Integer, ForeignKey("mobilepay_imports.id", ondelete="CASCADE"), nullable=False)
    fingerprint = Column(String(64), nullable=False)
    transaction_date = Column(DateTime, nullable=False)
    name = Column(String(255), nullable=True)
    transaction_type_name = Column(String(80), nullable=True)
    number = Column(String(80), nullable=True)
    message = Column(Text, nullable=True)
    amount_cents = Column(Integer, nullable=False)
    currency = Column(String(8), nullable=True)
    transaction_type = Column(String(30), nullable=False)
    allocation_status = Column(String(30), nullable=False, default="unmatched")
    allocated_player_id = Column(Integer, ForeignKey("players.id", ondelete="SET NULL"), nullable=True)


class HiddenMobilePayTransaction(Base):
    __tablename__ = "hidden_mobilepay_transactions"

    transaction_id = Column(Integer, ForeignKey("mobilepay_transactions.id", ondelete="CASCADE"), primary_key=True)
    hidden_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    hidden_at = Column(DateTime, default=utc_now, nullable=False)

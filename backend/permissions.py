from functools import wraps

from flask import jsonify
from sqlalchemy import and_, select

from .models import UserSquadPermission


PERMISSIONS = {
    "approve_fine_requests": "Approve fine requests",
    "issue_fines": "Issue fines directly",
    "manage_fine_rules": "Manage fine rules",
    "manage_finance": "Manage MobilePay imports",
    "manage_roster": "Manage players",
    "manage_matches": "Manage matches",
    "manage_dbu_sync": "Sync DBU data",
    "manage_permissions": "Manage squad permissions",
}


def has_permission(database_session, user, squad_id, permission):
    if user is None:
        return False
    if user.is_owner:
        return True
    return database_session.scalar(
        select(UserSquadPermission.id).where(
            and_(
                UserSquadPermission.user_id == user.id,
                UserSquadPermission.squad_id == squad_id,
                UserSquadPermission.permission == permission,
            )
        )
    ) is not None


def permission_error(database_session, user, squad_id, permission):
    if has_permission(database_session, user, squad_id, permission):
        return None
    return jsonify({"error": "permission_denied", "permission": permission}), 403


def squad_permission(permission):
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            from .security import load_current_user
            from .db import get_db

            user = load_current_user()
            if user is None:
                return jsonify({"error": "authentication_required"}), 401
            squad_id = kwargs.get("squad_id")
            error = permission_error(get_db(), user, squad_id, permission)
            if error:
                return error
            return view(*args, **kwargs)

        return wrapped

    return decorator

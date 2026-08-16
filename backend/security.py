from functools import wraps
import secrets

from flask import g, jsonify, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db
from .models import User


def hash_password(password):
    return generate_password_hash(str(password or "").casefold())


def verify_password(password_hash, password):
    normalized = str(password or "").casefold()
    # The second check keeps accounts created before passwords became
    # case-insensitive usable; successful logins are rehashed by the API.
    return check_password_hash(password_hash, normalized) or check_password_hash(password_hash, str(password or ""))


def set_login(user):
    session.clear()
    session.permanent = True
    session["user_id"] = user.id
    session["csrf_token"] = secrets.token_urlsafe(32)


def clear_login():
    session.clear()


def load_current_user():
    user_id = session.get("user_id")
    if not user_id:
        g.current_user = None
        return None
    user = get_db().get(User, user_id)
    if user is None or not user.is_active:
        clear_login()
        user = None
    g.current_user = user
    return user


def user_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user = load_current_user()
        if user is None:
            return jsonify({"error": "authentication_required"}), 401
        return view(*args, **kwargs)

    return wrapped


def csrf_required():
    if request.method not in {"POST", "PUT", "PATCH", "DELETE"}:
        return None
    if request.path.endswith("/auth/login") or request.path.endswith("/auth/register"):
        return None
    if request.path.endswith("/setup") and not session.get("user_id"):
        return None
    expected = session.get("csrf_token")
    supplied = request.headers.get("X-CSRF-Token")
    if not expected or not supplied or not secrets.compare_digest(expected, supplied):
        return jsonify({"error": "csrf_failed"}), 403
    return None

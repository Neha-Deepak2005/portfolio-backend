"""Tiny helpers: in-memory rate limiter + auth helpers."""
import time
from collections import defaultdict, deque
from functools import wraps

from flask import current_app, jsonify, request
from flask_jwt_extended import get_jwt_identity, verify_jwt_in_request

_hits = defaultdict(deque)


def client_ip():
    forwarded = request.headers.get("X-Forwarded-For", "")
    return (forwarded.split(",")[0].strip() if forwarded else request.remote_addr) or "unknown"


def rate_limit(limit, per_seconds, scope=None):
    """Allow `limit` requests per `per_seconds` for each client IP."""

    def decorator(fn):
        key_scope = scope or fn.__name__

        @wraps(fn)
        def wrapper(*args, **kwargs):
            if current_app.config.get("RATE_LIMIT_ENABLED", True):
                key = f"{key_scope}:{client_ip()}"
                now = time.time()
                window = _hits[key]
                while window and window[0] <= now - per_seconds:
                    window.popleft()
                if len(window) >= limit:
                    retry = int(per_seconds - (now - window[0])) + 1
                    resp = jsonify(error="Too many requests. Please try again later.",
                                   retry_after=retry)
                    resp.status_code = 429
                    resp.headers["Retry-After"] = str(retry)
                    return resp
                window.append(now)
            return fn(*args, **kwargs)

        return wrapper

    return decorator


def admin_required(fn):
    """Protect a route: valid access token of an active admin user."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        verify_jwt_in_request()
        from ..models import User  # local import avoids circular import
        from ..extensions import db

        user = db.session.get(User, int(get_jwt_identity()))
        if not user or not user.is_active or user.role != "admin":
            return jsonify(error="Admin access required"), 403
        return fn(*args, **kwargs)

    return wrapper


def is_admin_request():
    """True if the request carries a valid admin token (used for drafts)."""
    try:
        verify_jwt_in_request(optional=True)
        identity = get_jwt_identity()
    except Exception:
        return False
    if not identity:
        return False
    from ..models import User
    from ..extensions import db

    user = db.session.get(User, int(identity))
    return bool(user and user.is_active and user.role == "admin")

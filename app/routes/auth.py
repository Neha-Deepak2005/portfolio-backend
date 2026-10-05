"""
Authentication for the CMS admin panel (JWT).

    POST /api/auth/login      -> access + refresh token
    POST /api/auth/refresh    -> new access token (send refresh token as Bearer)
    GET  /api/auth/me         -> current admin
    PUT  /api/auth/password   -> change password
"""
from flask import Blueprint, jsonify, request
from flask_jwt_extended import (create_access_token, create_refresh_token,
                                get_jwt_identity, jwt_required)

from ..extensions import db
from ..models import User, utcnow
from ..utils.security import admin_required, rate_limit

bp = Blueprint("auth", __name__, url_prefix="/auth")


@bp.post("/login")
@rate_limit(10, 60, scope="login")
def login():
    body = request.get_json(silent=True) or {}
    email = (body.get("email") or "").strip().lower()
    password = body.get("password") or ""
    if not email or not password:
        return jsonify(error="Email and password are required"), 400

    user = User.query.filter_by(email=email).first()
    if not user or not user.check_password(password):
        return jsonify(error="Invalid email or password"), 401
    if not user.is_active:
        return jsonify(error="This account is disabled"), 403

    user.last_login = utcnow()
    db.session.commit()
    identity = str(user.id)
    claims = {"role": user.role, "name": user.name}
    return jsonify(
        access_token=create_access_token(identity=identity, additional_claims=claims),
        refresh_token=create_refresh_token(identity=identity),
        user=user.to_dict(),
    )


@bp.post("/refresh")
@jwt_required(refresh=True)
def refresh():
    user = db.session.get(User, int(get_jwt_identity()))
    if not user or not user.is_active:
        return jsonify(error="User not found"), 401
    token = create_access_token(identity=str(user.id),
                                additional_claims={"role": user.role, "name": user.name})
    return jsonify(access_token=token)


@bp.get("/me")
@admin_required
def me():
    user = db.session.get(User, int(get_jwt_identity()))
    return jsonify(user=user.to_dict())


@bp.put("/password")
@admin_required
def change_password():
    body = request.get_json(silent=True) or {}
    user = db.session.get(User, int(get_jwt_identity()))
    if not user.check_password(body.get("current_password") or ""):
        return jsonify(error="Current password is incorrect"), 400
    new = body.get("new_password") or ""
    if len(new) < 8:
        return jsonify(error="New password must be at least 8 characters"), 422
    user.set_password(new)
    db.session.commit()
    return jsonify(message="Password updated")

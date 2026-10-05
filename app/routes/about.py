"""
About / profile (a single record).

    GET /api/about   public
    PUT /api/about   admin
"""
from flask import Blueprint, jsonify, request

from ..extensions import db
from ..models import About
from ..utils.security import admin_required
from ..utils.validation import ValidationError, validate

bp = Blueprint("about", __name__)


def get_about():
    about = About.query.first()
    if about is None:
        about = About(name="Your Name", title="Developer", available_for_work=True)
        db.session.add(about)
        db.session.commit()
    return about


@bp.get("/about")
def read_about():
    return jsonify(data=get_about().to_dict())


@bp.put("/about")
@admin_required
def update_about():
    about = get_about()
    try:
        data = validate(About.FIELDS, request.get_json(silent=True) or {}, partial=True)
    except ValidationError as err:
        return jsonify(error="Validation failed", fields=err.errors), 422
    for key, value in data.items():
        setattr(about, key, value)
    db.session.commit()
    return jsonify(data=about.to_dict(), message="About section updated")

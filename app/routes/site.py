"""
Aggregated endpoints.

    GET /api/site        public – everything the portfolio home page needs in ONE request
    GET /api/dashboard   admin  – counts & recent activity for the CMS dashboard
    GET /api/health      public – health check for deployments
"""
from flask import Blueprint, jsonify
from sqlalchemy import text

from ..extensions import db
from ..models import Blog, Media, Message, Project
from ..utils.security import admin_required
from .about import get_about
from .content import RESOURCES, _ordering

bp = Blueprint("site", __name__)


def _published(model, limit=None):
    q = model.query.filter(model.status == "published").order_by(*_ordering(model))
    if limit:
        q = q.limit(limit)
    return [i.to_dict() for i in q.all()]


@bp.get("/site")
def site():
    data = {"about": get_about().to_dict()}
    for name, (model, _label, _cols) in RESOURCES.items():
        data[name.replace("-", "_")] = _published(model, limit=6 if model is Blog else None)
    return jsonify(data=data)


@bp.get("/dashboard")
@admin_required
def dashboard():
    counts = {}
    for name, (model, label, _cols) in RESOURCES.items():
        total = model.query.count()
        published = model.query.filter(model.status == "published").count()
        counts[name] = {"label": label, "total": total, "published": published,
                        "draft": total - published}
    counts["media"] = {"label": "Media", "total": Media.query.count()}
    counts["messages"] = {
        "label": "Messages",
        "total": Message.query.count(),
        "unread": Message.query.filter(Message.is_read.is_(False)).count(),
    }
    recent_messages = [m.to_dict() for m in
                       Message.query.order_by(Message.created_at.desc()).limit(5)]
    recent_content = []
    for model, kind in ((Project, "projects"), (Blog, "blogs")):
        for item in model.query.order_by(model.updated_at.desc()).limit(5):
            recent_content.append({"type": kind, "id": item.id, "title": item.title,
                                   "status": item.status,
                                   "updated_at": item.updated_at.isoformat() + "Z"})
    recent_content.sort(key=lambda r: r["updated_at"], reverse=True)
    return jsonify(counts=counts, recent_messages=recent_messages,
                   recent_content=recent_content[:6])


@bp.get("/health")
def health():
    try:
        db.session.execute(text("SELECT 1"))
        return jsonify(status="ok", database="connected")
    except Exception as exc:  # pragma: no cover
        return jsonify(status="error", database=str(exc)), 500

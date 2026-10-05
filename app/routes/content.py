"""
Generic CRUD API for every collection content type.

    GET    /api/<resource>                 list  (public: published only)
    GET    /api/<resource>/<id-or-slug>    detail
    POST   /api/<resource>                 create          (admin)
    PUT    /api/<resource>/<id>            update          (admin)
    DELETE /api/<resource>/<id>            delete          (admin)
    PATCH  /api/<resource>/<id>/status     publish/draft   (admin)
    POST   /api/<resource>/reorder         save ordering   (admin)
"""
from flask import Blueprint, abort, jsonify, request
from sqlalchemy import or_

from ..extensions import db
from ..models import (STATUS_CHOICES, Blog, Education, Experience, Project, Service,
                      Skill, SocialLink, Testimonial)
from ..utils.security import admin_required, is_admin_request
from ..utils.validation import ValidationError, slugify, validate

# URL name -> (Model, human label, searchable columns)
RESOURCES = {
    "skills": (Skill, "Skill", ["name", "category"]),
    "projects": (Project, "Project", ["title", "summary", "tech_stack", "category"]),
    "blogs": (Blog, "Blog post", ["title", "excerpt", "tags"]),
    "experience": (Experience, "Experience", ["company", "position"]),
    "education": (Education, "Education", ["institution", "degree", "field"]),
    "testimonials": (Testimonial, "Testimonial", ["name", "company", "content"]),
    "services": (Service, "Service", ["title", "description"]),
    "social-links": (SocialLink, "Social link", ["platform", "url"]),
}

bp = Blueprint("content", __name__)
RES_CONVERTER = "any(" + ",".join(f'"{r}"' for r in RESOURCES) + "):resource"


def _model(resource):
    return RESOURCES[resource][0]


def _ordering(model):
    if model is Blog:
        return [Blog.published_at.desc(), Blog.created_at.desc()]
    if model is Experience:
        return [Experience.display_order.asc(), Experience.start_date.desc()]
    if model is Education:
        return [Education.display_order.asc(), Education.end_year.desc()]
    return [model.display_order.asc(), model.id.asc()]


def _unique_slug(model, base, exclude_id=None):
    slug, n = base, 2
    while True:
        q = model.query.filter(model.slug == slug)
        if exclude_id:
            q = q.filter(model.id != exclude_id)
        if not q.first():
            return slug
        slug = f"{base}-{n}"
        n += 1


def _apply(model, obj, data):
    for key, value in data.items():
        setattr(obj, key, value)
    if "slug" in model.FIELDS:
        source = model.FIELDS["slug"]["source"]
        base = slugify(obj.slug or getattr(obj, source))
        obj.slug = _unique_slug(model, base, exclude_id=obj.id)


def _get_or_404(model, key):
    obj = None
    if str(key).isdigit():
        obj = db.session.get(model, int(key))
    if obj is None and "slug" in model.FIELDS:
        obj = model.query.filter_by(slug=str(key)).first()
    if obj is None:
        abort(404, description="Not found")
    return obj


@bp.get(f"/<{RES_CONVERTER}>")
def list_items(resource):
    model = _model(resource)
    admin = is_admin_request()
    q = model.query

    status = request.args.get("status")
    if not admin:
        q = q.filter(model.status == "published")
    elif status in STATUS_CHOICES:
        q = q.filter(model.status == status)

    search = (request.args.get("search") or "").strip()
    if search:
        cols = RESOURCES[resource][2]
        q = q.filter(or_(*[getattr(model, c).ilike(f"%{search}%") for c in cols]))

    if request.args.get("featured") in ("1", "true") and hasattr(model, "featured"):
        q = q.filter(model.featured.is_(True))
    category = request.args.get("category")
    if category and hasattr(model, "category"):
        q = q.filter(model.category == category)
    tag = request.args.get("tag")
    if tag and hasattr(model, "tags"):
        q = q.filter(model.tags.ilike(f"%{tag}%"))

    q = q.order_by(*_ordering(model))
    total = q.count()

    limit = request.args.get("limit", type=int)
    page = request.args.get("page", type=int)
    per_page = min(request.args.get("per_page", 10, type=int), 100)
    if page:
        items = q.offset((page - 1) * per_page).limit(per_page).all()
        pages = max(1, -(-total // per_page))
        return jsonify(data=[i.to_dict() for i in items], total=total, page=page,
                       per_page=per_page, pages=pages)
    if limit:
        q = q.limit(limit)
    return jsonify(data=[i.to_dict() for i in q.all()], total=total)


@bp.get(f"/<{RES_CONVERTER}>/<key>")
def get_item(resource, key):
    model = _model(resource)
    obj = _get_or_404(model, key)
    if obj.status != "published" and not is_admin_request():
        abort(404, description="Not found")
    return jsonify(data=obj.to_dict())


@bp.post(f"/<{RES_CONVERTER}>")
@admin_required
def create_item(resource):
    model = _model(resource)
    try:
        data = validate(model.FIELDS, request.get_json(silent=True) or {})
    except ValidationError as err:
        return jsonify(error="Validation failed", fields=err.errors), 422
    obj = model()
    _apply(model, obj, data)
    db.session.add(obj)
    db.session.commit()
    return jsonify(data=obj.to_dict(), message=f"{RESOURCES[resource][1]} created"), 201


@bp.put(f"/<{RES_CONVERTER}>/<int:item_id>")
@admin_required
def update_item(resource, item_id):
    model = _model(resource)
    obj = _get_or_404(model, item_id)
    try:
        data = validate(model.FIELDS, request.get_json(silent=True) or {}, partial=True)
    except ValidationError as err:
        return jsonify(error="Validation failed", fields=err.errors), 422
    _apply(model, obj, data)
    db.session.commit()
    return jsonify(data=obj.to_dict(), message=f"{RESOURCES[resource][1]} updated")


@bp.delete(f"/<{RES_CONVERTER}>/<int:item_id>")
@admin_required
def delete_item(resource, item_id):
    model = _model(resource)
    obj = _get_or_404(model, item_id)
    db.session.delete(obj)
    db.session.commit()
    return jsonify(message=f"{RESOURCES[resource][1]} deleted")


@bp.patch(f"/<{RES_CONVERTER}>/<int:item_id>/status")
@admin_required
def set_status(resource, item_id):
    model = _model(resource)
    obj = _get_or_404(model, item_id)
    status = (request.get_json(silent=True) or {}).get("status")
    if status not in STATUS_CHOICES:
        return jsonify(error="status must be 'draft' or 'published'"), 422
    obj.status = status
    if model is Blog and status == "published" and not obj.published_at:
        from datetime import date
        obj.published_at = date.today().isoformat()
    db.session.commit()
    return jsonify(data=obj.to_dict(), message=f"Marked as {status}")


@bp.post(f"/<{RES_CONVERTER}>/reorder")
@admin_required
def reorder(resource):
    model = _model(resource)
    if not hasattr(model, "display_order"):
        return jsonify(error="This content type cannot be reordered"), 400
    ids = (request.get_json(silent=True) or {}).get("ids") or []
    for index, item_id in enumerate(ids):
        obj = db.session.get(model, int(item_id))
        if obj:
            obj.display_order = index
    db.session.commit()
    return jsonify(message="Order saved")

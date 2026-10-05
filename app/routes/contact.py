"""
Contact form + admin inbox.

    POST   /api/contact               public – save message + send email
    GET    /api/messages              admin  – list (?unread=1, ?search=)
    PATCH  /api/messages/<id>         admin  – mark read / unread
    DELETE /api/messages/<id>         admin
"""
from flask import Blueprint, jsonify, request
from sqlalchemy import or_

from ..extensions import db
from ..models import Message
from ..utils.email import send_email
from ..utils.security import admin_required, client_ip, rate_limit
from ..utils.validation import EMAIL_RE, strip_tags

bp = Blueprint("contact", __name__)


@bp.post("/contact")
@rate_limit(5, 600, scope="contact")
def submit_contact():
    body = request.get_json(silent=True) or {}

    # Honeypot field: real users never fill it, bots usually do.
    if body.get("website"):
        return jsonify(message="Thanks! Your message has been sent."), 201

    name = strip_tags((body.get("name") or "").strip())[:120]
    email = (body.get("email") or "").strip().lower()[:255]
    subject = strip_tags((body.get("subject") or "").strip())[:200]
    message = strip_tags((body.get("message") or "").strip())[:5000]

    errors = {}
    if len(name) < 2:
        errors["name"] = "Please enter your name"
    if not EMAIL_RE.match(email):
        errors["email"] = "Please enter a valid email"
    if len(message) < 10:
        errors["message"] = "Message should be at least 10 characters"
    if errors:
        return jsonify(error="Validation failed", fields=errors), 422

    msg = Message(name=name, email=email, subject=subject or None,
                  message=message, ip_address=client_ip())
    db.session.add(msg)
    db.session.commit()

    sent = send_email(
        subject=f"New portfolio message: {subject or 'No subject'}",
        body=f"From: {name} <{email}>\nSubject: {subject or '-'}\n\n{message}",
        reply_to=email,
    )
    msg.email_sent = sent
    db.session.commit()
    return jsonify(message="Thanks! Your message has been sent.", id=msg.id), 201


@bp.get("/messages")
@admin_required
def list_messages():
    q = Message.query
    if request.args.get("unread") in ("1", "true"):
        q = q.filter(Message.is_read.is_(False))
    search = (request.args.get("search") or "").strip()
    if search:
        like = f"%{search}%"
        q = q.filter(or_(Message.name.ilike(like), Message.email.ilike(like),
                         Message.subject.ilike(like), Message.message.ilike(like)))
    items = q.order_by(Message.created_at.desc()).all()
    unread = Message.query.filter(Message.is_read.is_(False)).count()
    return jsonify(data=[m.to_dict() for m in items], total=len(items), unread=unread)


@bp.patch("/messages/<int:message_id>")
@admin_required
def update_message(message_id):
    msg = db.get_or_404(Message, message_id)
    body = request.get_json(silent=True) or {}
    msg.is_read = bool(body.get("is_read", True))
    db.session.commit()
    return jsonify(data=msg.to_dict())


@bp.delete("/messages/<int:message_id>")
@admin_required
def delete_message(message_id):
    msg = db.get_or_404(Message, message_id)
    db.session.delete(msg)
    db.session.commit()
    return jsonify(message="Message deleted")

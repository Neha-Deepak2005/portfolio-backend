"""
Media library & uploads.

    POST   /api/upload/image     upload an image (multipart, field "file")   admin
    POST   /api/upload/file      upload a PDF (e.g. resume)                  admin
    GET    /api/media            list media                                  admin
    PUT    /api/media/<id>       update alt text                             admin
    DELETE /api/media/<id>       delete file + record                        admin
    GET    /uploads/<filename>   serve uploaded file                         public
"""
import os
import uuid

from flask import Blueprint, current_app, jsonify, request, send_from_directory
from flask_jwt_extended import get_jwt_identity
from PIL import Image, UnidentifiedImageError

from ..extensions import db
from ..models import Media
from ..utils.security import admin_required

bp = Blueprint("media", __name__)
files_bp = Blueprint("files", __name__)

IMAGE_EXTS = {"jpg", "jpeg", "png", "gif", "webp"}
FILE_EXTS = {"pdf"}
MAX_IMAGE_SIDE = 1920  # images larger than this are resized (image optimisation)


def _ext(filename):
    return filename.rsplit(".", 1)[-1].lower() if "." in filename else ""


def _save_upload(kind):
    file = request.files.get("file")
    if not file or not file.filename:
        return None, (jsonify(error="No file uploaded. Use form field 'file'."), 400)

    ext = _ext(file.filename)
    allowed = IMAGE_EXTS if kind == "image" else FILE_EXTS
    if ext not in allowed:
        return None, (jsonify(error=f"File type not allowed. Allowed: {', '.join(sorted(allowed))}"), 400)

    max_bytes = current_app.config["MAX_UPLOAD_MB"] * 1024 * 1024
    file.stream.seek(0, os.SEEK_END)
    size = file.stream.tell()
    file.stream.seek(0)
    if size > max_bytes:
        return None, (jsonify(error=f"File too large. Max {current_app.config['MAX_UPLOAD_MB']} MB"), 413)

    folder = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(folder, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.{ext}"
    path = os.path.join(folder, filename)
    width = height = None

    if kind == "image":
        try:
            img = Image.open(file.stream)
            img.verify()                     # reject files that only pretend to be images
            file.stream.seek(0)
            img = Image.open(file.stream)
        except (UnidentifiedImageError, OSError, SyntaxError):
            return None, (jsonify(error="The uploaded file is not a valid image"), 400)

        if ext == "gif":
            file.stream.seek(0)
            file.save(path)
        else:
            if max(img.size) > MAX_IMAGE_SIDE:
                img.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
            if ext in ("jpg", "jpeg") and img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            save_kwargs = {"optimize": True}
            if ext in ("jpg", "jpeg", "webp"):
                save_kwargs["quality"] = 85
            img.save(path, **save_kwargs)
        width, height = img.size
    else:
        head = file.stream.read(5)
        file.stream.seek(0)
        if head != b"%PDF-":
            return None, (jsonify(error="The uploaded file is not a valid PDF"), 400)
        file.save(path)

    media = Media(
        filename=filename,
        original_name=file.filename[:255],
        mime_type=file.mimetype,
        size=os.path.getsize(path),
        width=width,
        height=height,
        alt_text=request.form.get("alt_text") or None,
        uploaded_by=int(get_jwt_identity()),
    )
    db.session.add(media)
    db.session.commit()
    return media, None


@bp.post("/upload/image")
@admin_required
def upload_image():
    media, error = _save_upload("image")
    if error:
        return error
    return jsonify(data=media.to_dict(), url=media.url, message="Image uploaded"), 201


@bp.post("/upload/file")
@admin_required
def upload_file():
    media, error = _save_upload("file")
    if error:
        return error
    return jsonify(data=media.to_dict(), url=media.url, message="File uploaded"), 201


@bp.get("/media")
@admin_required
def list_media():
    items = Media.query.order_by(Media.created_at.desc()).all()
    return jsonify(data=[m.to_dict() for m in items], total=len(items))


@bp.put("/media/<int:media_id>")
@admin_required
def update_media(media_id):
    media = db.get_or_404(Media, media_id)
    media.alt_text = ((request.get_json(silent=True) or {}).get("alt_text") or "")[:255] or None
    db.session.commit()
    return jsonify(data=media.to_dict(), message="Media updated")


@bp.delete("/media/<int:media_id>")
@admin_required
def delete_media(media_id):
    media = db.get_or_404(Media, media_id)
    path = os.path.join(current_app.config["UPLOAD_FOLDER"], media.filename)
    if os.path.exists(path):
        os.remove(path)
    db.session.delete(media)
    db.session.commit()
    return jsonify(message="Media deleted")


@files_bp.get("/uploads/<path:filename>")
def serve_upload(filename):
    resp = send_from_directory(current_app.config["UPLOAD_FOLDER"], filename)
    resp.headers["Cache-Control"] = "public, max-age=604800"
    return resp

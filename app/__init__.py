"""Portfolio CMS – Flask application factory."""
import os

from flask import Flask, jsonify
from werkzeug.exceptions import HTTPException

from .config import Config
from .extensions import cors, db, jwt


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)
    jwt.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]},
                                  r"/uploads/*": {"origins": "*"}})

    from .routes import about, auth, contact, content, docs, media, site

    for module in (auth, about, content, media, contact, site, docs):
        app.register_blueprint(module.bp, url_prefix="/api" + (module.bp.url_prefix or ""))
    app.register_blueprint(media.files_bp)

    _register_error_handlers(app)
    _register_security_headers(app)

    with app.app_context():
        from . import models  # noqa: F401  (make sure tables are known)
        from sqlalchemy.exc import OperationalError
        try:
            db.create_all()
            # Lightweight migration for databases created by an earlier version
            from sqlalchemy import text
            db.session.execute(text("ALTER TABLE media ADD COLUMN IF NOT EXISTS data BYTEA"))
            db.session.commit()
        except OperationalError as exc:
            raise SystemExit(
                "\n❌ Cannot connect to PostgreSQL.\n"
                "   1. Make sure PostgreSQL is installed and running\n"
                "   2. Check DATABASE_URL in portfolio-backend/.env (user / password / db name)\n"
                "   3. Run  python seed.py  once – it creates the database for you\n\n"
                f"   Details: {str(exc.orig).strip()}\n") from None

    @app.get("/")
    def index():
        return jsonify(name="Portfolio CMS API", docs="/api/docs", health="/api/health")

    return app


def _register_error_handlers(app):
    @app.errorhandler(HTTPException)
    def http_error(err):
        return jsonify(error=err.description or err.name), err.code

    @app.errorhandler(413)
    def too_large(_err):
        return jsonify(error=f"File too large. Max {app.config['MAX_UPLOAD_MB']} MB"), 413

    @app.errorhandler(Exception)
    def server_error(err):  # pragma: no cover
        app.logger.exception(err)
        db.session.rollback()
        return jsonify(error="Internal server error"), 500

    @jwt.expired_token_loader
    def expired(_h, _p):
        return jsonify(error="Token has expired", code="token_expired"), 401

    @jwt.invalid_token_loader
    def invalid(reason):
        return jsonify(error=f"Invalid token: {reason}"), 401

    @jwt.unauthorized_loader
    def missing(reason):
        return jsonify(error="Authentication required"), 401


def _register_security_headers(app):
    @app.after_request
    def headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        resp.headers.setdefault("Cross-Origin-Resource-Policy", "cross-origin")
        return resp

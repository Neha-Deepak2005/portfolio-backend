import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _bool(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


DEFAULT_DB = "postgresql://postgres:postgres@localhost:5432/portfolio_cms"
DEFAULT_TEST_DB = "postgresql://postgres:postgres@localhost:5432/portfolio_cms_test"


def postgres_url(env_name, default):
    """This project uses PostgreSQL only."""
    url = os.getenv(env_name, default).strip()
    # Render/Heroku give "postgres://" – SQLAlchemy needs "postgresql://"
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    if not url.startswith("postgresql"):
        raise RuntimeError(
            f"{env_name} must be a PostgreSQL URL, e.g. {default} (got: {url!r})")
    # Always use the modern psycopg (v3) driver
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
    SQLALCHEMY_DATABASE_URI = postgres_url("DATABASE_URL", DEFAULT_DB)
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_SORT_KEYS = False

    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-jwt-secret-change-me-please-32b")
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=int(os.getenv("JWT_ACCESS_MINUTES", 30)))
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=int(os.getenv("JWT_REFRESH_DAYS", 7)))

    CORS_ORIGINS = [o.strip() for o in os.getenv(
        "CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",") if o.strip()]

    UPLOAD_FOLDER = str(BASE_DIR / os.getenv("UPLOAD_FOLDER", "uploads"))
    MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", 5))
    # A bit of head-room over the file limit for the multipart envelope
    MAX_CONTENT_LENGTH = (MAX_UPLOAD_MB + 1) * 1024 * 1024
    PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")

    SMTP_HOST = os.getenv("SMTP_HOST", "")
    SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
    SMTP_USER = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    SMTP_USE_TLS = _bool(os.getenv("SMTP_USE_TLS"), True)
    MAIL_FROM = os.getenv("MAIL_FROM", "")
    MAIL_TO = os.getenv("MAIL_TO", "")

    RATE_LIMIT_ENABLED = True


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = postgres_url("TEST_DATABASE_URL", DEFAULT_TEST_DB)
    RATE_LIMIT_ENABLED = False
    SMTP_HOST = ""

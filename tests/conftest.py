"""
Tests run against a separate PostgreSQL database (TEST_DATABASE_URL in .env,
default: portfolio_cms_test). It is created automatically if missing.
"""
import os
import shutil
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402
from app.config import TestConfig  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import User  # noqa: E402
from seed import ensure_database  # noqa: E402


@pytest.fixture(scope="session")
def _database():
    ensure_database(TestConfig.SQLALCHEMY_DATABASE_URI)


@pytest.fixture()
def app(_database):
    upload_dir = tempfile.mkdtemp()

    class Cfg(TestConfig):
        UPLOAD_FOLDER = upload_dir

    app = create_app(Cfg)
    with app.app_context():
        db.drop_all()
        db.create_all()
        admin = User(name="Admin", email="admin@test.com", role="admin")
        admin.set_password("Secret123")
        db.session.add(admin)
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()
    shutil.rmtree(upload_dir, ignore_errors=True)


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def tokens(client):
    res = client.post("/api/auth/login", json={"email": "admin@test.com", "password": "Secret123"})
    assert res.status_code == 200
    return res.get_json()


@pytest.fixture()
def auth(tokens):
    return {"Authorization": f"Bearer {tokens['access_token']}"}

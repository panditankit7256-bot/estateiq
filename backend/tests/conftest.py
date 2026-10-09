import os, tempfile
_tmp = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db"
os.environ["FIXED_NOW"] = "2026-10-09T14:00:00"
os.environ["SEED_DAYS"] = "90"
import pytest
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def token(client, user, pw):
    return {"Authorization": "Bearer " + client.post("/api/v1/auth/login", json={"username": user, "password": pw}).json()["token"]}


@pytest.fixture(scope="session")
def admin(client): return token(client, "admin", "admin123")
@pytest.fixture(scope="session")
def ops(client): return token(client, "ops", "ops123")
@pytest.fixture(scope="session")
def green(client): return token(client, "green", "green123")

import unittest
import os
import secrets

from fastapi.testclient import TestClient

import tempfile
from pathlib import Path
from unittest.mock import patch

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

import database
from database import get_db
from main import app
from models import User
from security import password_hash
from settings import get_settings
from schemas import ExpenseOutput
from pydantic import ValidationError


TEST_PASSWORD = "test-only-long-password"
TEST_HASH = password_hash.hash(TEST_PASSWORD)


class ExpenseFixture(unittest.TestCase):
    def setUp(self):
        env = patch.dict(os.environ, {"JWT_SECRET": secrets.token_hex(32), "APP_ORIGIN": "https://testserver"})
        env.start()
        self.addCleanup(env.stop)
        get_settings.cache_clear()
        self.addCleanup(get_settings.cache_clear)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.url = "sqlite:///" + (Path(self.temp.name) / "test.db").as_posix()
        self.engine = create_engine(self.url, connect_args={"check_same_thread": False})
        self.addCleanup(self.engine.dispose)
        self.factory = sessionmaker(bind=self.engine)
        self.config = Config(str(Path(__file__).parent / "alembic.ini"))
        self.engine_patch = patch.object(database, "engine", self.engine)
        self.engine_patch.start()
        self.addCleanup(self.engine_patch.stop)
        command.upgrade(self.config, "head")

        def override_db():
            with self.factory() as session:
                yield session

        app.dependency_overrides[get_db] = override_db
        self.addCleanup(app.dependency_overrides.clear)
        self.client = TestClient(app, base_url="https://testserver")
        self.addCleanup(self.client.close)
        self.seed_and_login()

    def seed_and_login(self):
        with self.factory() as db:
            db.add(User(username="alice", password_hash=TEST_HASH))
            db.commit()
        csrf = self.client.get("/auth/csrf").json()["csrf_token"]
        self.client.headers.update({"Origin": "https://testserver", "X-CSRF-Token": csrf})
        response = self.client.post("/auth/login", json={"username": "alice", "password": TEST_PASSWORD})
        self.assertEqual(response.status_code, 200)
        self.client.headers["X-CSRF-Token"] = response.json()["csrf_token"]

    def create(self, description="Lunch", amount=12.5):
        response = self.client.post(
            "/expenses", json={"description": description, "amount": amount}
        )
        self.assertEqual(response.status_code, 201)
        return response.json()

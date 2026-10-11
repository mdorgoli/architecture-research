import time
from concurrent.futures import ThreadPoolExecutor

import jwt
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from main import app
from models import AuthSession, User
from security import ACCESS_COOKIE, REFRESH_COOKIE, CSRF_COOKIE, digest, issue_token
from settings import get_settings
from test_support import ExpenseFixture, TEST_HASH, TEST_PASSWORD


class AuthTests(ExpenseFixture):
    def anonymous(self, https=True):
        client = TestClient(app, base_url="https://testserver" if https else "http://testserver")
        self.addCleanup(client.close)
        return client

    def clone(self):
        client = self.anonymous()
        for cookie in self.client.cookies.jar:
            client.cookies.set(cookie.name, cookie.value, domain=cookie.domain, path=cookie.path)
        client.headers.update({"Origin": "https://testserver", "X-CSRF-Token": self.client.cookies[CSRF_COOKIE]})
        return client

    def replace_cookie(self, client, name, value):
        client.cookies.delete(name)
        client.cookies.set(name, value, domain="testserver.local", path="/")

    def test_cookie_attributes_and_token_lifetimes(self):
        response = self.client.post("/auth/login", json={"username": "alice", "password": TEST_PASSWORD})
        headers = response.headers.get_list("set-cookie")
        self.assertEqual(len(headers), 3)
        for name in (ACCESS_COOKIE, REFRESH_COOKIE):
            header = next(h for h in headers if h.startswith(name + "="))
            for attribute in ("HttpOnly", "Secure", "SameSite=strict", "Path=/"):
                self.assertIn(attribute, header)
            self.assertNotIn("Domain=", header)
        self.assertNotIn("HttpOnly", next(h for h in headers if h.startswith(CSRF_COOKIE)))
        settings = get_settings()
        access = jwt.decode(self.client.cookies[ACCESS_COOKIE], settings.secret, algorithms=["HS256"], audience=settings.audience)
        refresh = jwt.decode(self.client.cookies[REFRESH_COOKIE], settings.secret, algorithms=["HS256"], audience=settings.audience)
        self.assertEqual(access["exp"] - access["iat"], 900)
        self.assertEqual(refresh["exp"] - refresh["iat"], 604800)
        self.assertNotIn("access_token", response.json())
        self.assertEqual(response.headers["cache-control"], "no-store")
        with self.factory() as db:
            session = db.get(AuthSession, refresh["sid"])
            self.assertEqual(session.refresh_hash, digest(self.client.cookies[REFRESH_COOKIE]))
            self.assertNotEqual(session.refresh_hash, self.client.cookies[REFRESH_COOKIE])

    def test_missing_login_and_wrong_password(self):
        client = self.anonymous()
        self.assertEqual(client.get("/expenses").status_code, 401)
        csrf = client.get("/auth/csrf").json()["csrf_token"]
        client.headers.update({"Origin": "https://testserver", "X-CSRF-Token": csrf})
        for username in ("alice", "nobody"):
            response = client.post("/auth/login", json={"username": username, "password": "wrong"})
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.json()["detail"], "invalid_credentials")

    def test_csrf_origin_header_and_session_binding(self):
        for headers in ({"Origin": "https://evil.example"}, {"Origin": "null"}, {"X-CSRF-Token": "bad"}, {"Origin": ""}):
            for path, payload in (("/expenses", {"description": "bad", "amount": 1}), ("/auth/refresh", None), ("/auth/logout", None)):
                self.assertEqual(self.client.post(path, json=payload, headers=headers).status_code, 403)
        client = self.anonymous()
        self.assertEqual(client.post("/auth/login", json={"username": "alice", "password": TEST_PASSWORD}).status_code, 403)
        foreign_csrf = client.get("/auth/csrf").json()["csrf_token"]
        self.replace_cookie(self.client, CSRF_COOKIE, foreign_csrf)
        self.client.headers["X-CSRF-Token"] = foreign_csrf
        self.assertEqual(self.client.post("/auth/refresh").status_code, 403)

    def test_refresh_rotates_and_replay_revokes_session(self):
        old = self.clone()
        old_refresh = self.client.cookies[REFRESH_COOKIE]
        response = self.client.post("/auth/refresh")
        self.assertEqual(response.status_code, 200)
        self.assertNotEqual(self.client.cookies[REFRESH_COOKIE], old_refresh)
        self.assertEqual(self.client.get("/auth/me").status_code, 200)
        replay = old.post("/auth/refresh")
        self.assertEqual(replay.status_code, 401)
        self.assertEqual(replay.json()["detail"], "refresh_reused")
        self.assertEqual(self.client.get("/auth/me").status_code, 401)
        self.assertEqual(self.client.post("/auth/refresh").status_code, 401)

    def test_concurrent_refresh_only_one_succeeds(self):
        clients = [self.clone(), self.clone()]
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda client: client.post("/auth/refresh").status_code, clients))
        self.assertEqual(sorted(results), [200, 401])
        self.assertEqual(self.client.get("/auth/me").status_code, 401)

    def test_expired_access_can_renew_without_login(self):
        claims = jwt.decode(self.client.cookies[ACCESS_COOKIE], options={"verify_signature": False})
        expired = issue_token("access", claims["sub"], claims["sid"], int(time.time()) - 1)
        self.replace_cookie(self.client, ACCESS_COOKIE, expired)
        response = self.client.get("/expenses")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "token_expired")
        self.assertEqual(self.client.post("/auth/refresh").status_code, 200)
        self.assertEqual(self.client.get("/expenses").status_code, 200)

    def test_invalid_token_claims_and_wrong_token_type(self):
        original = self.client.cookies[ACCESS_COOKIE]
        claims = jwt.decode(original, options={"verify_signature": False})
        bad_tokens = ["not.a.jwt", self.client.cookies[REFRESH_COOKIE]]
        for field, value in (("aud", "wrong"), ("iss", "wrong"), ("sub", "not-numeric"), ("exp", "bad")):
            bad_tokens.append(jwt.encode({**claims, field: value}, get_settings().secret, algorithm="HS256"))
        missing = dict(claims)
        del missing["exp"]
        bad_tokens.append(jwt.encode(missing, get_settings().secret, algorithm="HS256"))
        bad_tokens.append(jwt.encode(claims, "wrong-key-" * 8, algorithm="HS256"))
        bad_tokens.append(jwt.encode(claims, get_settings().secret, algorithm="HS384"))
        for token in bad_tokens:
            self.replace_cookie(self.client, ACCESS_COOKIE, token)
            self.assertEqual(self.client.get("/expenses").status_code, 401)

    def test_expired_refresh_clears_cookies(self):
        claims = jwt.decode(self.client.cookies[REFRESH_COOKIE], options={"verify_signature": False})
        expired = issue_token("refresh", claims["sub"], claims["sid"], int(time.time()) - 1)
        self.replace_cookie(self.client, REFRESH_COOKIE, expired)
        response = self.client.post("/auth/refresh")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "token_expired")
        self.assertEqual(len(response.headers.get_list("set-cookie")), 3)
        self.assertNotIn(ACCESS_COOKIE, self.client.cookies)

    def test_logout_revokes_copied_tokens_and_deletes_cookies(self):
        copied = self.clone()
        response = self.client.post("/auth/logout")
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, b"")
        for header in response.headers.get_list("set-cookie"):
            self.assertIn("Max-Age=0", header)
            self.assertIn("Secure", header)
            self.assertIn("Path=/", header)
        self.assertNotIn(ACCESS_COOKIE, self.client.cookies)
        self.assertEqual(copied.get("/expenses").status_code, 401)
        self.assertEqual(copied.post("/auth/refresh").status_code, 401)

    def test_absolute_session_expiry_is_not_extended(self):
        old = jwt.decode(self.client.cookies[REFRESH_COOKIE], options={"verify_signature": False})
        self.assertEqual(self.client.post("/auth/refresh").status_code, 200)
        new = jwt.decode(self.client.cookies[REFRESH_COOKIE], options={"verify_signature": False})
        self.assertEqual(old["exp"], new["exp"])
        with self.factory() as db:
            session = db.get(AuthSession, new["sid"])
            session.expires_at = int(time.time()) - 1
            db.commit()
        self.assertEqual(self.client.get("/auth/me").status_code, 401)
        self.assertEqual(self.client.post("/auth/refresh").status_code, 401)

    def test_other_user_cannot_read_update_or_delete_expense(self):
        expense = self.create()
        with self.factory() as db:
            db.add(User(username="bob", password_hash=TEST_HASH))
            db.commit()
        bob = self.anonymous()
        csrf = bob.get("/auth/csrf").json()["csrf_token"]
        bob.headers.update({"Origin": "https://testserver", "X-CSRF-Token": csrf})
        login = bob.post("/auth/login", json={"username": "bob", "password": TEST_PASSWORD})
        bob.headers["X-CSRF-Token"] = login.json()["csrf_token"]
        self.assertEqual(bob.get("/expenses").json(), [])
        path = f"/expenses/{expense['id']}"
        self.assertEqual(bob.get(path).status_code, 404)
        self.assertEqual(bob.put(path, json={"description": "stolen", "amount": 1}).status_code, 404)
        self.assertEqual(bob.delete(path).status_code, 404)
        self.assertEqual(self.client.get(path).json(), expense)
        self.assertEqual(bob.post("/expenses", json={"description": "bad", "amount": 1, "owner_id": 1}).status_code, 422)

    def test_legacy_unowned_expenses_are_hidden(self):
        with self.engine.begin() as connection:
            connection.execute(text("INSERT INTO expenses(description,amount) VALUES ('legacy',1)"))
            row_id = connection.execute(text("SELECT id FROM expenses")).scalar_one()
        self.assertEqual(self.client.get("/expenses").json(), [])
        self.assertEqual(self.client.get(f"/expenses/{row_id}").status_code, 404)

    def test_secure_cookies_not_sent_over_http(self):
        self.assertEqual(self.client.get("http://testserver/auth/me").status_code, 401)

    def test_missing_refresh_and_tampered_csrf(self):
        self.client.cookies.delete(REFRESH_COOKIE)
        self.assertEqual(self.client.post("/auth/refresh").status_code, 401)
        fake = "forged.csrf.token"
        self.replace_cookie(self.client, CSRF_COOKIE, fake)
        self.client.headers["X-CSRF-Token"] = fake
        self.assertEqual(self.client.post("/auth/login", json={"username": "alice", "password": TEST_PASSWORD}).status_code, 403)

    def test_logout_works_with_expired_access(self):
        copied = self.clone()
        claims = jwt.decode(self.client.cookies[ACCESS_COOKIE], options={"verify_signature": False})
        self.replace_cookie(self.client, ACCESS_COOKIE, issue_token("access", claims["sub"], claims["sid"], int(time.time()) - 1))
        self.assertEqual(self.client.post("/auth/logout").status_code, 204)
        self.assertEqual(copied.get("/auth/me").status_code, 401)

    def test_startup_rejects_missing_secret_or_http_origin(self):
        import os
        from unittest.mock import patch

        for values in ({"JWT_SECRET": ""}, {"APP_ORIGIN": "http://testserver"}):
            with patch.dict(os.environ, values):
                get_settings.cache_clear()
                with self.assertRaises(RuntimeError):
                    with TestClient(app, base_url="https://testserver"):
                        pass
        get_settings.cache_clear()

    def test_populated_legacy_migration_preserves_without_assigning(self):
        from alembic import command

        command.downgrade(self.config, "0001")
        with self.engine.begin() as connection:
            connection.execute(text("INSERT INTO expenses(description,amount) VALUES ('old record',12.5)"))
        command.upgrade(self.config, "head")
        with self.engine.connect() as connection:
            row = connection.execute(text("SELECT description,amount,owner_id FROM expenses")).one()
            self.assertEqual(tuple(row), ("old record", 12.5, None))
            self.assertEqual(connection.execute(text("PRAGMA foreign_keys")).scalar(), 1)
        self.seed_and_login()
        self.assertEqual(self.client.get("/expenses").json(), [])

    def test_foreign_key_rejects_nonexistent_owner(self):
        from sqlalchemy.exc import IntegrityError

        with self.assertRaises(IntegrityError):
            with self.engine.begin() as connection:
                connection.execute(text("INSERT INTO expenses(description,amount,owner_id) VALUES ('invalid',1,99999)"))

    def test_example_client_renews_and_retries_without_password(self):
        from examples.session_client import SessionClient

        client = self.anonymous()
        api = SessionClient(client, "https://testserver")
        api.login("alice", TEST_PASSWORD)
        client.cookies.delete(ACCESS_COOKIE)
        response = api.request("POST", "/expenses", json={"description": "renewed", "amount": 2.5})
        self.assertEqual(response.status_code, 201)
        self.assertEqual(api.request("GET", "/expenses").json(), [response.json()])
        api.logout()
        self.assertEqual(client.get("/auth/me").status_code, 401)

    def test_user_creation_tool_stores_argon2_and_allows_login(self):
        from unittest.mock import patch
        import create_user
        from security import password_hash

        with patch.object(create_user, "SessionLocal", self.factory), \
                patch("sys.argv", ["create_user.py", "student"]), \
                patch.object(create_user.getpass, "getpass", side_effect=[TEST_PASSWORD, TEST_PASSWORD]):
            create_user.main()
        with self.factory() as db:
            user = db.scalar(select(User).where(User.username == "student"))
            self.assertTrue(user.password_hash.startswith("$argon2id$"))
            self.assertTrue(password_hash.verify(TEST_PASSWORD, user.password_hash))
        client = self.anonymous()
        csrf = client.get("/auth/csrf").json()["csrf_token"]
        response = client.post("/auth/login", json={"username": "student", "password": TEST_PASSWORD},
                               headers={"Origin": "https://testserver", "X-CSRF-Token": csrf})
        self.assertEqual(response.status_code, 200)

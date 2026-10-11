from concurrent.futures import ThreadPoolExecutor
import gettext
import unittest

from fastapi.testclient import TestClient
from i18n import select_language, load_catalog
from main import app
from test_support import ExpenseFixture, TEST_PASSWORD


class LanguageSelectionTests(unittest.TestCase):
    def test_negotiation(self):
        cases = [
            (None, "", "en"), (None, "fa-IR", "fa"),
            (None, "en;q=0.3,fa;q=0.9", "fa"),
            (None, "fa;q=0,en;q=0.5", "en"),
            (None, "fa;q=bad,en", "en"), (None, "fa;q=2,en", "en"),
            (None, "de,fa;q=0.5", "fa"), (None, "*", "en"),
            (None, "en;q=0,*;q=0.8", "fa"),
            (None, "fa;q=0,en;q=0", "en"),
            ("fa", "en", "fa"), ("EN-us", "fa", "en"),
            ("unsupported", "fa", "en"), ("../../etc", "fa", "en"),
        ]
        for query, header, expected in cases:
            with self.subTest(query=query, header=header):
                self.assertEqual(select_language(query, header), expected)

    def test_mo_files_and_missing_message_fallback(self):
        for language in ("en", "fa"):
            catalog = load_catalog(language)
            self.assertIsInstance(catalog, gettext.GNUTranslations)
            self.assertEqual(catalog.gettext("Untranslated source text"), "Untranslated source text")
        self.assertNotEqual(load_catalog("fa").gettext("Welcome to the expense manager."), "Welcome to the expense manager.")

    def test_concurrent_requests_do_not_share_language(self):
        # No lifespan is needed for these read-only public endpoints.
        def request(language):
            client = TestClient(app, base_url="https://testserver")
            try:
                return client.get("/welcome", headers={"Accept-Language": language}).json()
            finally:
                client.close()
        languages = ["fa", "en"] * 10
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(request, languages))
        for language, result in zip(languages, results):
            self.assertEqual(result["language"], language)
            self.assertEqual(result["message"], load_catalog(language).gettext("Welcome to the expense manager."))


class LocalizedAPITests(ExpenseFixture):
    def test_public_messages_query_and_headers(self):
        for path in ("/welcome", "/about"):
            response = self.client.get(path + "?lang=fa", headers={"Accept-Language": "en"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()["language"], "fa")
            self.assertEqual(response.headers["Content-Language"], "fa")
            self.assertIn("Accept-Language", response.headers["Vary"])
        self.assertEqual(self.client.get("/welcome?lang=xx").headers["Content-Language"], "en")

    def test_expense_errors_and_validation_are_translated(self):
        response = self.client.get("/expenses/99999?lang=fa")
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "Expense not found", "message": "هزینه پیدا نشد."})
        invalid = self.client.post("/expenses?lang=fa", json={"description": "Lunch", "amount": -1})
        self.assertEqual(invalid.status_code, 422)
        self.assertEqual(invalid.json()["detail"][0]["type"], "greater_than")
        self.assertIn("بزرگ‌تر", invalid.json()["detail"][0]["msg"])
        self.assertNotIn("input", invalid.json()["detail"][0])

    def test_auth_success_and_csrf_messages_keep_codes(self):
        login = self.client.post("/auth/login?lang=fa", json={"username": "alice", "password": TEST_PASSWORD})
        self.assertEqual(login.json()["code"], "logged_in")
        self.assertEqual(login.json()["message"], "با موفقیت وارد شدید.")
        self.client.headers["X-CSRF-Token"] = login.json()["csrf_token"]
        refresh = self.client.post("/auth/refresh?lang=fa")
        self.assertEqual(refresh.json(), {"code": "session_renewed", "message": "نشست شما تمدید شد."})
        denied = self.client.post("/auth/refresh?lang=fa", headers={"Origin": "https://evil.example"})
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(denied.json()["detail"], "csrf_failed")
        self.assertEqual(denied.json()["message"], "بررسی امنیتی درخواست ناموفق بود.")

    def test_unauthenticated_message_and_unknown_routes(self):
        self.client.cookies.clear()
        response = self.client.get("/expenses?lang=fa")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "authentication_required")
        self.assertEqual(response.json()["message"], "برای ادامه وارد حساب خود شوید.")
        self.assertEqual(self.client.get("/missing?lang=fa").json()["message"], "مسیر درخواستی پیدا نشد.")

    def test_summary_plural_and_user_text_unchanged(self):
        self.assertEqual(self.client.get("/expenses/summary").json()["message"], "You have 0 expenses.")
        self.create("توضیح شخصی", 1)
        self.assertEqual(self.client.get("/expenses/summary").json()["message"], "You have 1 expense.")
        self.create("Second", 2)
        response = self.client.get("/expenses/summary?lang=fa")
        self.assertEqual(response.json()["count"], 2)
        self.assertEqual(response.json()["message"], "شما 2 هزینه دارید.")
        self.assertEqual(self.client.get("/expenses?lang=en").json()[0]["description"], "توضیح شخصی")

    def test_logout_remains_empty_204(self):
        response = self.client.post("/auth/logout?lang=fa")
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, b"")
        self.assertEqual(response.headers["Content-Language"], "fa")

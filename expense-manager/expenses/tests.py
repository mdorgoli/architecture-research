from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError, transaction
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from config.telemetry import scrub_event
from .models import Category, Expense


class ExpenseTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.alice = User.objects.create_user("alice", password="Strong-test-password-123")
        cls.bob = User.objects.create_user("bob", password="Strong-test-password-456")
        cls.food = Category.objects.create(owner=cls.alice, name="خوراک")
        cls.private = Category.objects.create(owner=cls.bob, name="دسته خصوصی")
        cls.expense = Expense.objects.create(
            owner=cls.alice,
            category=cls.food,
            title="ناهار",
            amount=125000,
            spent_on=date(2026, 10, 10),
        )
        cls.other = Expense.objects.create(
            owner=cls.bob,
            category=cls.private,
            title="BOB-SECRET",
            amount=999999,
            spent_on=date(2026, 10, 10),
        )

    def setUp(self):
        self.client.force_login(self.alice, backend="django.contrib.auth.backends.ModelBackend")

    def payload(self, **changes):
        data = {
            "title": "رفت‌وآمد",
            "amount": "32000",
            "category": self.food.pk,
            "spent_on": "2026-10-11",
            "note": "",
        }
        data.update(changes)
        return data

    def test_anonymous_redirects_to_login(self):
        self.client.logout()
        for url in ("/", "/expenses/new/", "/categories/"):
            self.assertEqual(self.client.get(url).status_code, 302)

    def test_dashboard_isolates_totals_and_rows(self):
        response = self.client.get("/?month=2026-10")
        self.assertEqual(response.context["total"], Decimal("125000"))
        self.assertContains(response, "ناهار")
        self.assertNotContains(response, "BOB-SECRET")
        self.assertNotContains(response, "دسته خصوصی")
        self.assertIn("no-store", response.headers["Cache-Control"])

    def test_month_boundaries(self):
        Expense.objects.create(
            owner=self.alice, category=self.food, title="next", amount=1, spent_on=date(2026, 11, 1)
        )
        self.assertEqual(self.client.get("/?month=2026-10").context["count"], 1)
        self.assertEqual(self.client.get("/?month=2026-11").context["total"], 1)

    def test_invalid_month_is_handled(self):
        for month in ("bad", "2026-13", "9999-12"):
            self.assertEqual(self.client.get("/", {"month": month}).status_code, 200)

    def test_category_filter(self):
        response = self.client.get("/", {"month": "2026-10", "category": self.food.pk})
        self.assertEqual(response.context["count"], 1)
        for category in (self.private.pk, "bad", "9" * 100):
            self.assertEqual(self.client.get("/", {"category": category}).status_code, 404)

    def test_create_binds_owner_server_side(self):
        response = self.client.post("/expenses/new/", self.payload(owner=self.bob.pk))
        self.assertRedirects(response, "/")
        self.assertEqual(Expense.objects.get(title="رفت‌وآمد").owner, self.alice)

    def test_cannot_assign_another_users_category(self):
        response = self.client.post("/expenses/new/", self.payload(category=self.private.pk))
        self.assertEqual(response.status_code, 200)
        self.assertIn("category", response.context["form"].errors)
        self.assertEqual(Expense.objects.count(), 2)

    def test_reject_invalid_amounts_and_dates(self):
        for amount in ("0", "-1", "1.5", "999999999999999", "not-a-number"):
            response = self.client.post("/expenses/new/", self.payload(amount=amount))
            self.assertIn("amount", response.context["form"].errors)
        response = self.client.post("/expenses/new/", self.payload(spent_on="2026-02-30"))
        self.assertIn("spent_on", response.context["form"].errors)

    def test_model_rejects_cross_owner_category(self):
        with self.assertRaises(ValidationError):
            Expense.objects.create(owner=self.alice, category=self.private, title="bad", amount=1)

    def test_database_positive_constraint(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Expense.objects.filter(pk=self.expense.pk).update(amount=-1)

    def test_edit_own_expense(self):
        self.client.post(
            reverse("expense_edit", args=[self.expense.pk]), self.payload(title="Updated")
        )
        self.expense.refresh_from_db()
        self.assertEqual(self.expense.title, "Updated")

    def test_cannot_read_edit_delete_other_expense(self):
        edit = reverse("expense_edit", args=[self.other.pk])
        self.assertEqual(self.client.get(edit).status_code, 404)
        self.assertEqual(self.client.post(edit, self.payload()).status_code, 404)
        self.assertEqual(
            self.client.post(reverse("expense_delete", args=[self.other.pk])).status_code, 404
        )
        self.assertTrue(Expense.objects.filter(pk=self.other.pk).exists())

    def test_delete_requires_post(self):
        url = reverse("expense_delete", args=[self.expense.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(url).status_code, 302)
        self.assertFalse(Expense.objects.filter(pk=self.expense.pk).exists())

    def test_csrf_is_required(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.alice, backend="django.contrib.auth.backends.ModelBackend")
        for url in (
            "/expenses/new/",
            reverse("expense_delete", args=[self.expense.pk]),
            "/categories/",
            "/accounts/logout/",
        ):
            self.assertEqual(client.post(url, self.payload()).status_code, 403)

    def test_category_create_and_duplicate(self):
        self.assertEqual(
            self.client.post("/categories/", {"name": "مسافرت", "owner": self.bob.pk}).status_code,
            302,
        )
        self.assertEqual(Category.objects.get(name="مسافرت").owner, self.alice)
        response = self.client.post("/categories/", {"name": "مسافرت"})
        self.assertIn("name", response.context["form"].errors)

    def test_category_delete_is_scoped_and_protected(self):
        self.assertEqual(
            self.client.post(reverse("category_delete", args=[self.private.pk])).status_code, 404
        )
        self.client.post(reverse("category_delete", args=[self.food.pk]))
        self.assertTrue(Category.objects.filter(pk=self.food.pk).exists())
        unused = Category.objects.create(owner=self.alice, name="unused")
        url = reverse("category_delete", args=[unused.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.post(url)
        self.assertFalse(Category.objects.filter(pk=unused.pk).exists())

    def test_user_text_is_escaped(self):
        self.expense.title = "<script>alert(1)</script>"
        self.expense.save()
        response = self.client.get("/?month=2026-10")
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, "<script>alert(1)</script>")

    def test_pagination_keeps_total(self):
        for number in range(22):
            Expense.objects.create(
                owner=self.alice,
                category=self.food,
                title=str(number),
                amount=1,
                spent_on=date(2026, 10, 10),
            )
        response = self.client.get("/?month=2026-10&page=2")
        self.assertEqual(len(response.context["page_obj"]), 3)
        self.assertEqual(response.context["total"], 125022)

    def test_signup_and_default_categories(self):
        self.client.logout()
        response = self.client.post(
            "/accounts/signup/",
            {
                "username": "Charlie",
                "password1": "Long-enough-test-password-321",
                "password2": "Long-enough-test-password-321",
            },
        )
        self.assertRedirects(response, "/")
        user = User.objects.get(username="charlie")
        self.assertEqual(Category.objects.filter(owner=user).count(), 5)
        self.assertTrue(user.check_password("Long-enough-test-password-321"))

    def test_signup_rejects_weak_password(self):
        self.client.logout()
        response = self.client.post(
            "/accounts/signup/", {"username": "weak", "password1": "123", "password2": "123"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="weak").exists())

    def test_login_logout_and_open_redirect_protection(self):
        self.client.logout()
        response = self.client.post(
            "/accounts/login/",
            {
                "username": "ALICE",
                "password": "Strong-test-password-123",
                "next": "https://example.org/",
            },
        )
        self.assertRedirects(response, "/")
        self.assertEqual(self.client.get("/accounts/logout/").status_code, 405)
        self.assertRedirects(self.client.post("/accounts/logout/"), "/accounts/login/")

    def test_login_locks_after_five_failures(self):
        self.client.logout()
        for _ in range(5):
            self.client.post("/accounts/login/", {"username": "ALICE", "password": "incorrect"})
        response = self.client.post(
            "/accounts/login/", {"username": "alice", "password": "Strong-test-password-123"}
        )
        self.assertEqual(response.status_code, 429)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_readiness_failure_and_liveness(self):
        self.assertEqual(self.client.get("/health/ready/").status_code, 200)
        with patch(
            "expenses.views.connection.cursor", side_effect=DatabaseError("secret connection data")
        ):
            response = self.client.get("/health/ready/")
            self.assertEqual(response.status_code, 503)
            self.assertNotContains(response, "secret", status_code=503)
            self.assertEqual(self.client.get("/health/live/").status_code, 200)

    @override_settings(
        SECURE_SSL_REDIRECT=True, SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https")
    )
    def test_https_redirect_proxy_and_health(self):
        self.assertEqual(self.client.get("/").status_code, 301)
        self.assertEqual(self.client.get("/", HTTP_X_FORWARDED_PROTO="https").status_code, 200)
        self.assertEqual(self.client.get("/health/live/").status_code, 200)

    def test_sentry_scrubs_sensitive_data(self):
        event = {
            "request": {"data": "secret"},
            "user": {"id": 1},
            "breadcrumbs": [],
            "extra": {},
            "message": "expense",
            "logentry": {"message": "expense"},
            "exception": {
                "values": [
                    {
                        "value": "expense secret",
                        "stacktrace": {
                            "frames": [{"vars": {"password": "secret"}, "filename": "views.py"}]
                        },
                    }
                ]
            },
        }
        result = scrub_event(event, {})
        self.assertNotIn("secret", str(result))
        self.assertNotIn("request", result)
        self.assertIn("views.py", str(result))

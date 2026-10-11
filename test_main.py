import unittest
from alembic import command
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from pydantic import ValidationError
from schemas import ExpenseOutput
from test_support import ExpenseFixture


class ExpenseAPITests(ExpenseFixture):
    def test_empty_list(self):
        response = self.client.get("/expenses")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    def test_create_and_read(self):
        expense = self.create("ناهار", 125.75)
        self.assertIsInstance(expense["id"], int)
        self.assertEqual(expense["description"], "ناهار")
        self.assertEqual(expense["amount"], 125.75)
        response = self.client.get(f"/expenses/{expense['id']}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), expense)
        self.assertEqual(self.client.get("/expenses").json(), [expense])

    def test_update_preserves_id_and_other_expenses(self):
        first = self.create()
        second = self.create("Bus", 2.5)
        response = self.client.put(
            f"/expenses/{first['id']}",
            json={"description": "Dinner", "amount": 20.25},
        )
        expected = {"id": first["id"], "description": "Dinner", "amount": 20.25}
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), expected)
        self.assertEqual(self.client.get(f"/expenses/{first['id']}").json(), expected)
        self.assertEqual(self.client.get(f"/expenses/{second['id']}").json(), second)

    def test_delete_and_ids_are_not_reused(self):
        first = self.create()
        second = self.create()
        response = self.client.delete(f"/expenses/{second['id']}")
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, b"")
        self.assertEqual(self.client.get(f"/expenses/{second['id']}").status_code, 404)
        third = self.create()
        self.assertGreater(third["id"], second["id"])
        self.assertEqual(self.client.get("/expenses").json(), [first, third])

    def test_missing_expenses_return_404(self):
        for method in ("get", "put", "delete"):
            with self.subTest(method=method):
                kwargs = {"json": {"description": "Missing", "amount": 1.5}} if method == "put" else {}
                response = getattr(self.client, method)("/expenses/999999", **kwargs)
                self.assertEqual(response.status_code, 404)
                self.assertEqual(response.json(), {"detail": "Expense not found"})
        self.assertEqual(self.client.get("/expenses").json(), [])

    def test_invalid_input_and_failed_update_leave_data_unchanged(self):
        expense = self.create()
        for payload in ({"description": "Missing amount"}, {"description": "Bad", "amount": "abc"}, {"description": "Bad", "amount": "Infinity"}):
            with self.subTest(payload=payload):
                self.assertEqual(self.client.post("/expenses", json=payload).status_code, 422)
                self.assertEqual(self.client.put(f"/expenses/{expense['id']}", json=payload).status_code, 422)
        self.assertEqual(self.client.get("/expenses/abc").status_code, 422)
        self.assertEqual(self.client.get("/expenses").json(), [expense])

    def test_validation_rejects_invalid_fields_without_mutation(self):
        expense = self.create()
        invalid = [
            {"description": value, "amount": 10}
            for value in ("", "   ", "\n\t", None, 123, True)
        ] + [
            {"description": "Lunch", "amount": value}
            for value in (0, -1, "12.5", True, None, "NaN")
        ] + [
            {"description": "Lunch", "amount": 10, "id": 99},
            {"description": "Lunch", "amount": 10, "unknown": "field"},
        ]
        for payload in invalid:
            for method, path in (("post", "/expenses"), ("put", f"/expenses/{expense['id']}")):
                with self.subTest(payload=payload, method=method):
                    response = getattr(self.client, method)(path, json=payload)
                    self.assertEqual(response.status_code, 422)
                    self.assertTrue(response.json()["detail"])
        self.assertEqual(self.client.get("/expenses").json(), [expense])

    def test_whitespace_normalization_and_numeric_amount(self):
        expense = self.create("  خرید کتاب!  ", 10)
        self.assertEqual(expense["description"], "خرید کتاب!")
        self.assertEqual(expense["amount"], 10.0)
        self.assertIsInstance(expense["amount"], float)
        self.assertEqual(set(expense), {"id", "description", "amount"})

    def test_output_schema_rejects_invalid_id(self):
        with self.assertRaises(ValidationError):
            ExpenseOutput(id=-1, description="Bad", amount=1.0)

    def test_data_survives_new_engine(self):
        expense = self.create("Persistent", 42.5)
        self.engine.dispose()
        other = create_engine(self.url)
        try:
            with other.connect() as connection:
                row = connection.execute(text("SELECT id, description, amount FROM expenses")).mappings().one()
                self.assertEqual(dict(row), expense)
        finally:
            other.dispose()

    def test_database_constraints(self):
        for description, amount in (("", 1), ("  ", 1), ("Bad", 0), ("Bad", -1), ("Bad", float("inf")), (None, 1), ("Bad", None)):
            with self.subTest(description=description, amount=amount):
                with self.assertRaises(IntegrityError):
                    with self.engine.begin() as connection:
                        connection.execute(
                            text("INSERT INTO expenses(description, amount) VALUES (:description, :amount)"),
                            {"description": description, "amount": amount},
                        )
        self.assertEqual(self.client.get("/expenses").json(), [])

    def test_migration_round_trip_and_model_match(self):
        command.check(self.config)
        self.assertIn("expenses", inspect(self.engine).get_table_names())
        command.downgrade(self.config, "base")
        self.assertNotIn("expenses", inspect(self.engine).get_table_names())
        command.upgrade(self.config, "head")
        command.check(self.config)
        with self.engine.connect() as connection:
            self.assertEqual(connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one(), "0002")
        self.seed_and_login()
        self.create()


if __name__ == "__main__":
    unittest.main()

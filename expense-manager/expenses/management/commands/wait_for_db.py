import time
from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, connection


class Command(BaseCommand):
    help = "Wait up to 60 seconds for the configured database."

    def handle(self, *args, **options):
        deadline = time.monotonic() + 60
        while True:
            try:
                connection.ensure_connection()
                self.stdout.write("Database is available.")
                return
            except DatabaseError:
                connection.close()
                if time.monotonic() >= deadline:
                    raise CommandError(
                        "Database unavailable; verify connection configuration."
                    ) from None
                time.sleep(2)

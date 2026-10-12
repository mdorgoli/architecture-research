import os
import sentry_sdk
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Send one synthetic error to Sentry; confirm receipt in its dashboard."

    def handle(self, *args, **options):
        if not os.getenv("SENTRY_DSN"):
            raise CommandError("SENTRY_DSN is not configured.")
        try:
            raise RuntimeError("Synthetic expense-manager deployment check")
        except RuntimeError:
            event_id = sentry_sdk.capture_exception()
        sentry_sdk.flush(timeout=10)
        self.stdout.write(
            f"Queued event: {event_id}. Verify receipt in Sentry; this is not a delivery confirmation."
        )

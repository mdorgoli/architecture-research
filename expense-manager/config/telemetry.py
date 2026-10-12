def scrub_event(event, hint):
    """Retain stack locations, not customer expense text, SQL or request data."""
    for key in ("request", "user", "breadcrumbs", "extra", "message", "logentry"):
        event.pop(key, None)
    for exception in event.get("exception", {}).get("values", []):
        exception["value"] = "Exception details redacted"
        for frame in exception.get("stacktrace", {}).get("frames", []):
            frame.pop("vars", None)
    return event

import os
from dataclasses import dataclass
from functools import lru_cache
from urllib.parse import urlsplit


@dataclass(frozen=True)
class Settings:
    secret: str
    origin: str
    issuer: str = "expense-api"
    audience: str = "expense-browser"
    access_seconds: int = 15 * 60
    refresh_seconds: int = 7 * 24 * 60 * 60


@lru_cache
def get_settings():
    secret = os.getenv("JWT_SECRET", "")
    if len(secret.encode()) < 32:
        raise RuntimeError("JWT_SECRET must contain at least 32 bytes; generate a random secret.")
    origin = os.getenv("APP_ORIGIN", "https://localhost:8443")
    parsed = urlsplit(origin)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.path or
            parsed.query or parsed.fragment or parsed.username or parsed.password):
        raise RuntimeError("APP_ORIGIN must be an HTTPS origin without a path or trailing slash.")
    return Settings(secret=secret, origin=origin)

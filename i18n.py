import gettext
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from fastapi import Request

SUPPORTED_LANGUAGES = ("en", "fa")
DEFAULT_LANGUAGE = "en"
LOCALES = Path(__file__).resolve().parent / "locales"


def select_language(query: str | None, header: str) -> str:
    if query is not None:
        language = query.strip().lower().split("-")[0]
        return language if language in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE
    ranges = []
    for position, item in enumerate(header[:4096].split(",")[:50]):
        parts = [part.strip().lower() for part in item.split(";")]
        tag = parts[0]
        if not re.fullmatch(r"[a-z]{1,8}(?:-[a-z0-9]{1,8})*|\*", tag):
            continue
        quality = 1.0
        if len(parts) > 1:
            if len(parts) != 2 or not re.fullmatch(r"q=(?:0(?:\.[0-9]{0,3})?|1(?:\.0{0,3})?)", parts[1]):
                continue
            quality = float(parts[1][2:])
        ranges.append((tag.split("-")[0], quality, position))
    candidates = []
    for language in SUPPORTED_LANGUAGES:
        specific = [(q, pos) for tag, q, pos in ranges if tag == language]
        matches = specific or [(q, pos) for tag, q, pos in ranges if tag == "*"]
        if matches:
            quality, position = max(matches, key=lambda pair: (pair[0], -pair[1]))
            if quality > 0:
                candidates.append((quality, -position, language == DEFAULT_LANGUAGE, language))
    return max(candidates)[3] if candidates else DEFAULT_LANGUAGE


@lru_cache(maxsize=16)
def load_catalog(language: str):
    if language not in SUPPORTED_LANGUAGES:
        language = DEFAULT_LANGUAGE
    # Only allowlisted directories are read; missing catalogs fail at startup.
    with (LOCALES / language / "LC_MESSAGES" / "messages.mo").open("rb") as source:
        return gettext.GNUTranslations(source)


@dataclass(frozen=True)
class Translator:
    language: str

    def gettext(self, message):
        return load_catalog(self.language).gettext(message)

    def ngettext(self, singular, plural, count):
        return load_catalog(self.language).ngettext(singular, plural, count)


def get_translator(request: Request) -> Translator:
    # Request-local selection; never install a process-wide gettext language.
    return Translator(select_language(request.query_params.get("lang"), request.headers.get("accept-language", "")))


ERROR_MESSAGES = {
    "authentication_required": "Please log in to continue.",
    "invalid_credentials": "The username or password is incorrect.",
    "token_expired": "The token has expired.",
    "invalid_token": "The token is invalid.",
    "session_invalid": "The session is no longer valid. Please log in again.",
    "refresh_reused": "A refresh token was reused. Please log in again.",
    "csrf_failed": "The request security check failed.",
    "Expense not found": "Expense not found.",
    "Not Found": "The requested route was not found.",
    "Method Not Allowed": "This HTTP method is not allowed.",
}

VALIDATION_MESSAGES = {
    "missing": "This field is required.",
    "string_type": "Enter a text value.",
    "string_too_short": "The text is too short.",
    "string_too_long": "The text is too long.",
    "string_pattern_mismatch": "The text format is invalid.",
    "float_type": "Enter a numeric value.",
    "float_parsing": "Enter a numeric value.",
    "finite_number": "Enter a finite number.",
    "greater_than": "The number must be greater than the allowed minimum.",
    "int_parsing": "Enter an integer.",
    "int_type": "Enter an integer.",
    "extra_forbidden": "Extra fields are not allowed.",
    "json_invalid": "The JSON body is invalid.",
}

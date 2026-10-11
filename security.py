import hashlib
import secrets
import time

import jwt
from fastapi import Depends, HTTPException, Request, Response
from pwdlib import PasswordHash
from sqlalchemy.orm import Session

from database import get_db
from models import AuthSession, User
from settings import get_settings

ACCESS_COOKIE = "__Host-access"
REFRESH_COOKIE = "__Host-refresh"
CSRF_COOKIE = "__Host-csrf"
password_hash = PasswordHash.recommended()
# One dummy hash per process makes unknown-user and wrong-password paths comparable.
DUMMY_HASH = password_hash.hash(secrets.token_urlsafe(32))


class AuthError(Exception):
    def __init__(self, code, clear=False):
        self.code = code
        self.clear = clear


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def issue_token(kind: str, subject: str, sid: str, expires: int) -> str:
    settings = get_settings()
    now = int(time.time())
    return jwt.encode({
        "sub": subject, "sid": sid, "type": kind,
        "jti": secrets.token_hex(16), "iat": now, "nbf": now,
        "exp": expires, "iss": settings.issuer, "aud": settings.audience,
    }, settings.secret, algorithm="HS256")


def decode_token(token: str | None, kind: str, *, allow_expired=False):
    if not token:
        raise AuthError("authentication_required")
    settings = get_settings()
    try:
        claims = jwt.decode(
            token, settings.secret, algorithms=["HS256"],
            issuer=settings.issuer, audience=settings.audience,
            options={"require": ["sub", "sid", "type", "jti", "iat", "nbf", "exp", "iss", "aud"],
                     "verify_exp": not allow_expired},
        )
        if claims["type"] != kind:
            raise jwt.InvalidTokenError()
        if not all(isinstance(claims[k], str) and claims[k] for k in ("sub", "sid", "jti")):
            raise jwt.InvalidTokenError()
        if not all(type(claims[k]) is int for k in ("exp", "iat", "nbf")):
            raise jwt.InvalidTokenError()
        if kind != "csrf" and (not claims["sub"].isascii() or not claims["sub"].isdigit() or len(claims["sub"]) > 18):
            raise jwt.InvalidTokenError()
        return claims
    except jwt.ExpiredSignatureError:
        raise AuthError("token_expired") from None
    except jwt.InvalidTokenError:
        raise AuthError("invalid_token") from None


def set_cookie(response: Response, name: str, value: str, seconds: int, *, httponly=True):
    response.set_cookie(name, value, max_age=seconds, path="/", secure=True,
                        httponly=httponly, samesite="strict")


def clear_cookies(response: Response):
    for name in (ACCESS_COOKIE, REFRESH_COOKIE, CSRF_COOKIE):
        response.delete_cookie(name, path="/", secure=True,
                               httponly=name != CSRF_COOKIE, samesite="strict")


def set_session_cookies(response: Response, access: str, refresh: str, csrf: str, expires: int):
    remaining = max(0, expires - int(time.time()))
    set_cookie(response, ACCESS_COOKIE, access, min(get_settings().access_seconds, remaining))
    set_cookie(response, REFRESH_COOKIE, refresh, remaining)
    set_cookie(response, CSRF_COOKIE, csrf, remaining, httponly=False)


def require_csrf(request: Request):
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    if request.headers.get("origin") != get_settings().origin:
        raise HTTPException(403, "csrf_failed")
    cookie = request.cookies.get(CSRF_COOKIE, "")
    header = request.headers.get("x-csrf-token", "")
    if not cookie or not secrets.compare_digest(cookie.encode(), header.encode()):
        raise HTTPException(403, "csrf_failed")
    try:
        decode_token(cookie, "csrf")
    except AuthError:
        raise HTTPException(403, "csrf_failed") from None


def check_session_csrf(request: Request, session: AuthSession):
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        token = request.cookies.get(CSRF_COOKIE, "")
        if not secrets.compare_digest(digest(token), session.csrf_hash):
            raise HTTPException(403, "csrf_failed")


def current_user(request: Request, db: Session = Depends(get_db)):
    claims = decode_token(request.cookies.get(ACCESS_COOKIE), "access")
    session = db.get(AuthSession, claims["sid"])
    if (session is None or session.revoked or session.expires_at <= int(time.time())
            or session.user_id != int(claims["sub"])):
        raise AuthError("session_invalid")
    user = db.get(User, session.user_id)
    if user is None:
        raise AuthError("session_invalid")
    check_session_csrf(request, session)
    return user

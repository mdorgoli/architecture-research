import secrets
import time

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from database import get_db
from models import AuthSession, User
from security import (
    ACCESS_COOKIE, REFRESH_COOKIE, CSRF_COOKIE, AuthError, DUMMY_HASH,
    check_session_csrf, clear_cookies, current_user, decode_token, digest,
    issue_token, password_hash, set_cookie, set_session_cookies,
)
from settings import get_settings
from i18n import Translator, get_translator

router = APIRouter(prefix="/auth", tags=["Authentication"])


class LoginInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    username: str = Field(min_length=3, max_length=64, pattern=r"^[a-zA-Z0-9_.-]+$")
    password: str = Field(min_length=1, max_length=128)


@router.get("/csrf")
def csrf(request: Request, response: Response):
    token = request.cookies.get(CSRF_COOKIE)
    try:
        claims = decode_token(token, "csrf")
        remaining = claims["exp"] - int(time.time())
    except AuthError:
        remaining = get_settings().refresh_seconds
        token = issue_token("csrf", "csrf", "preauth", int(time.time()) + remaining)
    set_cookie(response, CSRF_COOKIE, token, remaining, httponly=False)
    return {"csrf_token": token}


@router.post("/login")
def login(data: LoginInput, request: Request, response: Response, db: Session = Depends(get_db), translator: Translator = Depends(get_translator)):
    user = db.scalar(select(User).where(User.username == data.username))
    valid = password_hash.verify(data.password, user.password_hash if user else DUMMY_HASH)
    if user is None or not valid:
        raise AuthError("invalid_credentials")
    settings = get_settings()
    now = int(time.time())
    expires = now + settings.refresh_seconds
    sid = secrets.token_hex(32)
    csrf_token = issue_token("csrf", "csrf", sid, expires)
    refresh = issue_token("refresh", str(user.id), sid, expires)
    access = issue_token("access", str(user.id), sid, now + settings.access_seconds)
    # Replace this browser's previous signed session, if present.
    try:
        old = decode_token(request.cookies.get(REFRESH_COOKIE), "refresh", allow_expired=True)
        db.execute(update(AuthSession).where(AuthSession.id == old["sid"], AuthSession.user_id == int(old["sub"])).values(revoked=True))
    except AuthError:
        pass
    db.add(AuthSession(id=sid, user_id=user.id, refresh_hash=digest(refresh),
                       csrf_hash=digest(csrf_token), expires_at=expires, revoked=False))
    db.commit()
    set_session_cookies(response, access, refresh, csrf_token, expires)
    return {"code": "logged_in", "message": translator.gettext("You have logged in successfully."), "csrf_token": csrf_token}


@router.post("/refresh")
def refresh(request: Request, response: Response, db: Session = Depends(get_db), translator: Translator = Depends(get_translator)):
    token = request.cookies.get(REFRESH_COOKIE)
    try:
        claims = decode_token(token, "refresh")
    except AuthError as error:
        raise AuthError(error.code, clear=True) from None
    sid, uid = claims["sid"], int(claims["sub"])
    session = db.get(AuthSession, sid)
    now = int(time.time())
    if (session is None or session.user_id != uid or session.revoked
            or session.expires_at <= now or db.get(User, uid) is None):
        raise AuthError("session_invalid", clear=True)
    check_session_csrf(request, session)
    expires = session.expires_at
    new_refresh = issue_token("refresh", str(uid), sid, expires)
    # Compare-and-swap: at most one request can consume a refresh token.
    result = db.execute(update(AuthSession).where(
        AuthSession.id == sid, AuthSession.refresh_hash == digest(token),
        AuthSession.revoked.is_(False), AuthSession.expires_at > now,
    ).values(refresh_hash=digest(new_refresh)))
    if result.rowcount != 1:
        db.execute(update(AuthSession).where(AuthSession.id == sid).values(revoked=True))
        db.commit()
        raise AuthError("refresh_reused", clear=True)
    db.commit()
    access = issue_token("access", str(uid), sid, min(now + get_settings().access_seconds, expires))
    set_session_cookies(response, access, new_refresh, request.cookies[CSRF_COOKIE], expires)
    return {"code": "session_renewed", "message": translator.gettext("Your session has been renewed.")}


@router.post("/logout", status_code=204)
def logout(request: Request, db: Session = Depends(get_db), translator: Translator = Depends(get_translator)):
    # Accept an expired but correctly signed token solely to revoke its session.
    for cookie, kind in ((REFRESH_COOKIE, "refresh"), (ACCESS_COOKIE, "access")):
        try:
            claims = decode_token(request.cookies.get(cookie), kind, allow_expired=True)
        except AuthError:
            continue
        session = db.get(AuthSession, claims["sid"])
        if session is not None and session.user_id == int(claims["sub"]):
            check_session_csrf(request, session)
            db.execute(update(AuthSession).where(AuthSession.id == session.id).values(revoked=True))
    db.commit()
    response = Response(status_code=204)
    clear_cookies(response)
    return response


@router.get("/me")
def me(user: User = Depends(current_user)):
    return {"id": user.id, "username": user.username}

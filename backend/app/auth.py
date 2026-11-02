from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Response
from sqlalchemy import delete, func, select, update

from .config import get_settings
from .dependencies import AuthenticatedUser, DB
from .enums import Role, UserStatus
from .errors import APIError
from .models import LoginThrottle, Session, User
from .schemas import ChangePasswordIn, LoginIn, UserOut
from .security import hash_password, hash_session_token, issue_session_token, normalize_login, session_expiry, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookie(response: Response, token: str, expiry: datetime) -> None:
    settings = get_settings()
    response.set_cookie(
        settings.session_cookie_name,
        token,
        httponly=True,
        secure=settings.cookie_secure or settings.is_production,
        samesite="lax",
        expires=expiry,
        path="/",
    )


@router.post("/login")
async def login(payload: LoginIn, response: Response, db: DB):
    settings = get_settings()
    login_identifier = normalize_login(payload.login_identifier)
    now = datetime.now(UTC)
    window = timedelta(seconds=settings.login_failure_window_seconds)
    throttle_key = hash_session_token(f"login:{login_identifier}")
    # A transaction-scoped advisory lock serializes this identifier even when
    # no throttle row exists yet. Counters therefore work across API workers.
    advisory_key = int(throttle_key[:16], 16) & ((1 << 63) - 1)
    await db.execute(select(func.pg_advisory_xact_lock(advisory_key)))
    throttle = await db.scalar(
        select(LoginThrottle).where(LoginThrottle.key_hash == throttle_key).with_for_update()
    )
    if throttle and throttle.window_started_at > now - window and throttle.failure_count >= settings.login_max_failures:
        retry_after = max(1, int((throttle.window_started_at + window - now).total_seconds()) + 1)
        await db.rollback()
        raise APIError(
            429,
            "login_rate_limited",
            "Too many failed login attempts. Try again later.",
            {"retry_after_seconds": retry_after},
        )
    # Serialize successful login with teacher-driven deactivation/password
    # reset so a session cannot be created just after the reset transaction
    # revokes the account's existing sessions.
    user = await db.scalar(
        select(User)
        .where(User.login_identifier == login_identifier)
        .with_for_update()
    )
    if not user or user.status != UserStatus.ACTIVE or not verify_password(payload.password, user.password_hash):
        if throttle is None:
            db.add(LoginThrottle(key_hash=throttle_key, failure_count=1, window_started_at=now, updated_at=now))
        elif throttle.window_started_at <= now - window:
            throttle.failure_count, throttle.window_started_at, throttle.updated_at = 1, now, now
        else:
            throttle.failure_count += 1
            throttle.updated_at = now
        await db.commit()
        # Cleanup runs only after the counter transaction releases its account
        # lock. This avoids opposite row-lock ordering between simultaneous
        # failures for different identifiers.
        try:
            await db.execute(delete(LoginThrottle).where(LoginThrottle.updated_at < now - (window * 2)))
            await db.commit()
        except Exception:
            await db.rollback()
        raise APIError(401, "invalid_credentials", "Invalid login credentials")
    if throttle is not None:
        await db.delete(throttle)
    token, token_hash = issue_session_token()
    expiry = session_expiry()
    db.add(Session(token_hash=token_hash, user_id=user.id, expires_at=expiry))
    await db.commit()
    _set_session_cookie(response, token, expiry)
    return {"user": UserOut.model_validate(user)}


@router.post("/logout", status_code=204)
async def logout(response: Response, db: DB, user: AuthenticatedUser):
    settings = get_settings()
    # Revoke all active sessions for this account; this avoids token exposure in handler arguments.
    await db.execute(update(Session).where(Session.user_id == user.id, Session.revoked_at.is_(None)).values(revoked_at=datetime.now(UTC)))
    await db.commit()
    response.delete_cookie(settings.session_cookie_name, path="/")


@router.get("/me")
async def me(user: AuthenticatedUser):
    return {"user": UserOut.model_validate(user)}


@router.post("/change-password")
async def change_password(
    payload: ChangePasswordIn,
    response: Response,
    db: DB,
    authenticated: AuthenticatedUser,
):
    if authenticated.role != Role.STUDENT:
        raise APIError(403, "student_required", "Student access is required")

    # Serialize with login, deactivation, email changes, and teacher resets.
    user = await db.scalar(
        select(User)
        .where(User.id == authenticated.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if user is None or user.role != Role.STUDENT or user.status != UserStatus.ACTIVE:
        await db.rollback()
        raise APIError(401, "invalid_session", "The session is invalid or expired")
    if not verify_password(payload.current_password, user.password_hash):
        await db.rollback()
        raise APIError(400, "invalid_current_password", "Current password is incorrect")
    if verify_password(payload.new_password, user.password_hash):
        await db.rollback()
        raise APIError(
            422,
            "password_reuse_not_allowed",
            "New password must be different from the current password",
        )

    now = datetime.now(UTC)
    user.password_hash = hash_password(payload.new_password)
    user.must_change_password = False
    user.updated_at = now
    await db.execute(
        update(Session)
        .where(Session.user_id == user.id, Session.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    token, token_hash = issue_session_token()
    expiry = session_expiry()
    db.add(Session(token_hash=token_hash, user_id=user.id, expires_at=expiry))
    await db.commit()
    await db.refresh(user)

    _set_session_cookie(response, token, expiry)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return {"user": UserOut.model_validate(user)}

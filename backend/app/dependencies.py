from datetime import UTC, datetime
from typing import Annotated

from fastapi import Cookie, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .config import get_settings
from .database import get_db
from .enums import Role, UserStatus
from .errors import APIError
from .models import Session, User
from .security import hash_session_token

DB = Annotated[AsyncSession, Depends(get_db)]


async def authenticated_user(
    db: DB,
    session_token: Annotated[str | None, Cookie(alias=get_settings().session_cookie_name)] = None,
) -> User:
    if not session_token:
        raise APIError(401, "not_authenticated", "Authentication is required")
    row = await db.execute(
        select(Session, User)
        .join(User, User.id == Session.user_id)
        .where(Session.token_hash == hash_session_token(session_token), Session.revoked_at.is_(None))
    )
    value = row.first()
    if not value:
        raise APIError(401, "invalid_session", "The session is invalid or expired")
    session, user = value
    if session.expires_at <= datetime.now(UTC) or user.status != UserStatus.ACTIVE:
        raise APIError(401, "invalid_session", "The session is invalid or expired")
    return user


AuthenticatedUser = Annotated[User, Depends(authenticated_user)]


async def current_user(user: AuthenticatedUser) -> User:
    if user.role == Role.STUDENT and user.must_change_password:
        raise APIError(
            403,
            "password_change_required",
            "You must change your temporary password before continuing",
        )
    return user


CurrentUser = Annotated[User, Depends(current_user)]


async def teacher(user: CurrentUser) -> User:
    if user.role != Role.TEACHER:
        raise APIError(403, "teacher_required", "Teacher access is required")
    return user


async def student(user: CurrentUser) -> User:
    if user.role != Role.STUDENT:
        raise APIError(403, "student_required", "Student access is required")
    return user


Teacher = Annotated[User, Depends(teacher)]
Student = Annotated[User, Depends(student)]

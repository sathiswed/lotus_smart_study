from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Query, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError

from .dependencies import DB, Teacher
from .enums import Role, UserStatus
from .errors import APIError
from .models import Curriculum, Session, StudentProfile, User
from .security import hash_password


router = APIRouter(prefix="/teacher/students", tags=["student-management"])

EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MOBILE_PATTERN = re.compile(r"^\+?[0-9]{7,15}$")


def _clean_name(value: str) -> str:
    cleaned = " ".join(value.split())
    if not cleaned:
        raise ValueError("Name is required")
    return cleaned


def _clean_email(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    cleaned = value.strip().casefold()
    if len(cleaned) > 320:
        raise ValueError("Email must be 320 characters or fewer")
    if not EMAIL_PATTERN.fullmatch(cleaned):
        raise ValueError("Enter a valid email address")
    return cleaned


def _clean_mobile(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    cleaned = re.sub(r"[\s().-]", "", value)
    if not MOBILE_PATTERN.fullmatch(cleaned):
        raise ValueError("Enter a valid mobile number with 7 to 15 digits")
    return cleaned


def _clean_optional_text(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    return " ".join(value.split())


class StudentCreateIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: str = Field(max_length=320)
    mobile: str | None = Field(default=None, max_length=32)
    school_name: str | None = Field(default=None, max_length=255)
    school_location: str | None = Field(default=None, max_length=255)
    curriculum_id: uuid.UUID | None = None
    class_level: int = Field(default=8, ge=8, le=12)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        return _clean_name(value)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        cleaned = _clean_email(value)
        if cleaned is None:
            raise ValueError("Email is required")
        return cleaned

    @field_validator("mobile")
    @classmethod
    def validate_mobile(cls, value: str | None) -> str | None:
        return _clean_mobile(value)

    @field_validator("school_name", "school_location")
    @classmethod
    def validate_school_text(cls, value: str | None) -> str | None:
        return _clean_optional_text(value)

class StudentUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    email: str | None = Field(default=None, max_length=320)
    mobile: str | None = Field(default=None, max_length=32)
    school_name: str | None = Field(default=None, max_length=255)
    school_location: str | None = Field(default=None, max_length=255)
    curriculum_id: uuid.UUID | None = None
    class_level: int | None = Field(default=None, ge=8, le=12)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("Name cannot be null")
        return _clean_name(value)

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        if value is None:
            raise ValueError("Email cannot be null")
        cleaned = _clean_email(value)
        if cleaned is None:
            raise ValueError("Email is required")
        return cleaned

    @field_validator("mobile")
    @classmethod
    def validate_mobile(cls, value: str | None) -> str | None:
        return _clean_mobile(value)

    @field_validator("school_name", "school_location")
    @classmethod
    def validate_school_text(cls, value: str | None) -> str | None:
        return _clean_optional_text(value)

def _student_payload(user: User, profile: StudentProfile, curriculum: Curriculum) -> dict:
    return {
        "id": user.id,
        "name": user.name,
        "login_identifier": user.login_identifier,
        "email": profile.email,
        "mobile": profile.mobile,
        "school_name": profile.school_name,
        "school_location": profile.school_location,
        "class_level": profile.class_level,
        "curriculum_id": curriculum.id,
        "board": curriculum.board,
        "state_code": curriculum.state_code,
        "status": user.status,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
    }


def _temporary_password(name: str) -> str:
    first_name = _clean_name(name).split()[0].casefold()
    return f"{first_name}123A#"


async def _email_in_use(
    db: DB, email: str, *, excluding_user_id: uuid.UUID | None = None
) -> bool:
    user_statement = select(User.id).where(func.lower(User.login_identifier) == email)
    profile_statement = select(StudentProfile.user_id).where(
        func.lower(StudentProfile.email) == email
    )
    if excluding_user_id is not None:
        user_statement = user_statement.where(User.id != excluding_user_id)
        profile_statement = profile_statement.where(
            StudentProfile.user_id != excluding_user_id
        )
    return (
        await db.scalar(user_statement) is not None
        or await db.scalar(profile_statement) is not None
    )


def _email_conflict() -> APIError:
    return APIError(
        409,
        "student_email_conflict",
        "A user with this email address already exists",
    )


async def _student_row(
    db: DB, student_id: uuid.UUID, *, lock: bool = False
) -> tuple[User, StudentProfile, Curriculum]:
    statement = (
        select(User, StudentProfile, Curriculum)
        .join(StudentProfile, StudentProfile.user_id == User.id)
        .join(Curriculum, Curriculum.id == StudentProfile.curriculum_id)
        .where(User.id == student_id, User.role == Role.STUDENT)
    )
    if lock:
        statement = statement.with_for_update()
    row = (await db.execute(statement)).first()
    if row is None:
        raise APIError(404, "student_not_found", "Student not found")
    return row[0], row[1], row[2]


async def _resolve_curriculum(db: DB, curriculum_id: uuid.UUID | None, class_level: int) -> Curriculum:
    if curriculum_id is None:
        curriculum = await db.scalar(
            select(Curriculum).where(Curriculum.board == "cbse", Curriculum.class_level == 8, Curriculum.state_code.is_(None))
        )
    else:
        curriculum = await db.get(Curriculum, curriculum_id)
    if curriculum is None:
        raise APIError(422, "invalid_curriculum", "Select a configured board and class curriculum")
    if curriculum.class_level != class_level:
        raise APIError(422, "curriculum_class_mismatch", "Student class must match the selected curriculum")
    return curriculum


async def _revoke_sessions(db: DB, student_id: uuid.UUID, now: datetime) -> None:
    await db.execute(
        update(Session)
        .where(Session.user_id == student_id, Session.revoked_at.is_(None))
        .values(revoked_at=now)
    )


@router.get("")
async def list_students(
    db: DB,
    _: Teacher,
    search: str | None = Query(default=None, max_length=200),
    status_filter: UserStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    filters = [User.role == Role.STUDENT]
    if status_filter is not None:
        filters.append(User.status == status_filter)
    if search and search.strip():
        term = search.strip().casefold()
        filters.append(
            or_(
                func.lower(User.name).contains(term, autoescape=True),
                User.login_identifier.contains(term, autoescape=True),
            )
        )
    total = int(
        await db.scalar(
            select(func.count())
            .select_from(User)
            .join(StudentProfile, StudentProfile.user_id == User.id)
            .join(Curriculum, Curriculum.id == StudentProfile.curriculum_id)
            .where(*filters)
        )
        or 0
    )
    rows = (
        await db.execute(
            select(User, StudentProfile, Curriculum)
            .join(StudentProfile, StudentProfile.user_id == User.id)
            .join(Curriculum, Curriculum.id == StudentProfile.curriculum_id)
            .where(*filters)
            .order_by(User.name, User.created_at, User.id)
            .limit(limit)
            .offset(offset)
        )
    ).all()
    return {
        "items": [_student_payload(user, profile, curriculum) for user, profile, curriculum in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.post("", status_code=201)
async def create_student(
    payload: StudentCreateIn, response: Response, db: DB, _: Teacher
):
    if await _email_in_use(db, payload.email):
        raise _email_conflict()
    curriculum = await _resolve_curriculum(db, payload.curriculum_id, payload.class_level)
    temporary_password = _temporary_password(payload.name)
    password_hash = hash_password(temporary_password)
    user = User(
        name=payload.name,
        login_identifier=payload.email,
        password_hash=password_hash,
        role=Role.STUDENT,
        status=UserStatus.ACTIVE,
        must_change_password=True,
    )
    try:
        async with db.begin_nested():
            db.add(user)
            await db.flush()
            profile = StudentProfile(
                user_id=user.id,
                curriculum_id=curriculum.id,
                class_level=payload.class_level,
                email=payload.email,
                mobile=payload.mobile,
                school_name=payload.school_name,
                school_location=payload.school_location,
            )
            db.add(profile)
            await db.flush()
    except IntegrityError:
        await db.rollback()
        raise _email_conflict()
    await db.commit()
    await db.refresh(user)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return {
        "student": _student_payload(user, profile, curriculum),
        "temporary_password": temporary_password,
    }


@router.get("/{student_id}")
async def get_student(student_id: uuid.UUID, db: DB, _: Teacher):
    user, profile, curriculum = await _student_row(db, student_id)
    return {"student": _student_payload(user, profile, curriculum)}


@router.patch("/{student_id}")
async def update_student(
    student_id: uuid.UUID, payload: StudentUpdateIn, db: DB, _: Teacher
):
    user, profile, curriculum = await _student_row(db, student_id, lock=True)
    changes = payload.model_dump(exclude_unset=True)
    is_email_login = (
        profile.email is not None
        and user.login_identifier == profile.email.casefold()
    )
    if not is_email_login and "email" not in changes:
        await db.rollback()
        raise APIError(
            422,
            "student_email_required",
            "Email is required before this legacy account can be edited",
        )
    if "email" in changes and await _email_in_use(
        db, changes["email"], excluding_user_id=user.id
    ):
        await db.rollback()
        raise _email_conflict()

    now = datetime.now(UTC)
    login_changed = False
    if "name" in changes:
        user.name = changes["name"]
    if "email" in changes:
        profile.email = changes["email"]
        if user.login_identifier != changes["email"]:
            user.login_identifier = changes["email"]
            login_changed = True
    if "mobile" in changes:
        profile.mobile = changes["mobile"]
    if "school_name" in changes:
        profile.school_name = changes["school_name"]
    if "school_location" in changes:
        profile.school_location = changes["school_location"]
    if "curriculum_id" in changes or "class_level" in changes:
        selected_class = changes.get("class_level", profile.class_level)
        curriculum = await _resolve_curriculum(db, changes.get("curriculum_id", profile.curriculum_id), selected_class)
        profile.curriculum_id = curriculum.id
        profile.class_level = curriculum.class_level
    if changes:
        user.updated_at = now
    if login_changed:
        await _revoke_sessions(db, user.id, now)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise _email_conflict()
    await db.refresh(user)
    return {"student": _student_payload(user, profile, curriculum)}


@router.post("/{student_id}/activate")
async def activate_student(student_id: uuid.UUID, db: DB, _: Teacher):
    user, profile, curriculum = await _student_row(db, student_id, lock=True)
    user.status = UserStatus.ACTIVE
    user.updated_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(user)
    return {"student": _student_payload(user, profile, curriculum)}


@router.post("/{student_id}/deactivate")
async def deactivate_student(student_id: uuid.UUID, db: DB, _: Teacher):
    user, profile, curriculum = await _student_row(db, student_id, lock=True)
    now = datetime.now(UTC)
    user.status = UserStatus.INACTIVE
    user.updated_at = now
    await _revoke_sessions(db, user.id, now)
    await db.commit()
    await db.refresh(user)
    return {"student": _student_payload(user, profile, curriculum)}


@router.post("/{student_id}/reset-password")
async def reset_student_password(
    student_id: uuid.UUID, response: Response, db: DB, _: Teacher
):
    user, profile, curriculum = await _student_row(db, student_id, lock=True)
    temporary_password = _temporary_password(user.name)
    now = datetime.now(UTC)
    user.password_hash = hash_password(temporary_password)
    user.must_change_password = True
    user.updated_at = now
    await _revoke_sessions(db, user.id, now)
    await db.commit()
    await db.refresh(user)
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return {
        "student": _student_payload(user, profile, curriculum),
        "temporary_password": temporary_password,
    }

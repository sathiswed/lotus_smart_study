from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Response
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from .config import get_settings
from .dependencies import DB, Teacher
from .errors import APIError
from .models import Curriculum, SourceChunk, SourceDocument, Subject, Textbook
from .storage import run_storage, storage

router = APIRouter(prefix="/teacher/textbooks", tags=["textbook-management"])


def _normalized_code(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.strip().casefold()).strip("-")
    if not cleaned:
        raise ValueError("A normalized identifier is required")
    return cleaned


class TextbookUploadIn(BaseModel):
    board: Literal["cbse", "state", "icse"]
    state_code: str | None = Field(default=None, max_length=80)
    class_level: int = Field(ge=8, le=12)
    subject_code: str = Field(min_length=1, max_length=80)
    subject_title: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=1, max_length=255)
    academic_year: str | None = Field(default=None, max_length=40)
    edition: str = Field(default="current", min_length=1, max_length=80)
    file_name: str = Field(min_length=1, max_length=255)
    content_type: Literal["application/pdf"]
    byte_size: int = Field(gt=0)

    @field_validator("state_code", "subject_code")
    @classmethod
    def normalize_identifiers(cls, value: str | None) -> str | None:
        return _normalized_code(value) if value else None

    @field_validator("subject_title", "title", "edition", "academic_year")
    @classmethod
    def clean_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("Value cannot be blank")
        return cleaned

    @model_validator(mode="after")
    def validate_state(self):
        if self.board == "state" and not self.state_code:
            raise ValueError("State Board requires a state or curriculum identifier")
        if self.board != "state" and self.state_code:
            raise ValueError("State identifier is only valid for State Board")
        if Path(self.file_name).suffix.casefold() != ".pdf":
            raise ValueError("Textbook file must use the .pdf extension")
        return self


@router.get("")
async def list_managed_textbooks(db: DB, _: Teacher):
    rows = (
        await db.execute(
            select(Textbook, Subject, Curriculum, func.count(SourceChunk.id))
            .join(Subject, Subject.id == Textbook.subject_id)
            .join(Curriculum, Curriculum.id == Subject.curriculum_id)
            .outerjoin(SourceDocument, (SourceDocument.textbook_id == Textbook.id) & (SourceDocument.ingestion_status == "ready"))
            .outerjoin(SourceChunk, SourceChunk.source_document_id == SourceDocument.id)
            .group_by(Textbook.id, Subject.id, Curriculum.id)
            .order_by(Curriculum.board, Curriculum.class_level, Subject.title, Textbook.title)
        )
    ).all()
    return {"items": [_out(book, subject, curriculum, int(chunks or 0)) for book, subject, curriculum, chunks in rows]}


@router.post("/upload-url", status_code=201)
async def create_textbook_upload(payload: TextbookUploadIn, response: Response, db: DB, teacher: Teacher):
    settings = get_settings()
    if payload.byte_size > settings.textbook_max_bytes:
        raise APIError(422, "textbook_too_large", "Textbook exceeds the configured size limit")
    curriculum_code = f"{payload.board}-{payload.state_code + '-' if payload.state_code else ''}{payload.class_level}"
    curriculum = await db.scalar(select(Curriculum).where(Curriculum.code == curriculum_code))
    if curriculum is None:
        curriculum = Curriculum(
            code=curriculum_code,
            board=payload.board,
            state_code=payload.state_code,
            class_level=payload.class_level,
        )
        db.add(curriculum)
        await db.flush()
    subject = await db.scalar(
        select(Subject).where(Subject.curriculum_id == curriculum.id, Subject.code == payload.subject_code)
    )
    if subject is None:
        subject = Subject(curriculum_id=curriculum.id, code=payload.subject_code, title=payload.subject_title)
        db.add(subject)
        await db.flush()
    elif subject.title != payload.subject_title:
        raise APIError(409, "subject_title_conflict", "This subject identifier already uses a different title")

    existing = await db.scalar(
        select(Textbook.id).where(
            Textbook.subject_id == subject.id,
            func.lower(Textbook.title) == payload.title.casefold(),
            func.lower(Textbook.edition) == payload.edition.casefold(),
        )
    )
    if existing is not None:
        raise APIError(409, "textbook_exists", "This textbook title and edition already exist for the selected curriculum")
    textbook_id = uuid.uuid4()
    object_key = f"textbooks/{curriculum.code}/{subject.code}/{textbook_id}.pdf"
    textbook = Textbook(
        id=textbook_id,
        subject_id=subject.id,
        title=payload.title,
        academic_year=payload.academic_year,
        edition=payload.edition,
        object_key=object_key,
        processing_status="pending_upload",
        created_by=teacher.id,
    )
    db.add(textbook)
    try:
        await db.flush()
        upload_url = await run_storage(storage.create_upload_put, object_key, "application/pdf")
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise APIError(409, "textbook_exists", "This textbook already exists") from exc
    response.headers["Cache-Control"] = "no-store"
    return {
        "textbook": _out(textbook, subject, curriculum, 0),
        "upload_url": upload_url,
        "upload_method": "PUT",
        "required_headers": {"Content-Type": "application/pdf"},
        "expires_at": datetime.now(UTC) + timedelta(seconds=settings.s3_signed_url_seconds),
    }


@router.post("/{textbook_id}/complete")
async def complete_textbook_upload(textbook_id: uuid.UUID, db: DB, teacher: Teacher):
    row = (
        await db.execute(
            select(Textbook, Subject, Curriculum)
            .join(Subject, Subject.id == Textbook.subject_id)
            .join(Curriculum, Curriculum.id == Subject.curriculum_id)
            .where(Textbook.id == textbook_id, Textbook.created_by == teacher.id)
            .with_for_update(of=Textbook)
        )
    ).one_or_none()
    if row is None:
        raise APIError(404, "textbook_not_found", "Textbook upload not found")
    textbook, subject, curriculum = row
    if textbook.processing_status in {"uploaded", "processing", "ready"}:
        return {"textbook": _out(textbook, subject, curriculum, 0)}
    if not textbook.object_key:
        raise APIError(409, "textbook_upload_missing", "Textbook upload does not have a private object key")
    try:
        verified = await run_storage(storage.verify_uploaded_pdf, textbook.object_key)
    except APIError as exc:
        textbook.processing_status = "failed"
        textbook.failure_reason = exc.message
        await db.commit()
        try:
            await run_storage(storage.delete, textbook.object_key)
        except Exception:
            pass
        raise exc
    textbook.checksum = verified.checksum
    textbook.processing_status = "uploaded"
    textbook.failure_reason = None
    await db.commit()
    return {
        "textbook": _out(textbook, subject, curriculum, 0),
        "page_count": verified.page_count,
        "message": "Upload verified. Chapter extraction and indexing must complete before generation is enabled.",
    }


def _out(book: Textbook, subject: Subject, curriculum: Curriculum, chunks: int) -> dict:
    return {
        "id": book.id,
        "subject_id": subject.id,
        "subject_code": subject.code,
        "subject_title": subject.title,
        "curriculum_id": curriculum.id,
        "board": curriculum.board,
        "state_code": curriculum.state_code,
        "class_level": curriculum.class_level,
        "title": book.title,
        "academic_year": book.academic_year,
        "edition": book.edition,
        "processing_status": book.processing_status,
        "failure_reason": book.failure_reason,
        "content_available": book.processing_status == "ready" and chunks > 0,
        "indexed_chunk_count": chunks,
    }

from __future__ import annotations

import hashlib
import logging
import re
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Response
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from .config import get_settings
from .dependencies import DB, Teacher
from .errors import APIError
from .generation.ingestion import build_page_chunks, detect_pdf_chapters, extract_pdf_pages
from .models import (
    Chapter, Curriculum, GenerationBatch, Question, SourceChunk, SourceDocument,
    Subject, Term, Textbook, TextbookFile, Topic,
)
from .storage import run_storage, storage

router = APIRouter(prefix="/teacher/textbooks", tags=["textbook-management"])
logger = logging.getLogger(__name__)


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


class TextbookCatalogIn(BaseModel):
    board: Literal["cbse", "state", "icse"]
    state_code: str | None = Field(default=None, max_length=80)
    class_level: int = Field(ge=8, le=12)
    subject_code: str = Field(min_length=1, max_length=80)
    subject_title: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=1, max_length=255)
    academic_year: str | None = Field(default=None, max_length=40)
    edition: str = Field(default="current", min_length=1, max_length=80)

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
        return self


class TermCreateIn(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    title: str = Field(min_length=1, max_length=80)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return _normalized_code(value).replace("-", "_")

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        return " ".join(value.split())


class TextbookFileUploadIn(BaseModel):
    term_id: uuid.UUID
    file_name: str = Field(min_length=1, max_length=255)
    content_type: Literal["application/pdf"]
    byte_size: int = Field(gt=0)

    @field_validator("file_name")
    @classmethod
    def validate_pdf_name(cls, value: str) -> str:
        cleaned = Path(value).name
        if Path(cleaned).suffix.casefold() != ".pdf":
            raise ValueError("Textbook file must use the .pdf extension")
        return cleaned


class ChapterApprovalIn(BaseModel):
    code: str = Field(min_length=1, max_length=20)
    title: str = Field(min_length=1, max_length=255)
    page_start: int = Field(ge=1)
    page_end: int = Field(ge=1)

    @field_validator("code")
    @classmethod
    def clean_code(cls, value: str) -> str:
        cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip()).strip("-")
        if not cleaned:
            raise ValueError("Chapter number is required")
        return cleaned.casefold()

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        cleaned = " ".join(value.split())
        if not cleaned:
            raise ValueError("Chapter title is required")
        return cleaned

    @model_validator(mode="after")
    def validate_pages(self):
        if self.page_end < self.page_start:
            raise ValueError("Chapter end page must not precede its start page")
        return self


class FinalizeTextbookFileIn(BaseModel):
    chapters: list[ChapterApprovalIn] = Field(min_length=1, max_length=100)


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


@router.post("/catalog", status_code=201)
async def create_textbook_catalog(payload: TextbookCatalogIn, db: DB, teacher: Teacher):
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
        select(Subject).where(
            Subject.curriculum_id == curriculum.id,
            Subject.code == payload.subject_code,
        )
    )
    if subject is None:
        subject = Subject(
            curriculum_id=curriculum.id,
            code=payload.subject_code,
            title=payload.subject_title,
        )
        db.add(subject)
        await db.flush()
    elif subject.title.casefold() != payload.subject_title.casefold():
        raise APIError(409, "subject_title_conflict", "This subject identifier already uses a different title")
    textbook = await db.scalar(
        select(Textbook).where(
            Textbook.subject_id == subject.id,
            func.lower(Textbook.title) == payload.title.casefold(),
            func.lower(Textbook.edition) == payload.edition.casefold(),
        )
    )
    if textbook is not None:
        return {"textbook": _out(textbook, subject, curriculum, 0), "created": False}
    textbook = Textbook(
        subject_id=subject.id,
        title=payload.title,
        academic_year=payload.academic_year,
        edition=payload.edition,
        processing_status="pending_upload",
        created_by=teacher.id,
    )
    db.add(textbook)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise APIError(409, "textbook_exists", "This textbook already exists") from exc
    await db.refresh(textbook)
    return {"textbook": _out(textbook, subject, curriculum, 0), "created": True}


@router.post("/{textbook_id}/terms", status_code=201)
async def create_textbook_term(
    textbook_id: uuid.UUID,
    payload: TermCreateIn,
    db: DB,
    _: Teacher,
):
    textbook = await db.get(Textbook, textbook_id)
    if textbook is None:
        raise APIError(404, "textbook_not_found", "Textbook not found")
    term = await db.scalar(
        select(Term).where(Term.subject_id == textbook.subject_id, Term.code == payload.code)
    )
    if term is not None:
        if term.title.casefold() != payload.title.casefold():
            raise APIError(409, "term_title_conflict", "This term identifier already uses a different title")
        return {"term": _term_out(term), "created": False}
    maximum = await db.scalar(select(func.max(Term.sequence)).where(Term.subject_id == textbook.subject_id)) or 0
    term = Term(
        subject_id=textbook.subject_id,
        code=payload.code,
        title=payload.title,
        sequence=maximum + 1,
    )
    db.add(term)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise APIError(409, "term_exists", "This term already exists") from exc
    await db.refresh(term)
    return {"term": _term_out(term), "created": True}


@router.get("/{textbook_id}/files")
async def list_textbook_files(
    textbook_id: uuid.UUID,
    db: DB,
    _: Teacher,
    term_id: uuid.UUID | None = None,
):
    if await db.get(Textbook, textbook_id) is None:
        raise APIError(404, "textbook_not_found", "Textbook not found")
    statement = select(TextbookFile).where(TextbookFile.textbook_id == textbook_id)
    if term_id is not None:
        statement = statement.where(TextbookFile.term_id == term_id)
    files = (await db.scalars(statement.order_by(TextbookFile.created_at, TextbookFile.id))).all()
    return {"items": [_file_out(item) for item in files]}


@router.post("/{textbook_id}/files/upload-url", status_code=201)
async def create_textbook_file_upload(
    textbook_id: uuid.UUID,
    payload: TextbookFileUploadIn,
    response: Response,
    db: DB,
    teacher: Teacher,
):
    settings = get_settings()
    if payload.byte_size > settings.textbook_max_bytes:
        raise APIError(422, "textbook_too_large", "Textbook PDF exceeds the configured per-file size limit")
    textbook, subject, curriculum = await _textbook_scope(db, textbook_id)
    term = await db.get(Term, payload.term_id)
    if term is None or term.subject_id != subject.id:
        raise APIError(422, "invalid_term_scope", "Term does not belong to the selected textbook subject")
    file_id = uuid.uuid4()
    object_key = (
        f"textbooks/{curriculum.code}/{subject.code}/{textbook.id}/"
        f"{term.code}/{file_id}.pdf"
    )
    textbook_file = TextbookFile(
        id=file_id,
        textbook_id=textbook.id,
        term_id=term.id,
        original_filename=payload.file_name,
        object_key=object_key,
        byte_size=payload.byte_size,
        status="uploading",
        created_by=teacher.id,
    )
    db.add(textbook_file)
    await db.flush()
    upload_url = await run_storage(storage.create_upload_put, object_key, "application/pdf")
    if textbook.processing_status != "ready":
        textbook.processing_status = "processing"
        textbook.failure_reason = None
    await db.commit()
    response.headers["Cache-Control"] = "no-store"
    return {
        "file": _file_out(textbook_file),
        "upload_url": upload_url,
        "upload_method": "PUT",
        "required_headers": {"Content-Type": "application/pdf"},
        "expires_at": datetime.now(UTC) + timedelta(seconds=settings.s3_signed_url_seconds),
    }


@router.post("/{textbook_id}/files/{file_id}/complete")
async def complete_textbook_file(
    textbook_id: uuid.UUID,
    file_id: uuid.UUID,
    db: DB,
    teacher: Teacher,
):
    textbook_file = await _owned_file(db, textbook_id, file_id, teacher.id, lock=True)
    return await _detect_file(db, textbook_file)


@router.post("/{textbook_id}/files/{file_id}/detect")
async def retry_textbook_file_detection(
    textbook_id: uuid.UUID,
    file_id: uuid.UUID,
    db: DB,
    teacher: Teacher,
):
    textbook_file = await _owned_file(db, textbook_id, file_id, teacher.id, lock=True)
    if textbook_file.status == "ready":
        return await _replace_unused_file_index(db, textbook_file)
    return await _detect_file(db, textbook_file)


@router.post("/{textbook_id}/files/{file_id}/finalize")
async def finalize_textbook_file(
    textbook_id: uuid.UUID,
    file_id: uuid.UUID,
    payload: FinalizeTextbookFileIn,
    db: DB,
    teacher: Teacher,
):
    textbook_file = await _owned_file(db, textbook_id, file_id, teacher.id, lock=True)
    approved = [
        item.model_dump()
        for item in sorted(payload.chapters, key=lambda value: (value.page_start, value.code))
    ]
    if textbook_file.status == "ready":
        if textbook_file.approved_chapters == approved:
            return {"file": _file_out(textbook_file), "indexed": False}
        raise APIError(409, "textbook_file_finalized", "A finalized textbook file is immutable")
    if textbook_file.page_count is None or textbook_file.checksum is None:
        raise APIError(409, "textbook_file_not_detected", "Complete chapter detection before finalizing")
    _validate_approved_chapters(payload.chapters, textbook_file.page_count)
    textbook, subject, curriculum = await _textbook_scope(db, textbook_id)
    term = await db.get(Term, textbook_file.term_id)
    if term is None or term.subject_id != subject.id:
        raise APIError(409, "invalid_term_scope", "Textbook file term ancestry is invalid")

    try:
        verified = await run_storage(storage.verify_uploaded_pdf, textbook_file.object_key)
    except APIError as exc:
        textbook_file.status = "failed"
        textbook_file.failure_reason = exc.message
        await db.commit()
        raise
    if verified.checksum != textbook_file.checksum:
        textbook_file.status = "failed"
        textbook_file.failure_reason = "Uploaded PDF changed after chapter detection"
        await db.commit()
        raise APIError(409, "textbook_file_changed", "Uploaded PDF changed after chapter detection")
    try:
        pages = extract_pdf_pages(verified.data)
    except ValueError as exc:
        textbook_file.status = "failed"
        textbook_file.failure_reason = str(exc)
        await db.commit()
        raise APIError(422, "textbook_extraction_failed", str(exc)) from exc

    existing_by_code = {
        chapter.code: chapter
        for chapter in (
            await db.scalars(
                select(Chapter).where(
                    Chapter.textbook_id == textbook.id,
                    Chapter.term_id == term.id,
                    Chapter.code.in_([item.code for item in payload.chapters]),
                )
            )
        ).all()
    }
    for item in payload.chapters:
        existing = existing_by_code.get(item.code)
        if existing is None:
            continue
        source_row = (
            await db.execute(
                select(SourceDocument.textbook_file_id, TextbookFile.original_filename)
                .outerjoin(TextbookFile, TextbookFile.id == SourceDocument.textbook_file_id)
                .where(SourceDocument.chapter_id == existing.id)
                .limit(1)
            )
        ).one_or_none()
        if source_row is None or source_row[0] != textbook_file.id:
            source_name = source_row[1] if source_row and source_row[1] else "an existing indexed source"
            raise APIError(
                409,
                "duplicate_chapter",
                f"Chapter {item.code} already exists for this textbook and term from {source_name}. Re-detect or correct this file's chapter number before approving.",
                {"chapter_id": str(existing.id), "source_file": source_row[1] if source_row else None},
            )

    textbook_file.status = "indexing"
    textbook_file.failure_reason = None
    await db.flush()
    next_sequence = int(
        await db.scalar(
            select(func.coalesce(func.max(Chapter.sequence), 0)).where(
                Chapter.textbook_id == textbook.id,
                Chapter.term_id == term.id,
            )
        )
        or 0
    )
    for item in sorted(payload.chapters, key=lambda value: (value.page_start, value.code)):
        chapter = existing_by_code.get(item.code)
        if chapter is None:
            next_sequence += 1
            chapter = Chapter(
                textbook_id=textbook.id,
                term_id=term.id,
                code=item.code,
                title=item.title,
                sequence=next_sequence,
            )
            db.add(chapter)
            await db.flush()
        else:
            chapter.title = item.title
        page_chunks = build_page_chunks(pages, item.page_start, item.page_end)
        if not page_chunks:
            await db.rollback()
            failed = await db.get(TextbookFile, file_id)
            if failed is not None:
                failed.status = "failed"
                failed.failure_reason = f"Chapter {item.code} contains no extractable text"
                await db.commit()
            raise APIError(422, "chapter_content_empty", f"Chapter {item.code} contains no extractable text")
        source_document = await db.scalar(
            select(SourceDocument).where(
                SourceDocument.textbook_file_id == textbook_file.id,
                SourceDocument.chapter_id == chapter.id,
            )
        )
        chapter_text = "\n".join(pages[item.page_start - 1 : item.page_end])
        chapter_checksum = hashlib.sha256(chapter_text.encode("utf-8")).hexdigest()
        if source_document is None:
            source_document = SourceDocument(
                id=uuid.uuid5(textbook_file.id, f"source:{item.code}"),
                textbook_file_id=textbook_file.id,
                textbook_id=textbook.id,
                term_id=term.id,
                chapter_id=chapter.id,
                topic_id=None,
                path=textbook_file.object_key,
                checksum=chapter_checksum,
                version=textbook_file.checksum[:16],
                ingestion_status="processing",
                document_metadata={},
            )
            db.add(source_document)
            await db.flush()
        else:
            await db.execute(delete(SourceChunk).where(SourceChunk.source_document_id == source_document.id))
            source_document.path = textbook_file.object_key
            source_document.checksum = chapter_checksum
            source_document.version = textbook_file.checksum[:16]
            source_document.ingestion_status = "processing"
        source_document.document_metadata = {
            "board": curriculum.board,
            "state_code": curriculum.state_code,
            "class_level": curriculum.class_level,
            "subject": subject.code,
            "textbook_id": str(textbook.id),
            "textbook_file_id": str(textbook_file.id),
            "original_filename": textbook_file.original_filename,
            "page_start": item.page_start,
            "page_end": item.page_end,
            "teacher_approved_chapter": True,
            "authoritative_pattern_corpus": False,
        }
        for chunk in page_chunks:
            db.add(
                SourceChunk(
                    id=uuid.uuid5(source_document.id, f"{chunk['sequence']}:{chunk['checksum']}"),
                    source_document_id=source_document.id,
                    textbook_id=textbook.id,
                    term_id=term.id,
                    chapter_id=chapter.id,
                    topic_id=None,
                    page_start=chunk["page_start"],
                    page_end=chunk["page_end"],
                    sequence=chunk["sequence"],
                    content=chunk["content"],
                    checksum=chunk["checksum"],
                    index_reference=None,
                )
            )
        source_document.ingestion_status = "ready"

    textbook_file.approved_chapters = approved
    textbook_file.status = "ready"
    textbook_file.failure_reason = None
    textbook.processing_status = "ready"
    textbook.failure_reason = None
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
        logger.warning(
            "textbook indexing conflict file_id=%s exception_type=%s constraint=%s",
            file_id,
            type(exc.orig).__name__,
            constraint or "unknown",
        )
        failed = await db.get(TextbookFile, file_id)
        if failed is not None and failed.status != "ready":
            failed.status = "failed"
            failed.failure_reason = _index_conflict_message(constraint)
            await db.commit()
        raise APIError(
            409,
            "textbook_index_conflict",
            _index_conflict_message(constraint),
            {"constraint": constraint} if constraint else None,
        ) from exc
    await db.refresh(textbook_file)
    return {"file": _file_out(textbook_file), "indexed": True}


@router.delete("/{textbook_id}/files/{file_id}", status_code=204)
async def delete_textbook_file(
    textbook_id: uuid.UUID,
    file_id: uuid.UUID,
    db: DB,
    teacher: Teacher,
):
    textbook_file = await _owned_file(db, textbook_id, file_id, teacher.id, lock=True)
    if textbook_file.status == "ready":
        raise APIError(409, "textbook_file_finalized", "Finalized textbook files cannot be deleted")
    object_key = textbook_file.object_key
    await db.delete(textbook_file)
    await db.commit()
    try:
        await run_storage(storage.delete, object_key)
    except Exception:
        pass
    return Response(status_code=204)


async def _textbook_scope(db: DB, textbook_id: uuid.UUID) -> tuple[Textbook, Subject, Curriculum]:
    row = (
        await db.execute(
            select(Textbook, Subject, Curriculum)
            .join(Subject, Subject.id == Textbook.subject_id)
            .join(Curriculum, Curriculum.id == Subject.curriculum_id)
            .where(Textbook.id == textbook_id)
        )
    ).one_or_none()
    if row is None:
        raise APIError(404, "textbook_not_found", "Textbook not found")
    return row[0], row[1], row[2]


async def _owned_file(
    db: DB,
    textbook_id: uuid.UUID,
    file_id: uuid.UUID,
    _teacher_id: uuid.UUID,
    *,
    lock: bool = False,
) -> TextbookFile:
    statement = select(TextbookFile).where(
        TextbookFile.id == file_id,
        TextbookFile.textbook_id == textbook_id,
    )
    if lock:
        statement = statement.with_for_update()
    textbook_file = await db.scalar(statement)
    if textbook_file is None:
        raise APIError(404, "textbook_file_not_found", "Textbook PDF not found")
    return textbook_file


async def _detect_file(db: DB, textbook_file: TextbookFile) -> dict:
    if textbook_file.status == "ready":
        return {"file": _file_out(textbook_file)}
    try:
        verified = await run_storage(storage.verify_uploaded_pdf, textbook_file.object_key)
    except APIError as exc:
        textbook_file.status = "failed"
        textbook_file.failure_reason = exc.message
        await db.commit()
        raise
    duplicate = await db.scalar(
        select(TextbookFile.id).where(
            TextbookFile.textbook_id == textbook_file.textbook_id,
            TextbookFile.term_id == textbook_file.term_id,
            TextbookFile.checksum == verified.checksum,
            TextbookFile.id != textbook_file.id,
        )
    )
    if duplicate is not None:
        textbook_file.status = "failed"
        textbook_file.failure_reason = "This PDF has already been uploaded for the selected textbook and term"
        await db.commit()
        raise APIError(409, "duplicate_textbook_file", textbook_file.failure_reason)
    try:
        pages = extract_pdf_pages(verified.data)
        detected = detect_pdf_chapters(pages)
    except ValueError as exc:
        textbook_file.checksum = verified.checksum
        textbook_file.page_count = verified.page_count
        textbook_file.status = "failed"
        textbook_file.failure_reason = str(exc)
        await db.commit()
        raise APIError(422, "textbook_detection_failed", str(exc)) from exc
    textbook_file.checksum = verified.checksum
    textbook_file.byte_size = verified.byte_size
    textbook_file.page_count = verified.page_count
    textbook_file.detected_chapters = [
        {
            "code": item.code,
            "title": item.title,
            "page_start": item.page_start,
            "page_end": item.page_end,
            "confidence": item.confidence,
        }
        for item in detected
    ]
    textbook_file.status = "review_required"
    textbook_file.failure_reason = None if detected else "No chapter heading was confidently detected; add the chapter details manually"
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        failed = await db.get(TextbookFile, textbook_file.id)
        if failed is not None:
            failed.checksum = None
            failed.status = "failed"
            failed.failure_reason = "This PDF has already been uploaded for the selected textbook and term"
            await db.commit()
        raise APIError(409, "duplicate_textbook_file", "This PDF has already been uploaded for the selected textbook and term") from exc
    await db.refresh(textbook_file)
    return {"file": _file_out(textbook_file)}


async def _replace_unused_file_index(db: DB, textbook_file: TextbookFile) -> dict:
    """Re-detect a finalized file only when its chapter index has no consumers."""
    try:
        verified = await run_storage(storage.verify_uploaded_pdf, textbook_file.object_key)
        pages = extract_pdf_pages(verified.data)
        detected = detect_pdf_chapters(pages)
    except APIError:
        raise
    except ValueError as exc:
        raise APIError(422, "textbook_detection_failed", str(exc)) from exc
    if not detected:
        raise APIError(
            422,
            "textbook_redetection_empty",
            "No reliable chapter boundary was detected. The existing index was left unchanged.",
        )

    documents = (
        await db.scalars(
            select(SourceDocument).where(SourceDocument.textbook_file_id == textbook_file.id)
        )
    ).all()
    chapter_ids = {document.chapter_id for document in documents}
    if chapter_ids:
        used_batch = await db.scalar(
            select(GenerationBatch.id).where(GenerationBatch.chapter_id.in_(chapter_ids)).limit(1)
        )
        used_question = await db.scalar(
            select(Question.id).where(Question.chapter_id.in_(chapter_ids)).limit(1)
        )
        configured_topic = await db.scalar(
            select(Topic.id).where(Topic.chapter_id.in_(chapter_ids)).limit(1)
        )
        if used_batch is not None or used_question is not None or configured_topic is not None:
            raise APIError(
                409,
                "textbook_file_index_in_use",
                "This file's chapters have already been used or configured and cannot be replaced automatically. Existing academic records were left unchanged.",
            )

    await db.execute(delete(SourceDocument).where(SourceDocument.textbook_file_id == textbook_file.id))
    await db.flush()
    for chapter_id in chapter_ids:
        another_document = await db.scalar(
            select(SourceDocument.id).where(SourceDocument.chapter_id == chapter_id).limit(1)
        )
        if another_document is None:
            chapter = await db.get(Chapter, chapter_id)
            if chapter is not None:
                await db.delete(chapter)

    textbook_file.checksum = verified.checksum
    textbook_file.byte_size = verified.byte_size
    textbook_file.page_count = verified.page_count
    textbook_file.detected_chapters = [
        {
            "code": item.code,
            "title": item.title,
            "page_start": item.page_start,
            "page_end": item.page_end,
            "confidence": item.confidence,
        }
        for item in detected
    ]
    textbook_file.approved_chapters = []
    textbook_file.status = "review_required"
    textbook_file.failure_reason = None
    await db.flush()

    remaining_ready_source = await db.scalar(
        select(SourceDocument.id).where(
            SourceDocument.textbook_id == textbook_file.textbook_id,
            SourceDocument.ingestion_status == "ready",
        ).limit(1)
    )
    if remaining_ready_source is None:
        textbook = await db.get(Textbook, textbook_file.textbook_id)
        if textbook is not None:
            textbook.processing_status = "processing"
            textbook.failure_reason = None
    await db.commit()
    await db.refresh(textbook_file)
    return {"file": _file_out(textbook_file), "replaced_index": True}


def _validate_approved_chapters(chapters: list[ChapterApprovalIn], page_count: int) -> None:
    codes = [item.code.casefold() for item in chapters]
    if len(codes) != len(set(codes)):
        raise APIError(422, "duplicate_chapter_in_file", "Chapter numbers must be unique within a PDF")
    ordered = sorted(chapters, key=lambda item: item.page_start)
    previous_end = 0
    for item in ordered:
        if item.page_end > page_count:
            raise APIError(422, "chapter_page_out_of_range", f"Chapter {item.code} exceeds the PDF page count")
        if item.page_start <= previous_end:
            raise APIError(422, "chapter_pages_overlap", "Approved chapter page ranges cannot overlap")
        previous_end = item.page_end


def _index_conflict_message(constraint: str | None) -> str:
    if constraint in {"uq_chapter_term_code", "uq_chapter_textbook_term_code"}:
        return "A chapter with this number already exists for the selected textbook and term. Re-detect or correct the chapter number before approving."
    if constraint == "uq_source_document_file_chapter":
        return "This PDF chapter has already been indexed. Re-detect the file before retrying."
    if constraint == "uq_source_chunk_sequence":
        return "This PDF produced repeated source chunks. Re-detect the file before retrying."
    return "Chapter indexing conflicted with existing textbook content. Re-detect the file and review its chapter numbers before retrying."


def _term_out(term: Term) -> dict:
    return {
        "id": term.id,
        "subject_id": term.subject_id,
        "code": term.code,
        "title": term.title,
        "sequence": term.sequence,
    }


def _file_out(item: TextbookFile) -> dict:
    return {
        "id": item.id,
        "textbook_id": item.textbook_id,
        "term_id": item.term_id,
        "original_filename": item.original_filename,
        "byte_size": item.byte_size,
        "page_count": item.page_count,
        "status": item.status,
        "detected_chapters": item.detected_chapters or [],
        "approved_chapters": item.approved_chapters or [],
        "failure_reason": item.failure_reason,
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }

import re
import uuid

from fastapi import APIRouter, Query
from sqlalchemy import func, select

from .dependencies import CurrentUser, DB
from .errors import APIError
from .models import Chapter, Curriculum, SourceChunk, SourceDocument, Subject, Term, Textbook, Topic

router = APIRouter(prefix="/curriculum", tags=["curriculum"])

BOARD_OPTIONS = (
    {"code": "cbse", "title": "CBSE", "requires_state": False},
    {"code": "state", "title": "State Board", "requires_state": True},
    {"code": "icse", "title": "ICSE", "requires_state": False},
)
CLASS_OPTIONS = tuple(range(8, 13))


def normalize_code(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.strip().casefold()).strip("-")


@router.get("/options")
async def curriculum_options(db: DB, _: CurrentUser):
    configured = (
        await db.scalars(
            select(Curriculum).order_by(Curriculum.board, Curriculum.state_code, Curriculum.class_level)
        )
    ).all()
    return {
        "boards": list(BOARD_OPTIONS),
        "classes": list(CLASS_OPTIONS),
        "configured_curricula": [_curriculum_out(item) for item in configured],
    }


@router.get("/subjects")
async def list_subjects(
    db: DB,
    _: CurrentUser,
    board: str = Query(min_length=1, max_length=20),
    class_level: int = Query(ge=8, le=12),
    state_code: str | None = Query(default=None, max_length=80),
):
    normalized_board = normalize_code(board)
    if normalized_board not in {item["code"] for item in BOARD_OPTIONS}:
        raise APIError(422, "unsupported_board", "Board must be CBSE, State Board, or ICSE")
    normalized_state = normalize_code(state_code) if state_code else None
    if normalized_board == "state" and not normalized_state:
        raise APIError(422, "state_required", "A state or curriculum identifier is required for State Board")
    if normalized_board != "state" and normalized_state:
        raise APIError(422, "state_not_applicable", "State identifier is only valid for State Board")
    curriculum = await db.scalar(
        select(Curriculum).where(
            Curriculum.board == normalized_board,
            Curriculum.class_level == class_level,
            Curriculum.state_code == normalized_state,
        )
    )
    if curriculum is None:
        return {"curriculum": None, "items": []}
    subjects = (
        await db.scalars(select(Subject).where(Subject.curriculum_id == curriculum.id).order_by(Subject.title))
    ).all()
    return {"curriculum": _curriculum_out(curriculum), "items": [_subject_out(item) for item in subjects]}


@router.get("/subjects/{subject_id}/textbooks")
async def list_textbooks(subject_id: uuid.UUID, db: DB, _: CurrentUser):
    if await db.get(Subject, subject_id) is None:
        raise APIError(404, "subject_not_found", "Subject not found")
    rows = (
        await db.execute(
            select(Textbook, func.count(func.distinct(SourceChunk.id)))
            .outerjoin(SourceDocument, SourceDocument.textbook_id == Textbook.id)
            .outerjoin(
                SourceChunk,
                (SourceChunk.textbook_id == Textbook.id)
                & (SourceChunk.source_document_id == SourceDocument.id)
                & (SourceDocument.ingestion_status == "ready"),
            )
            .where(Textbook.subject_id == subject_id)
            .group_by(Textbook.id)
            .order_by(Textbook.title)
        )
    ).all()
    return {"items": [_textbook_out(book, int(chunk_count or 0)) for book, chunk_count in rows]}


@router.get("/textbooks/{textbook_id}/chapters")
async def list_textbook_chapters(textbook_id: uuid.UUID, db: DB, _: CurrentUser):
    textbook = await db.get(Textbook, textbook_id)
    if textbook is None:
        raise APIError(404, "textbook_not_found", "Textbook not found")
    rows = (
        await db.execute(
            select(Chapter, Term, func.count(SourceDocument.id))
            .join(Term, Term.id == Chapter.term_id)
            .outerjoin(
                SourceChunk,
                (SourceChunk.chapter_id == Chapter.id)
                & (SourceChunk.textbook_id == textbook_id),
            )
            .outerjoin(SourceDocument, (SourceDocument.id == SourceChunk.source_document_id) & (SourceDocument.ingestion_status == "ready"))
            .where(
                Chapter.textbook_id == textbook_id,
                Term.subject_id == textbook.subject_id,
            )
            .group_by(Chapter.id, Term.id)
            .order_by(Term.sequence, Chapter.sequence)
        )
    ).all()
    return {
        "textbook": _textbook_out(textbook, sum(int(count or 0) for _, _, count in rows)),
        "items": [
            {
                "id": chapter.id,
                "textbook_id": chapter.textbook_id,
                "term_id": chapter.term_id,
                "term_title": term.title,
                "code": chapter.code,
                "title": chapter.title,
                "sequence": chapter.sequence,
                "content_available": int(chunk_count or 0) > 0,
            }
            for chapter, term, chunk_count in rows
        ],
    }


# Backward-compatible endpoints for the existing Class 8 clients and records.
@router.get("/terms")
async def list_terms(db: DB, _: CurrentUser, subject_id: uuid.UUID | None = None):
    statement = select(Term)
    if subject_id is not None:
        statement = statement.where(Term.subject_id == subject_id)
    items = (await db.scalars(statement.order_by(Term.sequence))).all()
    return {"items": [{"id": x.id, "subject_id": x.subject_id, "code": x.code, "title": x.title, "sequence": x.sequence} for x in items]}


@router.get("/terms/{term_id}/chapters")
async def list_chapters(term_id: uuid.UUID, db: DB, _: CurrentUser):
    if not await db.get(Term, term_id):
        raise APIError(404, "term_not_found", "Term not found")
    items = (await db.scalars(select(Chapter).where(Chapter.term_id == term_id).order_by(Chapter.sequence))).all()
    return {"items": [{"id": x.id, "textbook_id": x.textbook_id, "term_id": x.term_id, "code": x.code, "title": x.title, "sequence": x.sequence} for x in items]}


@router.get("/chapters/{chapter_id}/topics")
async def list_topics(chapter_id: uuid.UUID, db: DB, _: CurrentUser):
    if not await db.get(Chapter, chapter_id):
        raise APIError(404, "chapter_not_found", "Chapter not found")
    items = (await db.scalars(select(Topic).where(Topic.chapter_id == chapter_id, Topic.is_enabled.is_(True)).order_by(Topic.sequence))).all()
    return {"items": [{"id": x.id, "chapter_id": x.chapter_id, "section_code": x.section_code, "title": x.title, "sequence": x.sequence} for x in items]}


def _curriculum_out(item: Curriculum) -> dict:
    return {"id": item.id, "code": item.code, "board": item.board, "state_code": item.state_code, "class_level": item.class_level}


def _subject_out(item: Subject) -> dict:
    return {"id": item.id, "curriculum_id": item.curriculum_id, "code": item.code, "title": item.title}


def _textbook_out(item: Textbook, chunk_count: int) -> dict:
    return {
        "id": item.id,
        "subject_id": item.subject_id,
        "title": item.title,
        "academic_year": item.academic_year,
        "edition": item.edition,
        "processing_status": item.processing_status,
        "failure_reason": item.failure_reason,
        "content_available": item.processing_status == "ready" and chunk_count > 0,
        "indexed_chunk_count": chunk_count,
    }

"""Remove only unused CBSE Class 12 curriculum sources and private PDFs.

The command is a dry run unless both --apply and the exact confirmation token
are supplied. It refuses to delete anything when a Class 12 student profile,
generation batch, question, or test references the selected scope.

Run from the backend directory so the existing .env configuration is used.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from sqlalchemy import delete, func, select

# Running ``python scripts/cleanup_cbse_class12.py`` places only the scripts
# directory on sys.path. Add the backend root so the existing ``app`` package
# is importable without requiring PYTHONPATH changes.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.database import SessionLocal
from app.models import (
    Chapter,
    Curriculum,
    GenerationBatch,
    Question,
    SourceChunk,
    SourceDocument,
    StudentProfile,
    Subject,
    Term,
    Test,
    Textbook,
    TextbookFile,
    Topic,
)
from app.storage import run_storage, storage


CONFIRMATION = "DELETE-CBSE-CLASS-12"


@dataclass(frozen=True)
class CleanupScope:
    curriculum_ids: tuple[UUID, ...]
    subject_ids: tuple[UUID, ...]
    textbook_ids: tuple[UUID, ...]
    term_ids: tuple[UUID, ...]
    chapter_ids: tuple[UUID, ...]
    object_keys: tuple[str, ...]


async def _ids(db, model, predicate) -> tuple[UUID, ...]:
    return tuple((await db.scalars(select(model.id).where(predicate))).all())


async def _count(db, model, predicate) -> int:
    return int(
        await db.scalar(select(func.count()).select_from(model).where(predicate))
        or 0
    )


async def _scope(db) -> CleanupScope:
    curriculum_ids = await _ids(
        db,
        Curriculum,
        (Curriculum.board == "cbse")
        & (Curriculum.class_level == 12)
        & Curriculum.state_code.is_(None),
    )
    subject_ids = await _ids(db, Subject, Subject.curriculum_id.in_(curriculum_ids))
    textbook_ids = await _ids(db, Textbook, Textbook.subject_id.in_(subject_ids))
    term_ids = await _ids(db, Term, Term.subject_id.in_(subject_ids))
    chapter_ids = await _ids(db, Chapter, Chapter.textbook_id.in_(textbook_ids))

    file_keys = (
        await db.scalars(
            select(TextbookFile.object_key).where(TextbookFile.textbook_id.in_(textbook_ids))
        )
    ).all()
    legacy_keys = (
        await db.scalars(
            select(Textbook.object_key).where(
                Textbook.id.in_(textbook_ids),
                Textbook.object_key.is_not(None),
            )
        )
    ).all()
    object_keys = tuple(sorted({key for key in (*file_keys, *legacy_keys) if key}))
    return CleanupScope(
        curriculum_ids=curriculum_ids,
        subject_ids=subject_ids,
        textbook_ids=textbook_ids,
        term_ids=term_ids,
        chapter_ids=chapter_ids,
        object_keys=object_keys,
    )


async def _summary(db, scope: CleanupScope) -> dict[str, int]:
    return {
        "curricula": len(scope.curriculum_ids),
        "subjects": len(scope.subject_ids),
        "textbooks": len(scope.textbook_ids),
        "terms": len(scope.term_ids),
        "chapters": len(scope.chapter_ids),
        "topics": await _count(db, Topic, Topic.chapter_id.in_(scope.chapter_ids)),
        "textbook_files": await _count(
            db, TextbookFile, TextbookFile.textbook_id.in_(scope.textbook_ids)
        ),
        "source_documents": await _count(
            db, SourceDocument, SourceDocument.textbook_id.in_(scope.textbook_ids)
        ),
        "source_chunks": await _count(
            db, SourceChunk, SourceChunk.textbook_id.in_(scope.textbook_ids)
        ),
        "private_pdf_objects": len(scope.object_keys),
    }


async def _blockers(db, scope: CleanupScope) -> dict[str, int]:
    blockers = {
        "student_profiles": await _count(
            db, StudentProfile, StudentProfile.curriculum_id.in_(scope.curriculum_ids)
        ),
        "generation_batches": await _count(
            db,
            GenerationBatch,
            GenerationBatch.curriculum_id.in_(scope.curriculum_ids)
            | GenerationBatch.subject_id.in_(scope.subject_ids)
            | GenerationBatch.textbook_id.in_(scope.textbook_ids),
        ),
        "questions": await _count(
            db,
            Question,
            Question.textbook_id.in_(scope.textbook_ids)
            | Question.chapter_id.in_(scope.chapter_ids),
        ),
        "tests": await _count(
            db,
            Test,
            Test.curriculum_id.in_(scope.curriculum_ids)
            | Test.subject_id.in_(scope.subject_ids)
            | Test.textbook_id.in_(scope.textbook_ids),
        ),
    }
    return {name: count for name, count in blockers.items() if count}


def _print_counts(title: str, values: dict[str, int]) -> None:
    print(title)
    for name, count in values.items():
        print(f"  {name}: {count}")


async def cleanup(apply: bool, confirmation: str | None) -> int:
    async with SessionLocal() as db:
        scope = await _scope(db)
        if not scope.curriculum_ids:
            print("No CBSE Class 12 curriculum records were found. Nothing was changed.")
            return 0

        summary = await _summary(db, scope)
        blockers = await _blockers(db, scope)
        _print_counts("CBSE Class 12 cleanup scope:", summary)
        print("  R2 object keys:")
        for key in scope.object_keys:
            print(f"    {key}")

        if blockers:
            _print_counts("Cleanup blocked by existing academic references:", blockers)
            print("No database rows or private objects were changed.")
            await db.rollback()
            return 2

        if not apply:
            print("Dry run only. Re-run with --apply and the confirmation token to delete this scope.")
            await db.rollback()
            return 0
        if confirmation != CONFIRMATION:
            print(f"Refusing cleanup. Supply --confirm {CONFIRMATION} exactly.")
            await db.rollback()
            return 2

        if scope.object_keys:
            try:
                storage.require_configured()
            except Exception as exc:
                print(
                    "Refusing cleanup because private storage is not configured; "
                    f"database rows were left unchanged ({type(exc).__name__})."
                )
                await db.rollback()
                return 2

        # Delete only content rows owned by the exact CBSE Class 12 scope.
        await db.execute(delete(SourceChunk).where(SourceChunk.textbook_id.in_(scope.textbook_ids)))
        await db.execute(delete(SourceDocument).where(SourceDocument.textbook_id.in_(scope.textbook_ids)))
        await db.execute(delete(TextbookFile).where(TextbookFile.textbook_id.in_(scope.textbook_ids)))
        await db.execute(delete(Topic).where(Topic.chapter_id.in_(scope.chapter_ids)))
        await db.execute(delete(Chapter).where(Chapter.id.in_(scope.chapter_ids)))
        await db.execute(delete(Term).where(Term.id.in_(scope.term_ids)))
        await db.execute(delete(Textbook).where(Textbook.id.in_(scope.textbook_ids)))
        await db.execute(delete(Subject).where(Subject.id.in_(scope.subject_ids)))
        await db.execute(delete(Curriculum).where(Curriculum.id.in_(scope.curriculum_ids)))
        await db.commit()

    failed_objects: list[str] = []
    for object_key in scope.object_keys:
        try:
            await run_storage(storage.delete, object_key)
        except Exception as exc:
            failed_objects.append(object_key)
            print(
                f"WARNING: database cleanup completed, but private object deletion failed "
                f"for {object_key} ({type(exc).__name__})."
            )

    print("CBSE Class 12 database content was removed. CBSE Class 8 was not selected or changed.")
    if failed_objects:
        print("Delete the warning-listed orphaned R2 keys manually before uploading fresh PDFs.")
        return 3
    print("The matching private PDF objects were also removed from storage.")
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Dry-run and optionally remove only unused CBSE Class 12 curriculum content."
    )
    parser.add_argument("--apply", action="store_true", help="Apply the displayed cleanup scope")
    parser.add_argument("--confirm", help=f"Required with --apply: {CONFIRMATION}")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(cleanup(args.apply, args.confirm)))


if __name__ == "__main__":
    main()

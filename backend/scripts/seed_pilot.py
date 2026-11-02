"""Seed the approved catalog and an optional local Pilot teacher account.

Codex does not execute this script. Run it manually after the migration and
textbook-ingestion steps, from the backend directory.

Create students through the teacher Students workflow so email login and the
mandatory temporary-password change are enforced. Existing database students
are not modified by this script or by the email-auth migration.
"""
import argparse
import asyncio

from sqlalchemy import select

from app.database import SessionLocal
from app.enums import Role, UserStatus
from app.generation.ingestion import CBSE_8_MATH_SUBJECT_ID, approved_catalog
from app.models import Chapter, Term, Topic, User
from app.security import hash_password, normalize_login


async def upsert_teacher(name: str, login: str, password: str) -> None:
    async with SessionLocal() as db:
        identifier = normalize_login(login)
        user = await db.scalar(select(User).where(User.login_identifier == identifier))
        if not user:
            user = User(
                name=name,
                login_identifier=identifier,
                password_hash=hash_password(password),
                role=Role.TEACHER,
                status=UserStatus.ACTIVE,
            )
            db.add(user)
        await db.commit()


async def seed_curriculum() -> None:
    catalog = approved_catalog()
    async with SessionLocal() as db:
        for item in catalog["terms"]:
            term = await db.scalar(
                select(Term).where(
                    Term.subject_id == CBSE_8_MATH_SUBJECT_ID,
                    Term.code == item["code"],
                )
            )
            if term is None:
                db.add(Term(**item))
            else:
                term.subject_id, term.code = item["subject_id"], item["code"]
                term.title, term.sequence = item["title"], item["sequence"]
        await db.flush()
        for item in catalog["chapters"]:
            chapter = await db.get(Chapter, item["id"])
            if chapter is None:
                db.add(Chapter(**item))
            else:
                chapter.textbook_id, chapter.term_id = item["textbook_id"], item["term_id"]
                chapter.title, chapter.sequence = item["title"], item["sequence"]
        await db.flush()
        for item in catalog["topics"]:
            topic = await db.get(Topic, item["id"])
            if topic is None:
                db.add(Topic(**item))
            else:
                topic.title = item["title"]
                topic.sequence = item["sequence"]
                topic.is_enabled = True
        await db.commit()


async def main(args: argparse.Namespace) -> None:
    await seed_curriculum()
    if args.teacher_login:
        await upsert_teacher(args.teacher_name, args.teacher_login, args.teacher_password)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--teacher-login")
    parser.add_argument("--teacher-password")
    parser.add_argument("--teacher-name", default="Pilot Teacher")
    values = parser.parse_args()
    if bool(values.teacher_login) != bool(values.teacher_password):
        parser.error("A supplied teacher login requires its matching password")
    asyncio.run(main(values))

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, select

from .dependencies import DB, Teacher
from .enums import QuestionStatus, Role, TestStatus, UserStatus
from .errors import APIError
from .models import Chapter, Curriculum, GenerationBatch, Question, StudentProfile, Subject, Term, Test, TestAssignment, TestQuestion, Textbook, Topic, User

router = APIRouter(tags=["tests"])


class TestCreateIn(BaseModel):
    generation_batch_id: uuid.UUID
    title: str = Field(min_length=1, max_length=255)
    instructions: str = Field(default="", max_length=10000)
    question_ids: list[uuid.UUID] = Field(min_length=1)
    student_ids: list[uuid.UUID] = Field(min_length=1)


class TestUpdateIn(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    instructions: str | None = Field(default=None, max_length=10000)
    question_ids: list[uuid.UUID] | None = None
    student_ids: list[uuid.UUID] | None = None


class AssignmentUpdateIn(BaseModel):
    student_ids: list[uuid.UUID] = Field(min_length=1)


async def owned_test(db: DB, test_id: uuid.UUID, teacher_id: uuid.UUID) -> Test:
    test = await db.scalar(select(Test).where(Test.id == test_id, Test.teacher_id == teacher_id))
    if not test:
        raise APIError(404, "test_not_found", "Test not found")
    return test


async def validate_students(db: DB, ids: list[uuid.UUID], curriculum_id: uuid.UUID) -> list[User]:
    unique = list(dict.fromkeys(ids))
    students = (await db.scalars(
        select(User)
        .join(StudentProfile, StudentProfile.user_id == User.id)
        .where(
            User.id.in_(unique),
            User.role == Role.STUDENT,
            User.status == UserStatus.ACTIVE,
            StudentProfile.curriculum_id == curriculum_id,
        )
    )).all()
    if len(students) != len(unique):
        raise APIError(422, "invalid_students", "Every assignment must reference an active student in the test curriculum")
    return list(students)


async def validate_questions(
    db: DB,
    batch_id: uuid.UUID,
    ids: list[uuid.UUID],
    require_approved: bool = False,
    *,
    lock: bool = False,
) -> list[Question]:
    unique = list(dict.fromkeys(ids))
    if len(unique) != len(ids):
        raise APIError(422, "duplicate_questions", "A test cannot include the same question more than once")
    statement = select(Question).where(Question.id.in_(unique), Question.batch_id == batch_id)
    if lock:
        statement = statement.with_for_update()
    rows = (await db.scalars(statement)).all()
    by_id = {row.id: row for row in rows}
    if len(by_id) != len(unique):
        raise APIError(422, "invalid_questions", "Every question must belong to the selected generation batch")
    ordered = [by_id[x] for x in ids]
    if require_approved and any(x.status != QuestionStatus.APPROVED for x in ordered):
        raise APIError(409, "questions_not_approved", "All included questions must be approved")
    return ordered


async def replace_assignments(db: DB, test: Test, student_ids: list[uuid.UUID]) -> None:
    await validate_students(db, student_ids, test.curriculum_id)
    await db.execute(delete(TestAssignment).where(TestAssignment.test_id == test.id))
    for student_id in dict.fromkeys(student_ids):
        db.add(TestAssignment(test_id=test.id, student_id=student_id))


def test_payload(test: Test, question_ids: list[uuid.UUID], student_ids: list[uuid.UUID]):
    return {
        "id": test.id, "generation_batch_id": test.generation_batch_id, "title": test.title,
        "instructions": test.instructions, "total_marks": test.total_marks, "status": test.status,
        "curriculum_id": test.curriculum_id, "subject_id": test.subject_id, "textbook_id": test.textbook_id,
        "published_at": test.published_at, "question_ids": question_ids, "student_ids": student_ids,
    }


async def load_test_relations(db: DB, test_id: uuid.UUID):
    question_ids = list((await db.scalars(select(TestQuestion.question_id).where(TestQuestion.test_id == test_id).order_by(TestQuestion.order))).all())
    student_ids = list((await db.scalars(select(TestAssignment.student_id).where(TestAssignment.test_id == test_id))).all())
    return question_ids, student_ids


@router.get("/students")
async def list_students(db: DB, _: Teacher, curriculum_id: uuid.UUID | None = Query(default=None)):
    statement = select(User).join(StudentProfile, StudentProfile.user_id == User.id).where(User.role == Role.STUDENT, User.status == UserStatus.ACTIVE)
    if curriculum_id is not None:
        statement = statement.where(StudentProfile.curriculum_id == curriculum_id)
    rows = (await db.scalars(statement.order_by(User.name))).all()
    return {"items": [{"id": x.id, "name": x.name, "login_identifier": x.login_identifier} for x in rows]}


@router.post("/tests", status_code=201)
async def create_test(payload: TestCreateIn, db: DB, teacher: Teacher):
    batch = await db.scalar(select(GenerationBatch).where(GenerationBatch.id == payload.generation_batch_id, GenerationBatch.teacher_id == teacher.id))
    if not batch:
        raise APIError(404, "generation_batch_not_found", "Generation batch not found")
    questions = await validate_questions(db, batch.id, payload.question_ids)
    await validate_students(db, payload.student_ids, batch.curriculum_id)
    test = Test(teacher_id=teacher.id, generation_batch_id=batch.id, curriculum_id=batch.curriculum_id, subject_id=batch.subject_id, textbook_id=batch.textbook_id, title=payload.title.strip(), instructions=payload.instructions, total_marks=sum(x.marks for x in questions))
    db.add(test)
    await db.flush()
    # Draft rows establish order; publication replaces their values with frozen snapshots.
    term = await db.get(Term, batch.term_id)
    chapter = await db.get(Chapter, batch.chapter_id)
    topic = await db.get(Topic, batch.topic_id) if batch.topic_id else None
    curriculum, subject, textbook = await db.get(Curriculum, batch.curriculum_id), await db.get(Subject, batch.subject_id), await db.get(Textbook, batch.textbook_id)
    board_label = _board_label(curriculum)
    for order, question in enumerate(questions, 1):
        db.add(TestQuestion(test_id=test.id, question_id=question.id, order=order, text=question.text, type=question.type, marks=question.marks, options=question.options, correct_option_id=question.correct_option_id, reference_answer=question.reference_answer, board_label=board_label, class_level=curriculum.class_level, subject_label=subject.title, textbook_label=textbook.title, term_label=term.title, chapter_label=chapter.title, topic_label=topic.title if topic else None))
    await replace_assignments(db, test, payload.student_ids)
    await db.commit()
    await db.refresh(test)
    return test_payload(test, payload.question_ids, payload.student_ids)


@router.get("/tests/{test_id}")
async def get_test(test_id: uuid.UUID, db: DB, teacher: Teacher):
    test = await owned_test(db, test_id, teacher.id)
    question_ids, student_ids = await load_test_relations(db, test.id)
    snapshots = (await db.scalars(select(TestQuestion).where(TestQuestion.test_id == test.id).order_by(TestQuestion.order))).all()
    data = test_payload(test, question_ids, student_ids)
    data["questions"] = [{"id": x.id, "question_id": x.question_id, "order": x.order, "text": x.text, "type": x.type, "marks": x.marks, "options": x.options, "correct_option_id": x.correct_option_id, "reference_answer": x.reference_answer, "board_label": x.board_label, "class_level": x.class_level, "subject_label": x.subject_label, "textbook_label": x.textbook_label, "term_label": x.term_label, "chapter_label": x.chapter_label, "topic_label": x.topic_label} for x in snapshots]
    return data


@router.patch("/tests/{test_id}")
async def update_test(test_id: uuid.UUID, payload: TestUpdateIn, db: DB, teacher: Teacher):
    test = await owned_test(db, test_id, teacher.id)
    if test.status != TestStatus.DRAFT:
        raise APIError(409, "test_published", "Published tests are immutable")
    if payload.title is not None:
        test.title = payload.title.strip()
    if payload.instructions is not None:
        test.instructions = payload.instructions
    if payload.question_ids is not None:
        questions = await validate_questions(db, test.generation_batch_id, payload.question_ids)
        await db.execute(delete(TestQuestion).where(TestQuestion.test_id == test.id))
        batch = await db.get(GenerationBatch, test.generation_batch_id)
        term, chapter = await db.get(Term, batch.term_id), await db.get(Chapter, batch.chapter_id)
        topic = await db.get(Topic, batch.topic_id) if batch.topic_id else None
        curriculum, subject, textbook = await db.get(Curriculum, batch.curriculum_id), await db.get(Subject, batch.subject_id), await db.get(Textbook, batch.textbook_id)
        board_label = _board_label(curriculum)
        for order, q in enumerate(questions, 1):
            db.add(TestQuestion(test_id=test.id, question_id=q.id, order=order, text=q.text, type=q.type, marks=q.marks, options=q.options, correct_option_id=q.correct_option_id, reference_answer=q.reference_answer, board_label=board_label, class_level=curriculum.class_level, subject_label=subject.title, textbook_label=textbook.title, term_label=term.title, chapter_label=chapter.title, topic_label=topic.title if topic else None))
        test.total_marks = sum(x.marks for x in questions)
    if payload.student_ids is not None:
        await replace_assignments(db, test, payload.student_ids)
    await db.commit()
    question_ids, student_ids = await load_test_relations(db, test.id)
    return test_payload(test, question_ids, student_ids)


@router.post("/tests/{test_id}/assignments")
async def update_assignments(test_id: uuid.UUID, payload: AssignmentUpdateIn, db: DB, teacher: Teacher):
    test = await owned_test(db, test_id, teacher.id)
    if test.status != TestStatus.DRAFT:
        raise APIError(409, "test_published", "Published assignments are immutable")
    await replace_assignments(db, test, payload.student_ids)
    await db.commit()
    return {"test_id": test.id, "student_ids": list(dict.fromkeys(payload.student_ids))}


@router.post("/tests/{test_id}/publish")
async def publish_test(test_id: uuid.UUID, db: DB, teacher: Teacher):
    test = await db.scalar(select(Test).where(Test.id == test_id, Test.teacher_id == teacher.id).with_for_update())
    if not test:
        raise APIError(404, "test_not_found", "Test not found")
    if test.status == TestStatus.PUBLISHED:
        question_ids, student_ids = await load_test_relations(db, test.id)
        return test_payload(test, question_ids, student_ids)
    snapshots = (await db.scalars(select(TestQuestion).where(TestQuestion.test_id == test.id).order_by(TestQuestion.order))).all()
    assignments = (await db.scalars(select(TestAssignment).where(TestAssignment.test_id == test.id))).all()
    if not snapshots or not assignments:
        raise APIError(409, "test_incomplete", "A test requires questions and at least one assigned student")
    await validate_students(db, [x.student_id for x in assignments], test.curriculum_id)
    questions = await validate_questions(
        db,
        test.generation_batch_id,
        [x.question_id for x in snapshots],
        require_approved=True,
        lock=True,
    )
    by_id = {x.id: x for x in questions}
    # Refresh draft snapshot fields from the approved authoritative questions in this transaction.
    for snapshot in snapshots:
        question = by_id[snapshot.question_id]
        snapshot.text, snapshot.type, snapshot.marks = question.text, question.type, question.marks
        snapshot.options, snapshot.correct_option_id = question.options, question.correct_option_id
        snapshot.reference_answer = question.reference_answer
    test.total_marks = sum(x.marks for x in snapshots)
    test.status = TestStatus.PUBLISHED
    test.published_at = datetime.now(UTC)
    await db.commit()
    return test_payload(test, [x.question_id for x in snapshots], [x.student_id for x in assignments])


def _board_label(curriculum: Curriculum) -> str:
    names = {"cbse": "CBSE", "icse": "ICSE", "state": "State Board"}
    base = names.get(curriculum.board, curriculum.board.upper())
    return f"{base} ({curriculum.state_code})" if curriculum.state_code else base

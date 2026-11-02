import uuid
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from .dependencies import DB, Teacher
from .enums import AttemptStatus, EvaluationStatus, ImageStatus, ResultStatus, TestStatus
from .errors import APIError
from .models import AnswerImage, Attempt, Curriculum, QuestionEvaluation, Result, StudentAnswer, Subject, Test, TestQuestion, User
from .schemas import EvaluationSaveIn
from .storage import run_storage, storage

router = APIRouter(prefix="/teacher", tags=["teacher"])


class ResultPublishIn(BaseModel):
    overall_comment: str | None = Field(default=None, max_length=4000)


async def owned_attempt(db: DB, attempt_id: uuid.UUID, teacher_id: uuid.UUID) -> tuple[Attempt, Test]:
    row = (await db.execute(select(Attempt, Test).join(Test, Test.id == Attempt.test_id).where(Attempt.id == attempt_id, Test.teacher_id == teacher_id))).first()
    if not row:
        raise APIError(404, "attempt_not_found", "Attempt not found")
    return row[0], row[1]


@router.get("/dashboard")
async def dashboard(db: DB, teacher: Teacher):
    total_tests = await db.scalar(select(func.count()).select_from(Test).where(Test.teacher_id == teacher.id)) or 0
    published_tests = await db.scalar(select(func.count()).select_from(Test).where(Test.teacher_id == teacher.id, Test.status == TestStatus.PUBLISHED)) or 0
    submitted_attempts = await db.scalar(select(func.count()).select_from(Attempt).join(Test, Test.id == Attempt.test_id).where(Test.teacher_id == teacher.id, Attempt.status.in_([AttemptStatus.SUBMITTED, AttemptStatus.EVALUATION_IN_PROGRESS, AttemptStatus.EVALUATED, AttemptStatus.RESULT_PUBLISHED]))) or 0
    pending = await db.scalar(select(func.count()).select_from(Attempt).join(Test, Test.id == Attempt.test_id).where(Test.teacher_id == teacher.id, Attempt.status.in_([AttemptStatus.SUBMITTED, AttemptStatus.EVALUATION_IN_PROGRESS]))) or 0
    recent = (await db.execute(select(Test, Curriculum, Subject).join(Curriculum, Curriculum.id == Test.curriculum_id).join(Subject, Subject.id == Test.subject_id).where(Test.teacher_id == teacher.id).order_by(Test.created_at.desc()).limit(10))).all()
    return {"total_tests": total_tests, "published_tests": published_tests, "submitted_attempts": submitted_attempts, "pending_evaluation": pending, "recent_tests": [{"id": test.id, "title": test.title, "status": test.status, "total_marks": test.total_marks, "published_at": test.published_at, "board": curriculum.board, "state_code": curriculum.state_code, "class_level": curriculum.class_level, "subject_title": subject.title} for test, curriculum, subject in recent]}


@router.get("/evaluations")
async def evaluation_queue(db: DB, teacher: Teacher):
    rows = (await db.execute(
        select(Attempt, Test, User).join(Test, Test.id == Attempt.test_id).join(User, User.id == Attempt.student_id).where(
            Test.teacher_id == teacher.id,
            Attempt.status.in_([AttemptStatus.SUBMITTED, AttemptStatus.EVALUATION_IN_PROGRESS, AttemptStatus.EVALUATED]),
        ).order_by(Attempt.submitted_at.asc())
    )).all()
    return {"items": [{"attempt_id": a.id, "test_id": t.id, "test_title": t.title, "student_id": u.id, "student_name": u.name, "status": a.status, "submitted_at": a.submitted_at} for a, t, u in rows]}


@router.get("/attempts/{attempt_id}")
async def get_answer_sheet(attempt_id: uuid.UUID, db: DB, teacher: Teacher):
    attempt, test = await owned_attempt(db, attempt_id, teacher.id)
    if attempt.status == AttemptStatus.IN_PROGRESS:
        raise APIError(409, "attempt_not_submitted", "Only submitted attempts can be evaluated")
    student = await db.get(User, attempt.student_id)
    questions = (await db.scalars(select(TestQuestion).where(TestQuestion.test_id == test.id).order_by(TestQuestion.order))).all()
    answers = (await db.scalars(select(StudentAnswer).where(StudentAnswer.attempt_id == attempt.id))).all()
    evaluations = (await db.scalars(select(QuestionEvaluation).where(QuestionEvaluation.attempt_id == attempt.id))).all()
    answer_by_question = {x.test_question_id: x for x in answers}
    evaluation_by_question = {x.test_question_id: x for x in evaluations}
    image_map: dict[uuid.UUID, list] = {}
    if answers:
        images = (await db.scalars(select(AnswerImage).where(AnswerImage.answer_id.in_([x.id for x in answers]), AnswerImage.status == ImageStatus.READY).order_by(AnswerImage.answer_id, AnswerImage.page_order))).all()
        for image in images:
            image_map.setdefault(image.answer_id, []).append({"id": image.id, "page_order": image.page_order, "media_type": image.media_type, "preview_url": await run_storage(storage.create_read_url, image.object_key)})
    question_items = []
    for q in questions:
        answer = answer_by_question.get(q.id)
        evaluation = evaluation_by_question.get(q.id)
        question_items.append({
            "id": q.id, "order": q.order, "text": q.text, "type": q.type, "marks": q.marks,
            "options": q.options, "correct_option_id": q.correct_option_id, "reference_answer": q.reference_answer,
            "board_label": q.board_label, "class_level": q.class_level, "subject_label": q.subject_label, "textbook_label": q.textbook_label, "term_label": q.term_label, "chapter_label": q.chapter_label, "topic_label": q.topic_label,
            "answer": None if not answer else {"id": answer.id, "answer_type": answer.answer_type, "selected_option_id": answer.selected_option_id, "text_answer": answer.text_answer, "images": image_map.get(answer.id, [])},
            "evaluation": None if not evaluation else {"status": evaluation.status, "awarded_marks": evaluation.awarded_marks, "feedback": evaluation.feedback, "version": evaluation.version},
        })
    return {"attempt_id": attempt.id, "status": attempt.status, "test": {"id": test.id, "title": test.title, "total_marks": test.total_marks}, "student": {"id": student.id, "name": student.name}, "questions": question_items}


@router.put("/attempts/{attempt_id}/evaluations/{test_question_id}")
async def save_evaluation(attempt_id: uuid.UUID, test_question_id: uuid.UUID, payload: EvaluationSaveIn, db: DB, teacher: Teacher):
    attempt, test = await owned_attempt(db, attempt_id, teacher.id)
    attempt = await db.scalar(
        select(Attempt).where(Attempt.id == attempt.id).with_for_update()
    )
    if attempt.status not in [AttemptStatus.SUBMITTED, AttemptStatus.EVALUATION_IN_PROGRESS]:
        raise APIError(409, "evaluation_locked", "This attempt cannot be evaluated")
    question = await db.scalar(select(TestQuestion).where(TestQuestion.id == test_question_id, TestQuestion.test_id == test.id))
    if not question:
        raise APIError(404, "question_not_found", "Question not found")
    max_marks = Decimal(question.marks)
    if payload.status == EvaluationStatus.CORRECT and payload.awarded_marks != max_marks:
        raise APIError(422, "marks_status_conflict", "Correct requires full marks")
    if payload.status == EvaluationStatus.WRONG and payload.awarded_marks != 0:
        raise APIError(422, "marks_status_conflict", "Wrong requires zero marks")
    if payload.status == EvaluationStatus.PARTIAL and not (0 < payload.awarded_marks < max_marks):
        raise APIError(422, "marks_status_conflict", "Partial requires marks between zero and full marks")
    evaluation = await db.scalar(select(QuestionEvaluation).where(QuestionEvaluation.attempt_id == attempt.id, QuestionEvaluation.test_question_id == question.id))
    if evaluation:
        if payload.version != evaluation.version:
            raise APIError(409, "version_conflict", "A newer evaluation version exists", {"current_version": evaluation.version})
        evaluation.status, evaluation.awarded_marks, evaluation.feedback = payload.status, payload.awarded_marks, payload.feedback
        evaluation.version += 1
    else:
        if payload.version != 0:
            raise APIError(409, "version_conflict", "New evaluations must start at version zero", {"current_version": 0})
        evaluation = QuestionEvaluation(attempt_id=attempt.id, test_question_id=question.id, evaluator_id=teacher.id, status=payload.status, awarded_marks=payload.awarded_marks, feedback=payload.feedback, version=1)
        db.add(evaluation)
    attempt.status = AttemptStatus.EVALUATION_IN_PROGRESS
    question_count = await db.scalar(select(func.count()).select_from(TestQuestion).where(TestQuestion.test_id == test.id)) or 0
    evaluation_count = await db.scalar(select(func.count()).select_from(QuestionEvaluation).where(QuestionEvaluation.attempt_id == attempt.id)) or 0
    # The pending in-session insert is not visible to the count until flushed.
    if evaluation.id is None:
        evaluation_count += 1
    if evaluation_count >= question_count:
        attempt.status = AttemptStatus.EVALUATED
    await db.commit()
    await db.refresh(evaluation)
    return {"status": evaluation.status, "awarded_marks": evaluation.awarded_marks, "feedback": evaluation.feedback, "version": evaluation.version, "updated_at": evaluation.updated_at}


@router.post("/attempts/{attempt_id}/results/publish")
async def publish_result(attempt_id: uuid.UUID, db: DB, teacher: Teacher, payload: ResultPublishIn | None = None):
    attempt, test = await owned_attempt(db, attempt_id, teacher.id)
    attempt = await db.scalar(select(Attempt).where(Attempt.id == attempt.id).with_for_update())
    existing = await db.scalar(select(Result).where(Result.attempt_id == attempt.id, Result.status == ResultStatus.PUBLISHED))
    if existing:
        return {"id": existing.id, "attempt_id": attempt.id, "awarded_total": existing.awarded_total, "max_total": existing.max_total, "percentage": existing.percentage, "overall_comment": existing.overall_comment, "published_at": existing.published_at}
    if attempt.status not in [AttemptStatus.SUBMITTED, AttemptStatus.EVALUATION_IN_PROGRESS, AttemptStatus.EVALUATED]:
        raise APIError(409, "result_not_ready", "Attempt is not ready for result publication")
    question_count = await db.scalar(select(func.count()).select_from(TestQuestion).where(TestQuestion.test_id == test.id)) or 0
    evaluations = (await db.scalars(select(QuestionEvaluation).where(QuestionEvaluation.attempt_id == attempt.id))).all()
    if len(evaluations) != question_count:
        raise APIError(409, "evaluation_incomplete", "Every question must be evaluated before publishing the result")
    awarded = sum((x.awarded_marks for x in evaluations), Decimal(0))
    maximum = Decimal(test.total_marks)
    now = datetime.now(UTC)
    result = Result(attempt_id=attempt.id, evaluator_id=teacher.id, awarded_total=awarded, max_total=maximum, percentage=(awarded / maximum * 100).quantize(Decimal("0.01")) if maximum else Decimal(0), overall_comment=payload.overall_comment if payload else None, status=ResultStatus.PUBLISHED, finalized_at=now, published_at=now)
    db.add(result)
    attempt.status = AttemptStatus.RESULT_PUBLISHED
    await db.commit()
    await db.refresh(result)
    return {"id": result.id, "attempt_id": attempt.id, "awarded_total": result.awarded_total, "max_total": result.max_total, "percentage": result.percentage, "overall_comment": result.overall_comment, "published_at": result.published_at}

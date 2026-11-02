import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Response
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError

from .config import get_settings
from .dependencies import DB, Student
from .enums import AnswerType, AttemptStatus, ImageStatus, QuestionType, ResultStatus, TestStatus
from .errors import APIError
from .models import AnswerImage, Attempt, Curriculum, QuestionEvaluation, Result, StudentAnswer, Subject, Test, TestAssignment, TestQuestion
from .schemas import AnswerSaveIn, CompleteUploadIn, ImageOrderIn, UploadUrlIn
from .storage import ALLOWED_IMAGE_TYPES, run_storage, storage

router = APIRouter(prefix="/student", tags=["student"])


async def assigned_test(db: DB, test_id: uuid.UUID, student_id: uuid.UUID) -> Test:
    test = await db.scalar(
        select(Test).join(TestAssignment, TestAssignment.test_id == Test.id).where(
            Test.id == test_id, Test.status == TestStatus.PUBLISHED, TestAssignment.student_id == student_id
        )
    )
    if not test:
        raise APIError(404, "test_not_found", "Test not found")
    return test


async def owned_attempt(db: DB, attempt_id: uuid.UUID, student_id: uuid.UUID) -> Attempt:
    attempt = await db.scalar(select(Attempt).where(Attempt.id == attempt_id, Attempt.student_id == student_id))
    if not attempt:
        raise APIError(404, "attempt_not_found", "Attempt not found")
    return attempt


def student_question(row: TestQuestion):
    return {"id": row.id, "order": row.order, "text": row.text, "type": row.type, "marks": row.marks, "options": row.options, "board_label": row.board_label, "class_level": row.class_level, "subject_label": row.subject_label, "textbook_label": row.textbook_label, "term_label": row.term_label, "chapter_label": row.chapter_label, "topic_label": row.topic_label}


@router.get("/dashboard")
async def dashboard(db: DB, student: Student):
    available_rows = (await db.execute(
        select(Test, Attempt, Curriculum, Subject).join(TestAssignment, TestAssignment.test_id == Test.id).join(Curriculum, Curriculum.id == Test.curriculum_id).join(Subject, Subject.id == Test.subject_id).outerjoin(
            Attempt, (Attempt.test_id == Test.id) & (Attempt.student_id == student.id)
        ).where(TestAssignment.student_id == student.id, Test.status == TestStatus.PUBLISHED).order_by(Test.published_at.desc())
    )).all()
    result_rows = (await db.execute(
        select(Result, Attempt, Test, Curriculum, Subject)
        .join(Attempt, Attempt.id == Result.attempt_id)
        .join(Test, Test.id == Attempt.test_id)
        .join(Curriculum, Curriculum.id == Test.curriculum_id)
        .join(Subject, Subject.id == Test.subject_id).where(
            Attempt.student_id == student.id, Result.status == ResultStatus.PUBLISHED
        ).order_by(Result.published_at.desc())
    )).all()
    available = []
    submitted = []
    for test, attempt, curriculum, subject in available_rows:
        scope = {"board": curriculum.board, "state_code": curriculum.state_code, "class_level": curriculum.class_level, "subject_title": subject.title}
        if not attempt or attempt.status == AttemptStatus.IN_PROGRESS:
            available.append({"id": test.id, "title": test.title, "total_marks": test.total_marks, "attempt_id": attempt.id if attempt else None, "attempt_status": attempt.status if attempt else None, **scope})
        elif attempt.status != AttemptStatus.RESULT_PUBLISHED:
            submitted.append({"id": test.id, "title": test.title, "total_marks": test.total_marks, "attempt_id": attempt.id, "attempt_status": attempt.status, "submitted_at": attempt.submitted_at, **scope})
    completed = [{"attempt_id": attempt.id, "test_id": test.id, "title": test.title, "awarded_total": result.awarded_total, "max_total": result.max_total, "percentage": result.percentage, "published_at": result.published_at, "board": curriculum.board, "state_code": curriculum.state_code, "class_level": curriculum.class_level, "subject_title": subject.title} for result, attempt, test, curriculum, subject in result_rows]
    return {"available_tests": available, "submitted_tests": submitted, "completed_tests": completed}


@router.get("/tests/{test_id}")
async def get_test(test_id: uuid.UUID, db: DB, student: Student):
    test = await assigned_test(db, test_id, student.id)
    questions = (await db.scalars(select(TestQuestion).where(TestQuestion.test_id == test.id).order_by(TestQuestion.order))).all()
    first = questions[0] if questions else None
    return {"id": test.id, "title": test.title, "instructions": test.instructions, "total_marks": test.total_marks, "board_label": first.board_label if first else None, "class_level": first.class_level if first else None, "subject_label": first.subject_label if first else None, "textbook_label": first.textbook_label if first else None, "questions": [student_question(x) for x in questions]}


@router.post("/tests/{test_id}/attempts", status_code=201)
async def start_attempt(test_id: uuid.UUID, db: DB, student: Student, response: Response):
    test = await assigned_test(db, test_id, student.id)
    attempt = await db.scalar(select(Attempt).where(Attempt.test_id == test.id, Attempt.student_id == student.id))
    if attempt:
        response.status_code = 200
        return {"id": attempt.id, "test_id": attempt.test_id, "status": attempt.status, "started_at": attempt.started_at}
    attempt = Attempt(test_id=test.id, student_id=student.id)
    db.add(attempt)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        attempt = await db.scalar(select(Attempt).where(Attempt.test_id == test.id, Attempt.student_id == student.id))
        response.status_code = 200
        return {"id": attempt.id, "test_id": attempt.test_id, "status": attempt.status, "started_at": attempt.started_at}
    await db.refresh(attempt)
    return {"id": attempt.id, "test_id": attempt.test_id, "status": attempt.status, "started_at": attempt.started_at}


@router.get("/attempts/{attempt_id}")
async def get_attempt(attempt_id: uuid.UUID, db: DB, student: Student):
    attempt = await owned_attempt(db, attempt_id, student.id)
    test = await db.get(Test, attempt.test_id)
    questions = (await db.scalars(select(TestQuestion).where(TestQuestion.test_id == attempt.test_id).order_by(TestQuestion.order))).all()
    answers = (await db.scalars(select(StudentAnswer).where(StudentAnswer.attempt_id == attempt.id))).all()
    answer_ids = [x.id for x in answers]
    images = (await db.scalars(select(AnswerImage).where(AnswerImage.answer_id.in_(answer_ids), AnswerImage.status == ImageStatus.READY).order_by(AnswerImage.answer_id, AnswerImage.page_order))).all() if answer_ids else []
    image_map: dict[uuid.UUID, list] = {}
    for image in images:
        image_map.setdefault(image.answer_id, []).append({"id": image.id, "page_order": image.page_order, "media_type": image.media_type, "preview_url": storage.create_read_url(image.object_key)})
    answered_question_ids = {x.test_question_id for x in answers if x.selected_option_id is not None or (x.text_answer is not None and x.text_answer.strip()) or image_map.get(x.id)}
    return {
        "id": attempt.id, "test_id": attempt.test_id, "test_title": test.title, "status": attempt.status, "started_at": attempt.started_at,
        "submitted_at": attempt.submitted_at, "unanswered_count": len(questions) - len(answered_question_ids),
        "short_answer_max_chars": get_settings().short_answer_max_chars,
        "questions": [student_question(x) for x in questions],
        "answers": [{"id": x.id, "test_question_id": x.test_question_id, "answer_type": x.answer_type, "selected_option_id": x.selected_option_id, "text_answer": x.text_answer, "version": x.version, "images": image_map.get(x.id, [])} for x in answers],
    }


@router.put("/attempts/{attempt_id}/answers/{test_question_id}")
async def save_answer(attempt_id: uuid.UUID, test_question_id: uuid.UUID, payload: AnswerSaveIn, db: DB, student: Student):
    # Serialize autosaves for one attempt so version checks also protect the
    # first insert, not only updates to an existing answer row.
    attempt = await db.scalar(
        select(Attempt)
        .where(Attempt.id == attempt_id, Attempt.student_id == student.id)
        .with_for_update()
    )
    if not attempt:
        raise APIError(404, "attempt_not_found", "Attempt not found")
    if attempt.status != AttemptStatus.IN_PROGRESS:
        raise APIError(409, "attempt_locked", "Submitted attempts are read-only")
    question = await db.scalar(select(TestQuestion).where(TestQuestion.id == test_question_id, TestQuestion.test_id == attempt.test_id))
    if not question:
        raise APIError(404, "question_not_found", "Question not found")
    if question.type == QuestionType.MCQ and payload.answer_type != AnswerType.MCQ:
        raise APIError(422, "answer_type_mismatch", "MCQ questions require an MCQ answer")
    if question.type != QuestionType.MCQ and payload.answer_type == AnswerType.MCQ:
        raise APIError(422, "answer_type_mismatch", "This question does not accept an MCQ answer")
    if payload.text_answer is not None and len(payload.text_answer) > get_settings().short_answer_max_chars:
        raise APIError(422, "answer_too_long", "Text answer exceeds the configured limit")
    if payload.answer_type == AnswerType.MCQ:
        option_ids = {str(x.get("id")) for x in (question.options or []) if isinstance(x, dict)}
        if payload.selected_option_id not in option_ids:
            raise APIError(422, "invalid_option", "Selected option is not part of this question")
    answer = await db.scalar(select(StudentAnswer).where(StudentAnswer.attempt_id == attempt.id, StudentAnswer.test_question_id == question.id))
    if answer:
        if payload.version != answer.version:
            raise APIError(409, "version_conflict", "A newer answer version exists", {"current_version": answer.version})
        answer.answer_type, answer.selected_option_id, answer.text_answer = payload.answer_type, payload.selected_option_id, payload.text_answer
        answer.version += 1
    else:
        if payload.version != 0:
            raise APIError(409, "version_conflict", "New answers must start at version zero", {"current_version": 0})
        answer = StudentAnswer(attempt_id=attempt.id, test_question_id=question.id, answer_type=payload.answer_type, selected_option_id=payload.selected_option_id, text_answer=payload.text_answer, version=1)
        db.add(answer)
    await db.commit()
    await db.refresh(answer)
    return {"id": answer.id, "test_question_id": answer.test_question_id, "answer_type": answer.answer_type, "selected_option_id": answer.selected_option_id, "text_answer": answer.text_answer, "version": answer.version, "updated_at": answer.updated_at}


@router.post("/attempts/{attempt_id}/submit")
async def submit_attempt(attempt_id: uuid.UUID, db: DB, student: Student):
    attempt = await db.scalar(select(Attempt).where(Attempt.id == attempt_id, Attempt.student_id == student.id).with_for_update())
    if not attempt:
        raise APIError(404, "attempt_not_found", "Attempt not found")
    if attempt.status != AttemptStatus.IN_PROGRESS:
        return {"id": attempt.id, "status": attempt.status, "submitted_at": attempt.submitted_at}
    answer_ids = list((await db.scalars(select(StudentAnswer.id).where(StudentAnswer.attempt_id == attempt.id))).all())
    if answer_ids:
        pending = await db.scalar(select(func.count()).select_from(AnswerImage).where(AnswerImage.answer_id.in_(answer_ids), AnswerImage.status != ImageStatus.READY))
        if pending:
            raise APIError(409, "images_not_ready", "All image operations must finish before submission")
    question_ids = set((await db.scalars(select(TestQuestion.id).where(TestQuestion.test_id == attempt.test_id))).all())
    answers = (await db.scalars(select(StudentAnswer).where(StudentAnswer.attempt_id == attempt.id))).all()
    ready_image_answer_ids = set()
    if answers:
        ready_image_answer_ids = set((await db.scalars(select(AnswerImage.answer_id).where(AnswerImage.answer_id.in_([x.id for x in answers]), AnswerImage.status == ImageStatus.READY))).all())
    answered_question_ids = {
        answer.test_question_id for answer in answers
        if answer.selected_option_id is not None
        or (answer.text_answer is not None and answer.text_answer.strip())
        or answer.id in ready_image_answer_ids
    }
    attempt.status, attempt.submitted_at = AttemptStatus.SUBMITTED, datetime.now(UTC)
    await db.commit()
    return {"id": attempt.id, "status": attempt.status, "submitted_at": attempt.submitted_at, "unanswered_count": len(question_ids - answered_question_ids)}


async def owned_answer(
    db: DB,
    answer_id: uuid.UUID,
    student_id: uuid.UUID,
    *,
    lock_attempt: bool = False,
):
    statement = (
        select(StudentAnswer, Attempt)
        .join(Attempt, Attempt.id == StudentAnswer.attempt_id)
        .where(StudentAnswer.id == answer_id, Attempt.student_id == student_id)
    )
    if lock_attempt:
        # Image mutations and submission serialize on the same Attempt row.
        # Once this lock is acquired, the status check below cannot race with
        # submission and no image change can commit after the attempt locks.
        statement = statement.with_for_update(of=Attempt)
    row = (await db.execute(statement)).first()
    if not row:
        raise APIError(404, "answer_not_found", "Answer not found")
    answer, attempt = row
    if attempt.status != AttemptStatus.IN_PROGRESS:
        raise APIError(409, "attempt_locked", "Submitted attempts are read-only")
    return answer, attempt


@router.post("/answers/{answer_id}/images/upload-url", status_code=201)
async def create_upload(answer_id: uuid.UUID, payload: UploadUrlIn, db: DB, student: Student):
    answer, attempt = await owned_answer(db, answer_id, student.id, lock_attempt=True)
    if answer.answer_type == AnswerType.MCQ:
        raise APIError(422, "image_answer_required", "Images cannot be attached to an MCQ answer")
    settings = get_settings()
    if payload.content_type not in ALLOWED_IMAGE_TYPES:
        raise APIError(422, "unsupported_image_type", "Only JPEG, PNG, and WebP images are supported")
    if payload.byte_size > settings.image_max_bytes:
        raise APIError(422, "image_too_large", "Image exceeds the configured size limit")
    active_filter = (
        AnswerImage.answer_id == answer.id,
        AnswerImage.status.in_([ImageStatus.UPLOADING, ImageStatus.READY]),
    )
    count = await db.scalar(select(func.count()).select_from(AnswerImage).where(*active_filter)) or 0
    if count >= settings.image_max_pages:
        raise APIError(422, "image_page_limit", "Image page limit reached")
    maximum_order = await db.scalar(select(func.max(AnswerImage.page_order)).where(*active_filter)) or 0
    suffix = Path(payload.file_name).suffix.lower()
    object_key = f"answers/{student.id}/{attempt.id}/{answer.id}/{uuid.uuid4()}{suffix}"
    image = AnswerImage(answer_id=answer.id, object_key=object_key, original_filename=Path(payload.file_name).name, media_type=payload.content_type, byte_size=payload.byte_size, page_order=maximum_order + 1)
    db.add(image)
    await db.flush()
    upload_url = await run_storage(
        storage.create_upload_put, object_key, payload.content_type
    )
    await db.commit()
    await db.refresh(image)
    return {
        "image_id": image.id,
        "object_key": object_key,
        "upload_url": upload_url,
        "upload_method": "PUT",
        "required_headers": {"Content-Type": payload.content_type},
        "expires_at": datetime.now(UTC) + timedelta(seconds=settings.s3_signed_url_seconds),
    }


@router.post("/answers/{answer_id}/images/{image_id}/complete")
async def complete_upload(answer_id: uuid.UUID, image_id: uuid.UUID, db: DB, student: Student, payload: CompleteUploadIn | None = None):
    answer, _ = await owned_answer(db, answer_id, student.id, lock_attempt=True)
    image = await db.scalar(select(AnswerImage).where(AnswerImage.id == image_id, AnswerImage.answer_id == answer.id))
    if not image:
        raise APIError(404, "image_not_found", "Image not found")
    if image.status == ImageStatus.READY:
        return {"id": image.id, "status": image.status, "page_order": image.page_order}
    try:
        verified = await run_storage(storage.verify_uploaded_image, image.object_key, image.media_type)
    except APIError as exc:
        # Commit removal of the invalid grant before best-effort object cleanup.
        # A cleanup failure can leave a private orphan for the bucket lifecycle,
        # but cannot leave a database row pointing at a deleted object.
        await db.delete(image)
        await db.commit()
        try:
            await run_storage(storage.delete, image.object_key)
        except Exception:
            pass
        raise exc
    image.byte_size, image.width, image.height, image.checksum = verified.byte_size, verified.width, verified.height, verified.checksum
    image.status = ImageStatus.READY
    await db.commit()
    return {"id": image.id, "status": image.status, "page_order": image.page_order, "width": image.width, "height": image.height}


@router.get("/answers/{answer_id}/images")
async def list_images(answer_id: uuid.UUID, db: DB, student: Student):
    answer, _ = await owned_answer(db, answer_id, student.id)
    images = (await db.scalars(select(AnswerImage).where(AnswerImage.answer_id == answer.id, AnswerImage.status == ImageStatus.READY).order_by(AnswerImage.page_order))).all()
    return {"items": [{"id": x.id, "page_order": x.page_order, "media_type": x.media_type, "byte_size": x.byte_size, "preview_url": await run_storage(storage.create_read_url, x.object_key)} for x in images]}


@router.put("/answers/{answer_id}/images/order")
async def reorder_images(answer_id: uuid.UUID, payload: ImageOrderIn, db: DB, student: Student):
    answer, _ = await owned_answer(db, answer_id, student.id, lock_attempt=True)
    pending = await db.scalar(
        select(func.count()).select_from(AnswerImage).where(
            AnswerImage.answer_id == answer.id,
            AnswerImage.status == ImageStatus.UPLOADING,
        )
    ) or 0
    if pending:
        raise APIError(409, "images_not_ready", "Finish pending uploads before reordering pages")
    images = (await db.scalars(select(AnswerImage).where(AnswerImage.answer_id == answer.id, AnswerImage.status == ImageStatus.READY))).all()
    if set(payload.image_ids) != {x.id for x in images} or len(payload.image_ids) != len(images):
        raise APIError(422, "invalid_image_order", "Image order must contain every ready image exactly once")
    by_id = {x.id: x for x in images}
    # Two-phase order avoids transient collisions if a unique Ready-order index is added later.
    for index, image_id in enumerate(payload.image_ids, 1):
        by_id[image_id].page_order = -index
    await db.flush()
    for index, image_id in enumerate(payload.image_ids, 1):
        by_id[image_id].page_order = index
    await db.commit()
    return {"items": [{"id": x, "page_order": i} for i, x in enumerate(payload.image_ids, 1)]}


@router.delete("/answers/{answer_id}/images/{image_id}", status_code=204)
async def delete_image(answer_id: uuid.UUID, image_id: uuid.UUID, db: DB, student: Student):
    answer, _ = await owned_answer(db, answer_id, student.id, lock_attempt=True)
    image = await db.scalar(select(AnswerImage).where(AnswerImage.id == image_id, AnswerImage.answer_id == answer.id))
    if not image:
        # Completion already removes invalid uploads. Treat a repeated cleanup
        # request as successful after answer ownership has been verified.
        return Response(status_code=204)
    object_key = image.object_key
    await db.delete(image)
    await db.flush()
    remaining = (await db.scalars(
        select(AnswerImage)
        .where(
            AnswerImage.answer_id == answer.id,
            AnswerImage.status == ImageStatus.READY,
        )
        .order_by(AnswerImage.page_order)
    )).all()
    for index, item in enumerate(remaining, 1):
        item.page_order = -index
    await db.flush()
    for index, item in enumerate(remaining, 1):
        item.page_order = index
    await db.commit()
    try:
        await run_storage(storage.delete, object_key)
    except Exception:
        # The database is authoritative. A private orphan is safer than a row
        # that references a missing object and is removed by bucket lifecycle.
        pass


@router.get("/results/{attempt_id}")
async def get_result(attempt_id: uuid.UUID, db: DB, student: Student):
    attempt = await owned_attempt(db, attempt_id, student.id)
    test = await db.get(Test, attempt.test_id)
    result = await db.scalar(select(Result).where(Result.attempt_id == attempt.id, Result.status == ResultStatus.PUBLISHED))
    if not result:
        raise APIError(404, "result_not_found", "Published result not found")
    rows = (await db.execute(select(QuestionEvaluation, TestQuestion).join(TestQuestion, TestQuestion.id == QuestionEvaluation.test_question_id).where(QuestionEvaluation.attempt_id == attempt.id).order_by(TestQuestion.order))).all()
    return {"attempt_id": attempt.id, "test_title": test.title, "awarded_total": result.awarded_total, "max_total": result.max_total, "percentage": result.percentage, "overall_comment": result.overall_comment, "published_at": result.published_at, "questions": [{"test_question_id": q.id, "order": q.order, "question_text": q.text, "status": e.status, "awarded_marks": e.awarded_marks, "max_marks": q.marks, "feedback": e.feedback} for e, q in rows]}

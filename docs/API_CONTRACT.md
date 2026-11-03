# Lotus Smart Study - Shared API Contract

Status: Approved multi-curriculum implementation  
Base path: `/api/v1`

## Conventions

- JSON uses `snake_case` to match FastAPI models. UUIDs and ISO-8601 UTC timestamps are strings.
- Cookie authentication uses an opaque `lotus_session` cookie. Browser requests include credentials.
- Successful deletes/actions may return `204`; other mutations return the updated resource.
- Errors use `{ "error": { "code": "stable_code", "message": "Readable message", "details": {} } }`.
- `401` means no valid session, `403` means wrong role, and ownership-scoped missing records return `404`.
- Versioned autosaves require `version`; a stale version returns `409 version_conflict` with the current version.

## Core enums

- Role: `teacher | student`
- Board: `cbse | state | icse`; State Board also requires `state_code`.
- Class level: integer 8 through 12.
- Syllabus-group/term code: normalized string (existing values remain `term_1` and `term_2`).
- Question type: `mcq | one_mark | two_mark | three_mark | five_mark | case_study`
- Difficulty: `easy | medium | hard | mixed`
- Style: `standard | cbse_style | challenging` (style is a framing request, not a claim of an approved CBSE corpus)
- Question status: `draft | approved | rejected`
- Test status: `draft | published`
- Attempt status: `in_progress | submitted | evaluation_in_progress | evaluated | result_published`
- Evaluation status: `correct | wrong | partial`

## Authentication

- `POST /auth/login` `{login_identifier, password}` -> `{user}` and session cookie.
- Repeated failed login attempts for the same normalized identifier return `429 login_rate_limited`; counters are shared through PostgreSQL and store only an HMAC-derived key.
- `POST /auth/logout` -> `204` and revoked/cleared cookie.
- `GET /auth/me` -> `{user: {id, name, login_identifier, role, must_change_password}}`.
- `POST /auth/change-password` accepts
  `{current_password, new_password, confirm_password}` for an authenticated
  student, revokes all of that student's active sessions, creates one fresh
  session for the caller, and clears `must_change_password`. Permanent
  passwords are 10-256 characters with no whitespace and at least one
  lowercase letter, uppercase letter, number, and symbol.

Students whose `must_change_password` value is true may call only the basic
authentication endpoints needed to inspect the session, change the password,
or log out. All curriculum, test, answer, upload, and result APIs return
`403 password_change_required` until the password is changed.

## Curriculum and textbooks

- `GET /curriculum/options` returns supported board/class selectors and configured curricula.
- `GET /curriculum/subjects?board=&class_level=&state_code=` returns the exact curriculum and its subjects; State Board requires `state_code`.
- `GET /curriculum/subjects/{subject_id}/textbooks` returns processing and indexed-content availability.
- `GET /curriculum/textbooks/{textbook_id}/chapters` returns owned chapters with syllabus-group labels and availability.
- `GET /curriculum/chapters/{chapter_id}/topics` returns enabled topics only.
- Legacy term/chapter endpoints remain available for backward compatibility.
- `GET /teacher/textbooks` lists managed textbook status.
- `POST /teacher/textbooks/upload-url` accepts board/state/class, subject identifier/title, textbook title, year/edition, and PDF metadata; it returns a private raw-byte PUT grant.
- `POST /teacher/textbooks/{textbook_id}/complete` verifies the private PDF and moves it to `uploaded`. Approved extraction/indexing must move it through `processing` to `ready`.
- `POST /teacher/textbooks/catalog` creates or returns textbook metadata for a normalized board, state (when applicable), class, and subject without fabricating curriculum content.
- `POST /teacher/textbooks/{textbook_id}/terms` creates or returns a normalized subject term/syllabus group.
- `GET /teacher/textbooks/{textbook_id}/files?term_id=` lists independently tracked private PDFs and their `uploading | review_required | indexing | ready | failed` status.
- `POST /teacher/textbooks/{textbook_id}/files/upload-url` accepts `{term_id, file_name, content_type: "application/pdf", byte_size}` and returns a presigned raw-byte `PUT` grant plus a file record.
- `POST /teacher/textbooks/{textbook_id}/files/{file_id}/complete` verifies the R2 object, extracts PDF text, and detects one or more chapter boundaries from content. It never derives chapter metadata from the filename.
- `POST /teacher/textbooks/{textbook_id}/files/{file_id}/detect` retries verification and content-based detection without creating chapters or chunks. For a Ready file, it may replace the source index only when none of its chapters has been used by generation or configured with topics; otherwise it returns `409 textbook_file_index_in_use` without changing academic records.
- `POST /teacher/textbooks/{textbook_id}/files/{file_id}/finalize` accepts teacher-reviewed `{chapters: [{code, title, page_start, page_end}]}`. It transactionally creates exact-textbook chapters, source documents, and page chunks and marks the file/book Ready.
- `DELETE /teacher/textbooks/{textbook_id}/files/{file_id}` removes only a non-finalized file record and its private object. Ready files are immutable.

Duplicate PDF checks use the verified checksum within textbook + term. Chapter
codes are unique within textbook + term, page ranges cannot overlap, and an
idempotent repeat of an already finalized payload does not re-index content.

## Generation and review

- `POST /generation-batches` accepts:
  `{textbook_id, chapter_id, topic_id?, counts: {mcq, one_mark, two_mark, three_mark, five_mark, case_study}, marks: {mcq, one_mark, two_mark, three_mark, five_mark, case_study}, difficulty, style}`.
  Counts are non-negative integers with a positive sum, at most 10 per type and
  at most 20 in one batch. Total marks are calculated server-side.
- `GET /generation-batches/{batch_id}` returns configuration, lifecycle status/failure, and teacher question DTOs.
- `GET /generation-batches` returns the authenticated teacher's 10 most recent batches for recovery/navigation.
- `POST /generation-batches/{batch_id}/generate` atomically claims a queued or
  failed batch, returns its Generating state immediately, and runs the slow
  provider work in a background database session. It is idempotent while an
  active generation is running or completed, and safely reclaims an interrupted
  Generating batch after the configured provider-attempt time budget.
- `PATCH /questions/{question_id}` accepts editable text, marks, options/correct option, and reference solution; teacher ownership required.
- `POST /questions/{question_id}/regenerate` creates/returns one replacement Draft with the same scope/type/marks.
- `POST /questions/{question_id}/approve` and `/reject` update status.

Teacher question DTO includes `reference_answer`, `correct_option_id`, scope/provenance, and validation flags. No student endpoint uses this DTO.

## Tests and publication

- `POST /tests` `{generation_batch_id, title, instructions, question_ids, student_ids}` -> Draft test.
- `GET /tests` lists every teacher-owned Draft/Published test with curriculum,
  assignment count, and attempt count.
- `GET /tests/{test_id}` -> teacher-owned Draft/Published test with ordered teacher snapshots.
- `PATCH /tests/{test_id}` edits title/instructions/question order/student assignments only while Draft.
- `POST /tests/{test_id}/assignments` adds active, curriculum-eligible students
  to either a Draft or Published test. It is idempotent and never removes or
  replaces existing assignments or attempts.
- `GET /students?curriculum_id=` -> active eligible students for direct assignment.
- `POST /tests/{test_id}/publish` validates non-empty Approved questions and assignments, freezes snapshots, calculates total marks, and returns Published test. Repeated calls return the same Published resource.

## Student management

All endpoints below require a teacher session. Student DTOs contain
`{id, name, login_identifier, email, mobile, school_name, school_location, curriculum_id, board, state_code, class_level, status, created_at, updated_at}`
and never contain a password hash.

- `GET /teacher/students?search=&status=&limit=&offset=` returns
  `{items, total, limit, offset}`. Search covers name and login ID; status is
  `active` or `inactive` when supplied.
- `POST /teacher/students` accepts `{name, email, mobile?, school_name?, school_location?, curriculum_id, class_level}` and
  returns `{student, temporary_password}`. Email is normalized to lowercase,
  is unique case-insensitively, and becomes the student's login ID. The initial
  password is the lowercase first name plus `123A#`; it is marked temporary,
  returned only in this response, and only its hash is persisted.
- `GET /teacher/students/{student_id}` returns `{student}`.
- `PATCH /teacher/students/{student_id}` accepts a partial update containing
  only name, email, mobile, optional school details, and curriculum profile data; email cannot be cleared.
  A legacy record must include email on its next edit. Changing email atomically
  changes the login ID and revokes active sessions without changing academic
  record IDs. Role, password hash, and status are not editable through this
  payload.
- `POST /teacher/students/{student_id}/activate` and `/deactivate` return
  `{student}` after updating account status without deleting assignments or
  academic history.
- `POST /teacher/students/{student_id}/reset-password` returns
  `{student, temporary_password}` once, revokes existing sessions, and sets
  `must_change_password`. The reset value uses the same lowercase-first-name
  plus `123A#` rule.

Responses containing a temporary password use `Cache-Control: no-store`; the
password is never available from subsequent detail or list requests.

Deactivation atomically revokes active sessions. Inactive users are rejected at
login and by the shared authentication dependency on every protected request.
The existing `GET /students` assignment picker remains active-only.

Legacy students retain their existing login identifier and password after the
migration. A teacher must provide a unique email the next time a legacy record
is edited; that save converts the account to email login without replacing its
password or history.

## Dashboards

- `GET /teacher/dashboard` -> `{total_tests, published_tests, submitted_attempts, pending_evaluation, recent_tests}` scoped to teacher ownership.
- `GET /student/dashboard` -> `{available_tests, completed_tests}` scoped to the session student. Completed items expose result links only after publication.
- `GET /teacher/test-history?student_id=&limit=&offset=` returns permanent
  teacher-owned attempt history, counts, marks and an optional student profile.
- `GET /student/test-history` returns all of the current student's assignments
  and their assigned/in-progress/submitted/evaluated/published state. Marks are
  included only for Published results.

## Student test and autosave

- `GET /student/tests/{test_id}` -> assigned Published test using student-safe snapshots. It never includes reference answers or correct options.
- `POST /student/tests/{test_id}/attempts` -> existing or new single attempt.
- `GET /student/attempts/{attempt_id}` -> attempt, student-safe questions, saved answers, ready images, unanswered count, and the configured `short_answer_max_chars` limit.
- `PUT /student/attempts/{attempt_id}/answers/{test_question_id}` accepts exactly one of `selected_option_id` or `text_answer`, plus `answer_type` and `version`. Empty text is allowed.
- `POST /student/attempts/{attempt_id}/submit` validates no uploading images, then idempotently locks the attempt and returns Submitted status/unanswered count.

## Images

The backend validates attempt ownership/status, JPEG/PNG/WebP content, byte/pixel/page limits, and key scope. On completion it strips metadata, normalizes the longest edge/quality using environment settings, overwrites the private object, and records a server-computed checksum and final dimensions.

- `POST /student/answers/{answer_id}/images/upload-url` `{file_name, content_type, byte_size}` -> `{image_id, object_key, upload_url, upload_method: "PUT", required_headers: {"Content-Type": content_type}, expires_at}`. The browser sends the raw image bytes with PUT using the exact signed headers. Completion performs the authoritative size, type, pixel, and content validation.
- `POST /student/answers/{answer_id}/images/{image_id}/complete` validates the uploaded object and marks it Ready.
- `GET /student/answers/{answer_id}/images` returns ordered image metadata and short-lived preview URLs.
- `PUT /student/answers/{answer_id}/images/order` `{image_ids: [...]}` reorders Ready images.
- `DELETE /student/answers/{answer_id}/images/{image_id}` is allowed only before submission.

## Evaluation and results

- `GET /teacher/evaluations` lists submitted/evaluation-in-progress attempts for owned tests.
- `GET /teacher/attempts/{attempt_id}` returns immutable submitted answers, ordered signed image URLs, maximum marks, and teacher-only reference solutions.
- `PUT /teacher/attempts/{attempt_id}/evaluations/{test_question_id}` accepts `{status, awarded_marks, feedback?, version}`.
  - Correct requires `awarded_marks == max_marks`.
  - Wrong requires `awarded_marks == 0`.
  - Partial requires `0 < awarded_marks < max_marks`.
- `POST /teacher/attempts/{attempt_id}/results/publish` requires every question evaluated, computes the total, persists an immutable Published result, and returns it idempotently.
- `GET /student/results/{attempt_id}` returns only the session student's Published result with total/max/percentage, question-wise status, the student's submitted text/choice/private image links, awarded marks, maximum marks, and teacher feedback. It never includes reference answers or correct choices.

## Cross-cutting invariants

- All teacher records are scoped by `teacher_id`; all student records by the session `student_id` and assignment/attempt ownership.
- All generation scope IDs must share exact Curriculum -> Subject -> Textbook -> Chapter -> optional enabled Topic ancestry and Ready source chunks.
- Published snapshots, submitted answers, and Published results are immutable.
- No endpoint performs AI marking or automatic MCQ scoring.
- No timer, schedule, Twist, result-reopen, or student reference-answer contract exists.

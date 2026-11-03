# Lotus Smart Study - PostgreSQL Schema Contract

Status: Multi-curriculum implementation approved. Migrations are owner-run.

## Identity and curriculum

- `users`: UUID identity, normalized unique login identifier, password hash,
  teacher/student role, active status, password-change flag, timestamps.
- `sessions` and `login_throttles`: revocable hashed sessions and shared
  HMAC-keyed login throttling. No plaintext session token or throttle login is
  stored.
- `curricula`: normalized unique code, `cbse|state|icse`, optional required
  State Board `state_code`, and class level 8-12.
- `subjects`: curriculum FK, normalized code and title; unique per curriculum.
- `textbooks`: subject FK, title, year/edition, private object key/checksum,
  processing status/failure, creator, timestamps; unique title+edition per
  subject.
- `textbook_files`: one independently processed private PDF belonging to a
  textbook and term, with original filename, opaque object key, verified
  checksum/size/pages, lifecycle status, detected and teacher-approved chapter
  JSON, failure detail, creator, and timestamps. Object keys are unique and a
  checksum cannot be repeated within the same textbook and term.
- `student_profiles`: existing student user PK/FK, curriculum FK, class level
  8-12, nullable legacy-compatible email/mobile, case-insensitive unique email.
  A check in application logic requires profile class to equal curriculum class.
- `terms`: subject FK, normalized free-form syllabus-group code, title and
  sequence. Existing `term_1` and `term_2` values are preserved.
- `chapters`: textbook and term FKs, code/title/sequence; chapter code is
  unique within the textbook + term pair.
- `topics`: chapter FK, section code/title/sequence and enablement.
- `source_documents` / `source_chunks`: textbook, term, chapter and optional
  topic ownership plus checksum/version/pages/content/index state. Retrieval
  requires exact ownership and a Ready source document. Newly uploaded
  documents also retain their `textbook_file_id`; one source document per
  uploaded file/chapter prevents retry duplication. Legacy Class 8 source rows
  remain valid with a null file ID.

## Generation, tests, and history

- `generation_batches`: teacher, curriculum, subject, textbook, term, chapter,
  optional topic FKs; count and marks JSONB patterns; difficulty/style;
  provider/version/status/failure metadata.
- `questions`: batch and textbook/term/chapter/topic ownership; type, marks,
  options, teacher solution, lineage, validation and provenance.
- `tests`: teacher/batch plus curriculum/subject/textbook FKs, title,
  instructions, total, status and publication time.
- `test_questions`: immutable ordered publication snapshots including board,
  class, subject, textbook, syllabus group, chapter and topic labels. Teacher
  reference answers remain in teacher-only DTOs.
- `test_assignments`: unique direct test/student assignment. APIs require an
  active student whose curriculum matches the test at draft assignment and
  again at publication.
- `attempts`, `student_answers`, `answer_images`, `question_evaluations`, and
  `results` retain the original immutable submission/manual-evaluation model;
  no academic history is rewritten by curriculum/profile changes.

## Migration ownership

- `0001_class8_pilot_schema.py`: original workflow schema.
- `0002_shared_login_throttling.py`: shared login throttling.
- `0003_student_management.py`: profile/contact/status management.
- `0004_student_email_password_change.py`: email login and temporary-password flow.
- `0005_multi_curriculum_platform.py`: normalized curriculum/subject/textbook
  relationships, Class 8-12 checks, flexible term code, per-batch marks, and
  historical backfill to fixed CBSE Class 8 Mathematics IDs.
- `0006_bulk_textbook_ingestion.py`: independent textbook PDF tracking,
  reviewable detected/approved chapter metadata, source-file lineage, and
  textbook-scoped chapter uniqueness. Existing textbooks, chapters, chunks,
  questions, tests, attempts, and results are not rewritten.

Migrations `0005` and `0006` are forward-only. They do not create dummy curricula or alter
passwords, attempts, answers, marks, results, or existing primary keys.

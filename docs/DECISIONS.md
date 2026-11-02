# Lotus Smart Study - Approved Decisions

Status: Approved implementation baseline  
Approved: 2026-10-31

## Product scope

- The platform supports configured curricula for **Classes 8-12** across CBSE,
  ICSE, and State Boards identified by state/curriculum code.
- Existing CBSE Class 8 Mathematics Term 1 and Term 2 content remains intact
  and is the only content shipped as generation-ready.
- All 16 PRD use cases apply to any curriculum with processed textbook content.
- AI generates draft questions and teacher reference solutions only. Teachers approve every published question and manually evaluate every student answer, including MCQs.
- No authoritative CBSE-pattern claim may be made until approved CBSE reference material is supplied.

## Approved technical decisions

| ID | Decision | Implementation consequence |
|---|---|---|
| D-001 | One Next.js/React/TypeScript frontend, one FastAPI backend, and one PostgreSQL database | Keep the architecture deployable and MVP-focused. |
| D-002 | Local teacher/student accounts | Store password hashes only; authenticate with a shared local user table. |
| D-003 | Secure HTTP-only session cookies | Persist opaque session tokens server-side; use Secure outside local development, SameSite=Lax, configurable expiry, and revoke on logout. |
| D-004 | Direct student assignment | Publish tests to selected student IDs; no class/batch assignment subsystem. |
| D-005 | No timers or scheduling | Published assigned tests remain available until submitted; do not add availability/duration fields or UI. |
| D-006 | Configurable LLM adapter with OpenAI initially | Provider/model/key/base URL/timeouts come from environment variables; provider calls stay backend-only. |
| D-007 | Private S3-compatible answer-image storage | Endpoint, region, bucket, credentials, and signed-URL expiry come from environment variables. Store opaque keys in PostgreSQL. |
| D-008 | JPEG, PNG, and WebP uploads | File-size, page-count, and pixel limits are configurable environment settings. Validate detected content type and image integrity. |
| D-009 | Teacher reference answers remain hidden from students | Student DTOs never contain reference solutions or intended correct MCQ choices, including after result publication. |
| D-010 | Correct/Partial/Wrong marks are deterministic | Correct requires full marks; Wrong requires zero; Partial requires marks strictly between zero and maximum. |
| D-011 | No result reopening | Published results are immutable in the first pilot. |
| D-012 | No Twist action | Implement initial generation and single-question regeneration only. |
| D-013 | Verified Class 8 chapter taxonomy is approved | Numbered textbook sections are selectable topics. Summary-derived or otherwise unverified subtopics remain disabled. |
| D-014 | Exact curriculum filtering | Every generation and retrieval operation is scoped to selected curriculum + subject + textbook + chapter + optional enabled topic. No fallback broadening. |
| D-015 | Immutable publication snapshots | Publishing copies complete student-facing question content and teacher-only reference content into ordered test-question snapshots. |
| D-016 | One attempt per assigned student per test | A uniqueness constraint and idempotent start/submit behavior enforce submit-once workflow. |
| D-017 | Server-backed optimistic autosave | Student answers and teacher evaluations use versioned idempotent updates; submitted answers are immutable. |
| D-018 | Operator-managed source ingestion | No Admin portal. Curriculum seed data and textbook extraction/indexing are development/operations tasks. |
| D-019 | Versioned API and consistent errors | Use `/api/v1`, UUIDs, UTC timestamps, and `{error: {code, message, details?}}`. |
| D-020 | Forward-only migrations | Migration files are created but must not be executed by Codex. |
| D-021 | Generated case-study items default to 5 marks | The PRD defines a case-study count but no separate marks input. Five marks is an editable generation default; the teacher may change it during Draft review before approval/publication. |
| D-022 | The teacher manages student accounts inside the existing teacher workspace | Reuse local `users`, `student_profiles`, password hashing, sessions, and role authorization. Store curriculum eligibility on the profile; use activation/deactivation instead of deletion. This is not a separate Admin portal or academic-year system. |
| D-023 | New student login IDs are normalized, unique email addresses | New and teacher-reset passwords use lowercase first name plus `123A#` and are temporary. Students must replace them with a policy-compliant password before accessing curriculum, tests, uploads, or results. Existing accounts retain their credentials until a teacher supplies an email during edit; no migration invents email data or overwrites a password. Email changes, resets, deactivation, and self-service password changes revoke active sessions. |
| D-024 | Normalize curriculum ownership without replacing historical IDs | `curricula -> subjects -> textbooks -> chapters/source chunks` is the authoritative ancestry. Existing Class 8 records are backfilled to fixed curriculum, subject, and textbook IDs; tests retain immutable scope labels. |
| D-025 | State Boards require a normalized state/curriculum identifier | A generic `state` board value is never sufficient by itself, preventing textbooks from unrelated State Boards from sharing a scope. |
| D-026 | Textbook upload and generation readiness are separate states | Teacher PDF upload is private and verified. Generation is enabled only after approved extraction/indexing marks the book Ready and produces exact-book chapter chunks; no automatic chapter invention is allowed. |
| D-027 | Question patterns are per generation batch | Counts and marks for supported types are stored with each batch instead of enforcing one syllabus-wide distribution. Style is framing only unless an approved pattern corpus exists. |

## Approved lifecycle rules

- Generation batch: `queued -> generating -> completed|failed`.
- Question: `draft -> approved|rejected`; regeneration creates a replacement draft and preserves lineage.
- Test: `draft -> published`; published test content is immutable.
- Attempt: `in_progress -> submitted -> evaluation_in_progress -> evaluated -> result_published`.
- Image: `uploading -> ready|failed`; only ready images permit submission.
- Result: `draft -> published`; published results cannot be reopened.

## Curriculum boundary

- Class: 8, 9, 10, 11, or 12 in a configured curriculum.
- Board: CBSE, ICSE, or State Board with a required state/curriculum identifier.
- Subject, textbook, syllabus grouping, chapter, and optional topic come from
  normalized backend records and exact processed source ownership.
- Existing Class 8 Mathematics chapters and numbered sections remain those
  verified in `docs/IMPLEMENTATION_PLAN.md`.
- Unverified subtopics must be stored as disabled or omitted from selectable curriculum responses.
- Empty curricula may be configured, but cannot generate until real processed
  textbook content is supplied.

## Explicit exclusions

Do not implement a separate Admin portal, academic-year engine, class/batch
assignment, timers, scheduling, reusable question bank/search, Twist action,
result reopening, AI evaluation, automatic MCQ scoring, student-facing
reference answers, parent portal, payments/subscriptions, notifications,
adaptive learning, AI tutor, recommendations, predictive/advanced analytics,
native apps, or PDF paper generation/printing.

## Missing configuration and material

These do not block source implementation, but must be supplied before the relevant manual setup or live workflow:

- PostgreSQL connection URL.
- Session secret and cookie security settings.
- OpenAI API key and approved model; optional compatible base URL.
- S3-compatible endpoint, region, bucket, access key, secret key, and CORS policy.
- Concrete upload limits if defaults are not accepted.
- Pilot teacher/student account credentials or password hashes.
- Approved CBSE reference material. Until supplied, generation is labelled syllabus-grounded, not authoritatively CBSE-pattern-grounded.
- Actual licensed/approved textbooks and chapter boundaries for every intended
  Class 9-12, ICSE, and State Board curriculum. None are fabricated or shipped
  by this change, so those selections cannot generate yet.
- An approved chapter extraction map or operator processing job for each newly
  uploaded whole-book PDF. Upload verification records the book as `uploaded`;
  only reviewed extraction/indexing may create its chapter/source records and
  move it to `ready`.

## Default operational values

Defaults are environment-configurable and documented in `.env.example`:

- Session lifetime: 8 hours.
- Short-answer maximum: 4,000 characters.
- Image maximum: 10 MiB per file, 10 pages per answer, 20 megapixels per image; accepted images are metadata-stripped and normalized to a configurable 3,000-pixel longest edge at configurable quality.
- Signed object URL lifetime: 15 minutes.
- Generation retry count: 2.
- Text autosave debounce: 750 ms.

These defaults do not alter academic rules and can be changed without schema changes.

# Lotus Smart Study - Pilot MVP Implementation Plan

Status: Multi-curriculum expansion implemented - owner build/test/setup validation pending  
Baseline: PRD v1.0, October 2026  
Last updated: 2026-10-31

## 1. Purpose and delivery boundary

This plan coordinates all 16 PRD use cases through the PRD's 10 development
stages. The same teacher-controlled workflow now supports configured Classes
8-12 across CBSE, ICSE, and state-specific State Boards. Existing CBSE Class 8
Mathematics Term 1/Term 2 is preserved as the currently available source. AI
generates draft questions only; teachers approve and manually evaluate.

Planning and shared contracts are approved. Implementation is active. Migration files may be authored, but Codex will not run migrations, builds, tests, application servers, or deployments.

## 2. Architecture baseline

### Runtime components

1. **Next.js application (React and TypeScript)**
   - One responsive web application with public, teacher, and student route groups.
   - Server-backed state for generation, attempts, autosave, evaluation, and results.
   - Separate teacher and student API projections; the browser never filters secrets out of a shared payload.
2. **FastAPI application (Python)**
   - One deployable backend organized into `auth`, `curriculum`, `generation`, `tests`, `attempts`, `evaluations`, `results`, and `storage` modules.
   - The backend is authoritative for role, ownership, lifecycle transitions, marks, totals, and result visibility.
   - A provider-neutral LLM adapter normalizes generation results.
3. **PostgreSQL database**
   - One database containing users, curriculum/source metadata, generation records, tests, attempts, evaluations, and results.
   - Forward-only migrations for every schema change.
4. **Private answer-image storage**
   - Private object storage in deployed environments, accessed through a small storage adapter.
   - PostgreSQL stores opaque object keys and metadata, never image binaries or unrestricted public URLs.
5. **Textbook/source ingestion and retrieval**
   - Preserve the operator-run legacy Class 8 seed ingestion and provide
     teacher-managed private PDF upload, content-based chapter review, and
     approved indexing in the existing Textbooks workspace (not a separate
     administration portal).
   - Textbook chunks carry exact class, subject, term, chapter, topic, document, page, checksum, and index-version metadata.
   - CBSE pattern guidance, when supplied, is a separate corpus that controls framing but cannot broaden syllabus content.

### Request and data flow

`Browser -> Next.js UI -> FastAPI -> PostgreSQL/private storage/LLM provider`

For generation, FastAPI validates the selected curriculum ancestry, retrieves
only exact-textbook chunks, optionally applies separately approved board-pattern
guidance, calls the configured LLM provider, validates structured output and
similarity, then stores Draft questions with source provenance. Publication
creates frozen test-question snapshots; student payloads exclude solutions and
correct MCQ choices.

### Security and lifecycle invariants

- Every protected endpoint enforces role and record ownership server-side.
- Curriculum scope is the exact tuple `class + subject + term + chapter`, plus topic when selected.
- Retrieval never falls back to another class, term, chapter, or topic when content is absent.
- Every generated question starts as Draft; only Approved questions can be published.
- Publishing freezes question text, options, marks, syllabus labels, and the teacher reference solution.
- Students can edit answers and image ordering only while an attempt is In Progress.
- Submission is idempotent and locks all student answers and images.
- Teachers evaluate manually. No AI marking or automatic MCQ scoring is permitted.
- Evaluation totals are computed server-side from teacher-entered marks.
- Students receive only their own published results; draft evaluation data stays hidden.
- Teacher reference answers and correct MCQ choices are never sent in active student-test payloads.

## 3. Verified textbook and syllabus inventory

The repository contains NCERT *Ganita Prakash*, Grade 8, Parts I and II. The directory names `Term1` and `Term2` are adopted as separate pilot syllabus groups. Each group has seven chapter PDFs and one preliminary-material PDF. All 16 PDFs were text-readable during this review.

### Class 8 - Term 1 / Part I

| Chapter | Title | Verified section/topic structure | Source |
|---|---|---|---|
| 1 | A Square and A Cube | Square Numbers; Cubic Numbers; A Pinch of History | `hegp101.pdf` |
| 2 | Power Play | Experiencing the Power Play; Exponential Notation and Operations; The Other Side of Powers; Powers of 10; Did You Ever Wonder?; A Pinch of History | `hegp102.pdf` |
| 3 | A Story of Numbers | Reema's Curiosity; Some Early Number Systems; The Idea of a Base | `hegp103.pdf` |
| 4 | Quadrilaterals | Rectangles and Squares; Angles in a Quadrilateral; Quadrilaterals with Parallel Opposite Sides; Quadrilaterals with Equal Sidelengths; Playing with Quadrilaterals; Kite and Trapezium | `hegp104.pdf` |
| 5 | Number Play | Is This a Multiple Of?; Checking Divisibility Quickly; Digits in Disguise | `hegp105.pdf` |
| 6 | We Distribute, Yet Things Multiply | Some Properties of Multiplication; Special Cases of the Distributive Property; Mind the Mistake, Mend the Mistake; This Way or That Way, All Ways Lead to the Bay | `hegp106.pdf` |
| 7 | Proportional Reasoning-1 | Observing Similarity in Change; Ratios; Ratios in their Simplest Form; Problem Solving with Proportional Reasoning; Sharing, but Not Equally!; Unit Conversions | `hegp107.pdf` |

### Class 8 - Term 2 / Part II

| Chapter | Title | Verified section/topic structure | Source |
|---|---|---|---|
| 1 | Fractions in Disguise | Fractions as Percentages; Percentage of Some Quantity; Using Percentages (including increase/decrease, profit/loss, tax, and compounding in the chapter summary) | `hegp201.pdf` |
| 2 | The Baudhāyana-Pythagoras Theorem | Doubling a Square; Halving a Square; Hypotenuse of an Isosceles Right Triangle; Combining Two Different Squares; Right-Triangles Having Integer Sidelengths; A Long-Standing Open Problem; Further Applications of the theorem | `hegp202.pdf` |
| 3 | Proportional Reasoning-2 | Proportionality - A Quick Recap; Ratios in Maps; Ratios with More than 2 Terms; Dividing a Whole in a Given Ratio; A Slice of the Pie; Inverse Proportions | `hegp203.pdf` |
| 4 | Exploring Some Geometric Themes | Fractals; Visualising Solids (nets, shortest surface paths, orthographic views, and isometric projection are confirmed in the chapter summary) | `hegp204.pdf` |
| 5 | Tales by Dots and Lines | The Balancing Act; Visualising and Interpreting Data (mean/median behavior and line graphs are confirmed in the chapter summary) | `hegp205.pdf` |
| 6 | Algebra Play | Algebra Play; Thinking about "Think of a Number" Tricks; Number Pyramids; Fun with Grids; The Largest Product; Decoding Divisibility Tricks | `hegp206.pdf` |
| 7 | Area | Rectangles and Squares; Triangles; Applications of the triangle-area formula; Triangles between parallel lines; Area of any polygon; Parallelogram; Rhombus; Trapezium; Areas in real life and unit conversion | `hegp207.pdf` |

The numbered book sections are safe initial topics. Parenthetical subtopics taken from explicit chapter summaries or unnumbered headings must be reviewed by a teacher before becoming selectable taxonomy records.

### Missing or insufficient content

- **Classes 9-12 and additional boards:** selectors and normalized setup are
  implemented, but no textbook/chapter content is assumed. Generation remains
  unavailable until approved source material is processed.
- **CBSE pattern/reference guidance:** no separate authoritative CBSE examples or pattern corpus was found. Generation can be textbook-grounded, but the product must not claim a maintained CBSE-style reference grounding until approved material is supplied.
- **Class 12 Term 1 and Term 2 mapping:** intentionally outside the final Pilot scope and must not be inferred.
- **Teacher-approved topic taxonomy:** verified numbered Class 8 sections are approved; unverified summary-derived subtopics remain disabled.
- **Student/user seed data and assignment groups:** absent.

## 4. Shared data model contract

All primary keys are UUIDs. Persist timestamps in UTC and expose ISO-8601 values. Use database foreign keys, uniqueness constraints, and checks alongside application authorization.

| Entity | Minimum contract and important constraints |
|---|---|
| `users` | name, normalized unique login identifier, password hash/auth ID, role `teacher|student`, status `active|inactive` |
| `student_profiles` | unique student user ID, class level, optional section/batch label; no academic-year engine |
| `class_levels` / `subjects` / `terms` | verified pilot catalog; term is class-scoped and unique by class/name |
| `chapters` / `topics` | ordered, stable IDs; chapter belongs to one term and topic to one chapter |
| `source_documents` | class, subject, term, optional chapter, private source path, checksum/version, ingestion status |
| `source_chunks` | document, exact curriculum ancestry, page range, ordered content, retrieval/index reference |
| `generation_batches` | teacher, exact selected scope, immutable configuration, counts/marks/difficulty/style, provider/model/prompt/index versions, status and failure reason |
| `questions` | batch, lineage/replacement ID, type, marks, text, options, intended answer, teacher reference solution, exact scope, difficulty/style, Draft/Approved/Rejected status, source trace, validation flags |
| `tests` | teacher, title, instructions, `draft|published`, total marks, timestamps; scheduling fields only if separately approved |
| `test_questions` | ordered question reference plus a complete frozen snapshot; unique test/order and test/question |
| `test_assignments` | test/student pair, unique per pair |
| `attempts` | test/student, lifecycle status, started/submitted timestamps; unique test/student for one pilot attempt |
| `student_answers` | attempt/test-question, answer type, selected option or text, optimistic version; unique per attempt/question |
| `answer_images` | answer, opaque storage key, detected MIME, size, checksum, dimensions, page order, upload status; unique answer/page order |
| `question_evaluations` | attempt/question, evaluator, `correct|wrong|partial`, awarded marks, feedback, version; unique per attempt/question; `0 <= marks <= maximum` |
| `results` | unique attempt, evaluator, authoritative awarded/max totals, percentage, overall comment, `draft|published`, finalized/published timestamps |

### Lifecycle values

- Generation batch: `queued | generating | completed | failed`
- Question: `draft | approved | rejected`
- Test: `draft | published`
- Attempt: `in_progress | submitted | evaluation_in_progress | evaluated | result_published`
- Image upload: `uploading | ready | failed`
- Result: `draft | published`

Test status intentionally describes the reusable published test, while per-student progress belongs to attempts/results.

## 5. Shared API contract

Use `/api/v1`, JSON request/response bodies, UUID identifiers, ISO-8601 UTC timestamps, a consistent error envelope, and pagination for lists. `PUT` autosaves use a client-supplied version or expected `updated_at` to reject stale writes. Publication/submission endpoints must be naturally idempotent and transaction-backed; an idempotency key may be added for final side effects.

### Common response rules

- Student test DTOs omit teacher solutions and correct MCQ choices.
- Teacher review/evaluation DTOs may include reference solutions only after authorization and ownership checks.
- Ownership failures should not reveal whether another user's record exists.
- Curriculum endpoints return only scopes with successfully indexed content; unsupported Class 12 scope is disabled, not fabricated.
- Errors include stable `code`, human-readable `message`, and optional field `details`.

### Endpoint surface

| Area | Endpoints |
|---|---|
| Auth | `POST /auth/login`, `POST /auth/logout`, `GET /auth/me` |
| Curriculum | `GET /curriculum/classes`, `GET /curriculum/classes/{id}/terms`, `GET /curriculum/terms/{id}/chapters`, `GET /curriculum/chapters/{id}/topics` |
| Generation | `POST /generation-batches`, `GET /generation-batches/{id}`, `POST /generation-batches/{id}/generate` |
| Question review | `PATCH /questions/{id}`, `POST /questions/{id}/regenerate`, `POST /questions/{id}/approve`, `POST /questions/{id}/reject` |
| Tests | `POST /tests`, `GET /tests`, `GET /tests/{id}`, `PATCH /tests/{id}`, additive `POST /tests/{id}/assignments`, `POST /tests/{id}/publish` |
| Teacher workflow | `GET /teacher/dashboard`, `GET /teacher/evaluations`, `GET /teacher/test-history`, `GET /teacher/attempts/{id}`, `PUT /teacher/attempts/{id}/evaluations/{test_question_id}`, `POST /teacher/attempts/{id}/results/publish` |
| Student workflow | `GET /student/dashboard`, `GET /student/test-history`, `GET /student/tests/{id}`, `POST /student/tests/{id}/attempts`, `PUT /student/attempts/{id}/answers/{test_question_id}`, `POST /student/attempts/{id}/submit`, `GET /student/results/{attempt_id}` |
| Answer images | authorize upload, complete/validate upload, list/preview, reorder, replace, and delete routes scoped to the student's In Progress attempt; teacher preview uses a separately authorized read grant |

### Generation request/response rules

The configuration must include class, subject, term, chapter, optional topic, counts for MCQ/1/2/3/5-mark/case-study questions, difficulty, style, and calculated total marks. Structured question output includes text, type, marks, options/correct option when applicable, case-study context/subquestions when applicable, teacher reference answer/solution, exact curriculum IDs, difficulty/style, source chunk IDs, and validation flags.

Before storage, validate schema, requested count/type/marks, MCQ option uniqueness and one intended answer, case-study coherence, source ancestry, reference-solution presence, duplicates/near-duplicates, and number-only variation. Failure after bounded retries is visible to the teacher and never silently broadens retrieval scope.

## 6. Ten-stage milestone plan

Agent ownership below is for implementation coordination. The Main Coordinator owns contracts, integration, dependency gates, and use-case acceptance. Frontend, Backend/Database, and AI agents work only after their dependencies are resolved and avoid simultaneous edits to shared files.

| Stage | Status | Primary owner | Deliverables | Dependencies | UC coverage / exit condition |
|---|---|---|---|---|---|
| 1. Foundation | Implemented; owner validation pending | Backend + Frontend | Local accounts, hashed passwords, opaque HTTP-only sessions, role authorization, role layouts and dashboards | Runtime database/accounts | UC-01, UC-02 implemented |
| 2. Test & Question Models | Implemented; migration not executed | Main + Backend/DB | Explicit PostgreSQL/Alembic schema, curriculum/source, generation, test, assignment and frozen snapshot models | Owner applies migration and ingestion | Models/contracts implemented |
| 3. AI Generation | Implemented; live provider validation pending | AI + Backend + Frontend | PDF ingestion, exact-scope retrieval, OpenAI Responses adapter, structured validation, similarity checks and single-question regeneration | Runtime OpenAI key/model and ingested PDFs | UC-05, UC-06 implemented; authoritative CBSE claim withheld |
| 4. Review / Publish | Implemented; owner validation pending | Frontend + Backend | Edit/approve/reject/regenerate, direct assignment, approval gate and immutable publication snapshots | Live generated drafts/accounts | UC-07, UC-08 implemented |
| 5. Student Test | Implemented; owner validation pending | Frontend + Backend | Assigned start, one attempt, student-safe snapshots, serialized versioned MCQ/text autosave and navigation | Published assigned test | UC-09, UC-10 implemented |
| 6. Photo Answers | Implemented; owner storage validation pending | Frontend + Backend/Storage | Mobile input, signed private upload, content verification, metadata stripping/normalization, ordered preview/reorder/remove and teacher zoom | Configured private S3-compatible bucket/CORS | UC-11 implemented |
| 7. Submission | Implemented; owner validation pending | Backend + Frontend | Unanswered confirmation, pending-image guard, idempotent transactional lock and evaluation queue | Completed owner walkthrough | UC-12 implemented |
| 8. Manual Evaluation | Implemented; owner validation pending | Frontend + Backend | Immutable answer sheet, private image access, Correct/full, Wrong/zero, Partial/intermediate marks, feedback and versioned autosave | Submitted attempts | UC-13, UC-14 implemented |
| 9. Results | Implemented; owner validation pending | Backend + Frontend | Completeness validation, authoritative total, idempotent immutable publication and student-only result history/detail | Fully evaluated attempts | UC-15, UC-16 implemented |
| 10. Pilot Hardening | Technical-review remediation implemented; owner runtime validation pending | Main + Review agent + all owners | Ownership review, DTO alignment, strict provider schema, bounded generation, concurrency locks, durable autosave recovery, upload policy/normalization, responsive UI, backup and manual setup runbooks | Owner executes build/test/migration/end-to-end checklist | C-01, H-01-H-06, M-01-M-11 and Low findings remediated in source |

Per project instruction, Codex will not run builds, tests, deployments, or production migrations. The project owner performs final validation commands and release operations.

## 7. Use-case coverage matrix

| UC | Planned components | Stage | Status |
|---|---|---|---|
| UC-01 Teacher Login | Shared auth, active/role checks, teacher redirect, logout | 1 | Implemented; owner validation pending |
| UC-02 Student Login | Shared auth, student scoping, wrong-role block | 1 | Implemented; owner validation pending |
| UC-03 Teacher Dashboard / KPIs | Ownership-scoped aggregates, recent tests, pending queue | 2-4 | Implemented; owner validation pending |
| UC-04 Student Dashboard / Result Access | Assigned available/submitted tests and published-only result history | 4, 9 | Implemented; owner validation pending |
| UC-05 Configure Question Generation | Cascading term/chapter/enabled-topic selector and validated stored configuration | 2-3 | Implemented; owner validation pending |
| UC-06 Generate Random Questions | Exact retrieval, provider adapter, validation, provenance, similarity checks, single-item regeneration | 3 | Implemented; live LLM validation pending and authoritative CBSE-pattern claim withheld |
| UC-07 Review / Edit / Regenerate / Approve | Teacher-only review DTO and lifecycle actions | 4 | Implemented; owner validation pending |
| UC-08 Publish Test | Approval gate, direct assignment, frozen snapshot transaction | 4 | Implemented; owner validation pending |
| UC-09 Student Answers MCQ | Student-safe options and serialized versioned autosave | 5 | Implemented; owner validation pending |
| UC-10 Student Types Short Answer | Debounced/serialized autosave, flush and exact submitted value | 5 | Implemented; owner validation pending |
| UC-11 Handwritten Photos | Private ordered normalized multi-image lifecycle and mobile preview | 6 | Implemented; owner S3 validation pending |
| UC-12 Submit Test | Confirmation/unanswered count, ready-upload guard and idempotent lock | 7 | Implemented; owner validation pending |
| UC-13 Open Student Answer Sheet | Read-only answer projection, ordered signed gallery/zoom, teacher solution | 8 | Implemented; owner validation pending |
| UC-14 Manual Mark Entry | Manual status/marks/feedback autosave and deterministic constraints | 8 | Implemented; owner validation pending |
| UC-15 Finalize / Publish Result | Completeness check, authoritative total and idempotent immutable release | 9 | Implemented; owner validation pending |
| UC-16 Student Views Result | Own published result, total/percentage/question detail without references | 9 | Implemented; owner validation pending |

## 8. Parallel-agent findings integrated

### Frontend analysis

- Use explicit server lifecycle statuses, per-answer save/upload indicators, and a page-level "all changes saved" state.
- Debounce text saves, save MCQ selections immediately, flush before navigation/submission, and block submission while operations are unresolved.
- Mobile uploads need camera hints, multi-page thumbnails, ordering, replace/remove, progress, retry, and readable zoom.
- Class 12 must not show invented selectors; unavailable content should be clearly disabled.

### Backend/database analysis

- Use unique constraints and transactions for one attempt per test/student, one answer/evaluation per attempt/question, idempotent submission/publication, and ordered images.
- Store published test-question snapshots so later edits or re-indexing cannot alter student history.
- Keep answer images private and issue only short-lived authorized upload/read access.
- Derive live KPIs from authoritative records and persist published result totals as a release snapshot.

### AI generation analysis

- Persist provider/model, prompt/index version, source chunks, operation type, lineage, and validation outcome.
- Apply exact metadata filters before semantic ranking; absence of content is a hard failure, not a reason to broaden scope.
- Keep any approved board-pattern guidance separate from textbook content.
- Regenerate replaces one item while retaining scope/type/marks. Twist is excluded from the first pilot.
- Similarity checks are quality gates, not proof of mathematical correctness; teacher approval remains authoritative.

## 9. MVP exclusion guardrail

Do not plan or implement an Admin portal, academic-year engine, reusable enterprise question bank/search, AI evaluation, automatic MCQ scoring, parent portal, payments/subscriptions, notifications, adaptive learning, tutoring, recommendations, predictive/advanced analytics, native apps, PDF question-paper/printing, other boards/subjects/classes, or complex scheduling. Internal provenance and duplicate-detection history are generation infrastructure, not a user-facing question bank.

## 10. Blocking inputs and next safe work

Approved implementation decisions are tracked in `docs/DECISIONS.md`. Missing runtime configuration includes PostgreSQL, OpenAI, session, and S3-compatible storage credentials. Approved CBSE pattern material is still absent, so the product must describe generation as textbook/syllabus-grounded rather than authoritatively CBSE-pattern-grounded.

Shared contracts are approved and Stages 1-10 may proceed for Class 8. Verified numbered topics are enabled; unverified subtopics remain disabled. Class 12, scheduling/timers, Twist, and result reopening are outside scope.

## 11. Implementation progress log

### 2026-10-31 - Stages 1-2

- Added the Next.js and FastAPI application foundations, local account/session authorization, PostgreSQL models, stable shared DTO conventions, explicit forward-only Alembic baseline, approved Class 8 taxonomy, and account/curriculum operator tooling.

### 2026-10-31 - Stages 3-4

- Added verified-PDF ingestion, exact Term/Chapter/enabled-Topic retrieval, configurable OpenAI adapter, structured generation validation/provenance/similarity, teacher review/regeneration/approval, direct assignment, and immutable publication snapshots.

### 2026-10-31 - Stages 5-7

- Added assigned student attempts, serialized optimistic MCQ/text autosave, mobile notebook-image upload and normalization, ordered page management, unanswered confirmation, and idempotent read-only submission.

### 2026-10-31 - Stages 8-9

- Added the teacher answer sheet and private image viewer, deterministic manual marking with feedback, evaluation autosave, server-calculated totals, immutable result publication, and published-only student history/detail.

### 2026-10-31 - Stage 10

- Completed static multi-agent integration review and repaired DTO mismatches, question replacement filtering, generation/autosave concurrency, image failure/order handling, scope leakage risks, and setup/backup documentation.
- No build, test, migration, application server, provider call, or deployment was executed. Runtime acceptance remains the project owner's required next step using `docs/MANUAL_SETUP.md`.

### 2026-11-01 - Final technical-review remediation

- Fixed C-01 by normalizing every OpenAI strict Structured Outputs object to
  require every property and reject additional properties, while preserving
  nullable values through the generated schema.
- Fixed H-01-H-06: bounded generation batches, atomic save-before-approve,
  persisted-only evaluation publication, durable local answer-draft recovery,
  attempt-row serialization for every image mutation, and pre-decode image
  dimension/decompression validation.
- Fixed M-01-M-11: serialized page allocation, database-first object deletion,
  completion-validated presigned PUT uploads, question/publication row locking,
  ingestion topic coverage checks, current-source filtering, teacher-edit
  provenance, a shared retry budget, a teacher-visible recent-batch recovery
  list, server-led answer limits, and PostgreSQL-backed account throttling
  shared across API workers.
- Fixed all Low findings: duplicate question validation, global expired-session
  handling, and consistent generation setting validation.
- Added the forward-only `0002_shared_login_throttling` migration; it has not
  been executed. Shared contracts and setup instructions now describe the
  additive upload grant fields and answer-length value.
- No build, test, dependency installation, migration, server, provider call, or
  deployment was executed. All runtime acceptance remains owner-run.

### 2026-11-02 - Student management

- Added teacher-managed Class 8 student account listing, search/status filters,
  create/edit, activation/deactivation, and password reset inside the existing
  teacher workspace.
- Reused the local user, password-hashing, session, role, and login-throttling
  infrastructure. Deactivation and password reset revoke active sessions;
  inactive users remain blocked on every authenticated request.
- Preserved the active-only direct-assignment picker and all historical tests,
  attempts, answers, evaluations, images, and results. Student deletion and role
  modification are not exposed.
- Added forward-only migration `0003_student_management`; it has not been
  executed. Runtime validation remains owner-run.

### 2026-11-02 - Student email login and temporary-password enforcement

- Made normalized email mandatory and case-insensitively unique for newly
  managed students; it is now their login ID. Email edits update the same user
  record and preserve all academic foreign-key relationships.
- Added deterministic initial/reset credentials using lowercase first name plus
  `123A#`, one-time teacher display, immediate session revocation, and a
  `must_change_password` account flag.
- Added the student password-change screen and API. Temporary-password sessions
  are restricted to authentication/password-change operations until a secure
  permanent password is set; successful changes rotate the caller's session
  after revoking every prior session.
- Preserved legacy identifiers and password hashes. A legacy student without an
  email continues to log in as before and is converted only when a teacher
  supplies a unique email during edit.
- Restricted the operator seed script to curriculum and teacher bootstrap;
  fresh students must use the managed API/UI so the email and forced-change
  invariants cannot be bypassed.
- Added forward-only migration `0004_student_email_auth` in
  `0004_student_email_password_change.py`; it has not been executed. No build,
  test, migration, server, or deployment command was run.

### 2026-11-02 - Premium Lotus visual system

- Applied the official `lotus_logo_new.png` identity to login and authenticated
  teacher/student navigation, and added matching application metadata/icons.
- Replaced the previous theme with reusable white, blue, navy, green, slate,
  semantic-status, focus, border, shadow, spacing, and radius tokens.
- Added a responsive desktop sidebar/mobile navigation treatment while keeping
  all existing routes, role gates, forms, APIs, and workflows unchanged.
- Unified dashboards, KPI cards, controls, tables, badges, question cards,
  uploads, dialogs, pagination, loading, validation, and destructive actions.
- No dependency, backend, API, database, build, test, server, or deployment
  change was made. Visual/runtime validation remains owner-run.

### 2026-11-02 - Multi-board, multi-class platform expansion

- Added normalized curriculum, subject, and textbook ownership for Classes
  8-12 across CBSE, ICSE, and state-identified State Boards. Migration
  `0005_multi_curriculum_platform.py` backfills every existing Class 8 source,
  batch, question, test, student profile, and publication snapshot without
  replacing historical IDs.
- Replaced fixed generation selection with Board -> Class -> Subject ->
  Textbook -> Chapter -> optional Topic. Empty/unprocessed sources are visible
  but generation remains disabled; exact ancestry is revalidated server-side.
- Added teacher-only private textbook PDF upload grants, PDF verification,
  metadata/status tracking, and an explicit uploaded-to-indexing handoff. No
  textbook, chapter, or subject content is fabricated.
- Generalized prompts, provenance, retrieval, per-batch marks patterns, test
  scope snapshots, student eligibility, dashboards, student management, and
  assignment selection. Existing answer, upload, manual evaluation, result,
  and password workflows remain unchanged.
- Preserved the verified CBSE Class 8 Mathematics corpus as the only preloaded
  Ready textbook. Additional curricula become generation-ready only after a
  teacher reviews detected PDF chapter boundaries and approves exact-book
  extraction/indexing.
- All 16 use cases retain coverage for every generation-ready curriculum. No
  build, test, migration, server, ingestion, provider call, or deployment was
  executed; owner validation remains required.

### 2026-11-03 - Bulk textbook upload and reviewed chapter indexing

- Added dependent Board -> Class -> Subject -> Textbook -> Term management and
  multi-PDF selection in the existing teacher Textbooks workspace.
- Each PDF now receives an independent private R2 raw-byte PUT grant and a
  durable upload/detection/indexing status with teacher-visible failure and
  retry controls.
- Added content-based PDF chapter candidate detection supporting one or many
  chapters per file. Filenames are not used as academic metadata; teachers edit
  chapter number, title, and page boundaries before approval.
- Finalization transactionally creates textbook/term-scoped chapters, source
  documents, and page chunks. Verified checksums, scoped unique constraints,
  source-file lineage, row locking, and immutable Ready files prevent duplicate
  chapters and repeated indexing on retry.
- Preserved the existing Class 8 catalog and legacy ingestion pipeline. No
  build, test, migration, server, provider call, or deployment was executed.
  Owner-run migration and runtime validation remain required.

### 2026-11-03 - Textbook chapter conflict remediation

- Tightened PDF chapter detection after Class 12 chapter-only books exposed a
  false-boundary case: running headers, body references to another chapter, and
  later numbered sections can no longer create chapter candidates by
  themselves. Detection now requires page-opening `Chapter/Unit` evidence or
  the first `x.1` section near the top of a page; trailing title numbers only
  corroborate those signals.
- Added a per-file **Re-detect chapters** action so already uploaded PDFs can
  use corrected detection without re-uploading, and moved finalize errors next
  to the affected file instead of only at the top of the page.
- Added guarded recovery for Ready files created by the earlier detector. A
  teacher may re-detect and replace an unused source index; the backend blocks
  replacement if any affected chapter has a generation batch, question, or
  configured topic, preserving all academic records.
- Duplicate chapter responses now identify the existing source file when
  available. Database integrity conflicts log only exception type, constraint
  name, and file UUID—never PDF text, prompts, credentials, or secrets.
- No build, test, migration, server, or deployment was executed.

### 2026-11-03 - Permanent history, additive assignments, and school details

- Confirmed attempts, answers, evaluations, marks, and results have no
  time-based deletion path. Added explicit teacher and student history APIs and
  screens so older and result-published records are no longer hidden by recent
  dashboard/evaluation queries.
- Added teacher-wide and per-student attempt history with answered/unanswered
  counts, marks, statuses, and read-only answer/evaluation detail. Published
  student result detail now includes the student's own submitted answers and
  private signed image links while continuing to hide reference answers.
- Added a complete teacher test list and additive assignment controls for Draft
  and Published tests. Duplicate assignments remain prevented by the existing
  unique constraint; prior assignments, attempts, marks, and results are never
  replaced.
- Added optional school name and location to student create/edit/list/profile
  contracts through forward-only migration `0007_student_school_fields.py`.
- No build, test, migration, server, or deployment was executed. The owner must
  apply migration `0007` and perform the documented manual workflow checks.

### 2026-11-03 - Production generation timeout remediation

- Removed the long OpenAI call from the lifetime of the browser/proxy request.
  Generation now claims the batch transactionally, returns Generating
  immediately, and completes through a separate backend database session while
  the existing review page polls durable status.
- Added idempotent active-batch handling and conservative stale-generation
  recovery based on the configured provider timeout and total retry budget, so
  a worker interruption cannot leave a batch permanently stuck in Generating.
- Kept provider retry limits, structured-output validation, textbook scope,
  diagnostic logging, and question-count/marks behavior unchanged. No prompt,
  textbook content, credentials, or student data is written to the new
  background boundary log.
- No build, test, migration, server, provider call, or deployment was executed.

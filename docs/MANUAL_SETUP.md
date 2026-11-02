# Lotus Smart Study - Manual Setup and Validation

All commands in this document are for the project owner to run. Codex did not
execute them.

## 1. Required services and credentials

- PostgreSQL database and credentials.
- OpenAI API key and an approved Responses API model.
- Private S3-compatible bucket with access credentials.
- HTTPS in production so the HTTP-only session cookie is also Secure.

The existing CBSE Class 8 Mathematics corpus is the only preloaded content.
Other boards/classes are available for curriculum setup but require real,
approved textbook content before generation. Until separate pattern references
are supplied, describe output as textbook-grounded rather than authoritatively
board-pattern-grounded.

## 2. Backend configuration

1. Create a Python virtual environment.
2. Install `backend/requirements.txt`.
3. Copy `backend/.env.example` to `backend/.env`.
4. Set at least:
   - `DATABASE_URL`
   - a strong random `SESSION_SECRET`
   - `FRONTEND_ORIGIN`
   - `OPENAI_API_KEY` and `OPENAI_MODEL`
   - `S3_ENDPOINT_URL`, `S3_REGION`, `S3_BUCKET`, `S3_ACCESS_KEY_ID`, and
     `S3_SECRET_ACCESS_KEY`
   - review `LOGIN_MAX_FAILURES` and `LOGIN_FAILURE_WINDOW_SECONDS` for the
     pilot account policy
5. For production set `ENVIRONMENT=production` and `COOKIE_SECURE=true`.

`OPENAI_BASE_URL` is an origin without `/v1`. The adapter appends
`/v1/responses`.

## 3. Database and curriculum

From `backend/`, after creating the empty database:

1. Apply the migration manually with `alembic upgrade head`.
2. Ingest the verified textbooks with:
   `python -m app.generation.cli --source-root ../docs/resources/textbooks`
3. Create the initial teacher with the seed script. Example:
   `python scripts/seed_pilot.py --teacher-login teacher --teacher-password <password> --teacher-name "Pilot Teacher"`
4. After startup, create every new student through the teacher's Students page
   so mandatory email login and temporary-password change rules are applied.
   Existing student rows from earlier migrations remain untouched.

The migration chain includes `0002_shared_login_throttling`, which stores only
HMAC-derived login throttle keys and counters so limits are shared by all API
workers, and `0003_student_management`, which adds optional contact fields and
backfills any missing Class 8 student profiles. It also includes
`0004_student_email_auth`, which adds the temporary-password flag, widens login
IDs for email addresses, and adds a case-insensitive unique index for non-null
student emails. Existing login identifiers and password hashes are not changed.
Codex created but did not execute these migrations.

The chain also includes `0005_multi_curriculum`, implemented in
`0005_multi_curriculum_platform.py`. It creates curriculum, subject, and
textbook ownership; permits Classes 8-12; converts term codes to flexible
normalized strings; and backfills all existing records to the preserved CBSE
Class 8 Mathematics textbook. Review a backup before applying it.

Before applying `0004`, check for duplicate non-null student emails and resolve
them deliberately if this query returns rows:

```sql
SELECT lower(email) AS normalized_email, count(*)
FROM student_profiles
WHERE email IS NOT NULL
GROUP BY lower(email)
HAVING count(*) > 1;
```

The legacy ingestion command seeds only the approved existing Class 8 Term
1/Term 2 catalog and numbered topics, then extracts those PDFs into exact-book
source chunks. Additional PDFs can be uploaded from Teacher -> Textbooks, but
remain `uploaded` and unavailable for generation until an approved operator
extraction/indexing step creates their true chapters/chunks and marks them
`ready`. Do not manually mark a book Ready without indexed content.

## 4. Private image storage

- Keep the bucket private and disable public object access.
- Permit signed `PUT` requests from the configured frontend origin for
  `image/jpeg`, `image/png`, `image/webp`, and textbook `application/pdf`, including the `Content-Type`
  request header. Keep public object access disabled.
  For local development, the R2 dashboard CORS JSON must include the exact
  browser origin (with no trailing slash):

  ```json
  [
    {
      "AllowedOrigins": ["http://localhost:3000"],
      "AllowedMethods": ["PUT", "GET", "HEAD"],
      "AllowedHeaders": ["Content-Type"],
      "ExposeHeaders": ["ETag"],
      "MaxAgeSeconds": 3600
    }
  ]
  ```
- Permit the backend credentials to put, get, head, and delete objects only in
  the configured bucket/prefix.
- Configure a lifecycle rule for abandoned/incomplete uploads.
- Review `IMAGE_MAX_BYTES`, `IMAGE_MAX_PAGES`, `IMAGE_MAX_PIXELS`,
  `IMAGE_MAX_DIMENSION`, `IMAGE_QUALITY`, and `S3_SIGNED_URL_SECONDS`.
- Follow `backend/BACKUP.md` so database rows and object versions are backed up
  and restored as one logical set.

## 5. Frontend configuration

1. Install dependencies from `frontend/package.json`.
2. Copy `frontend/.env.example` to `frontend/.env.local`.
3. Set `NEXT_PUBLIC_API_BASE_URL` to the FastAPI `/api/v1` URL.
4. Keep `NEXT_PUBLIC_TEXT_AUTOSAVE_MS=750` unless pilot observation justifies a
   change.

## 6. Owner-run build and launch

After configuration, the owner may run the backend/frontend build, lint, test,
migration, and launch commands. The FastAPI CORS origin must exactly match the
frontend origin and browser requests must include credentials.

## 7. Manual acceptance walkthrough

Verify in order:

1. Teacher and student can log in, see only their role area, and log out; repeated
   failed logins reach the configured account throttle without exposing a
   plaintext identifier in `login_throttles`.
2. Teacher can create a student in a configured Class 8-12 curriculum with a unique email, and the normalized
   email is the login ID. Confirm the one-time temporary password is lowercase
   first name plus `123A#`.
3. A new/reset student can authenticate but is redirected to Change Password;
   curriculum, tests, uploads, and results reject access until a 10-256
   character password with lowercase, uppercase, number, symbol, and no
   whitespace is accepted.
4. A successful student password change invalidates other sessions and keeps
   one rotated session for the caller. Teacher reset again invalidates all
   sessions, displays the deterministic temporary password once, and restores
   the mandatory-change state.
5. Changing a student's email changes the login ID, rejects a duplicate email,
   invalidates old sessions, and preserves assignments and academic history.
   Confirm a legacy account still uses its old credentials until a teacher edit
   supplies its missing email.
6. Teacher can edit contact details, search/filter the list, and reset any
   student's password.
7. Deactivation immediately rejects an existing student session and excludes
   the student from new assignments; reactivation permits login without
   deleting historical attempts, answers, marks, or results.
8. Teacher KPIs reflect owned tests and submissions.
9. Teacher selects Board, Class, Subject, Textbook, Chapter, and optionally an
   enabled topic. Verify State Board requires a state/curriculum identifier,
   mismatched IDs are rejected, and missing/unprocessed content disables
   generation. Confirm existing CBSE Class 8 content still generates.
10. Generated questions are Draft, source-traceable, materially varied, and
   include teacher-only reference solutions.
   Confirm a queued, running, failed, or completed batch remains discoverable
   from the teacher dashboard after leaving its batch page.
11. Teacher can edit, regenerate one Draft question, approve/reject, directly
   assign students, and publish only an all-approved non-empty test.
12. Assigned students alone can start the frozen test.
13. MCQ and typed answers autosave and survive navigation/refresh without
   revealing intended answers.
14. Written questions accept ordered JPEG/PNG/WebP notebook pages with preview,
   reorder, removal/replacement, presigned raw-byte PUT upload,
   normalization, and teacher zoom.
15. Submit warns about unanswered questions, waits for saves/uploads, is
   idempotent, and locks answers.
16. Teacher sees immutable submitted answers and manually saves Correct/full,
    Wrong/zero, or Partial/intermediate marks plus optional feedback.
17. Result publication is blocked until every question is marked, calculates
    the teacher-entered total, and is idempotent.
18. Only the owning student sees the Published result and question-wise marks;
    reference answers remain hidden.

Also confirm that no timer, schedule, Twist action, result reopen flow,
automatic MCQ scoring, or AI evaluation is present.

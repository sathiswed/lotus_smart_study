# Lotus Smart Study Backend

FastAPI/PostgreSQL backend for textbook-grounded Classes 8-12 assessment. The source includes a
forward-only Alembic baseline and operator scripts; no migration or seed action
is automatic.

## Manual setup

1. Create a Python virtual environment and install `requirements.txt`.
2. Copy `.env.example` to `.env` and provide PostgreSQL, session, OpenAI, and
   private S3-compatible storage values.
3. Create the PostgreSQL database.
4. From this directory, manually run `alembic upgrade head`.
5. Manually ingest the existing approved Class 8 source PDFs with
   `python -m app.generation.cli --source-root ../docs/resources/textbooks`.
6. Manually run `python scripts/seed_pilot.py` with optional teacher account
   arguments shown by `--help`, then create students through the teacher
   Students page.
7. Start the API manually with your preferred ASGI command.

`OPENAI_BASE_URL` may be the provider origin (for example,
`https://api.openai.com`) or its API base (`https://api.openai.com/v1`); the
adapter resolves the Responses API path without duplicating `/v1`. The application describes generated content as
textbook-grounded until a separate approved board-pattern corpus is
provided.

The storage bucket must be private. Configure bucket CORS to permit signed
PUT requests only from the frontend origin, including the `Content-Type` request
header, plus private signed GET/HEAD access as required. Upload completion
performs authoritative byte, type, pixel, and image-content validation.
Production should set `ENVIRONMENT=production`, `COOKIE_SECURE=true`, a strong
session secret, HTTPS, and restricted database/storage credentials.

The application deliberately does not create tables or accounts at startup.
Teacher textbook uploads are private and remain unavailable for generation
until approved extraction/indexing creates exact-book chapter chunks and marks
the textbook Ready.

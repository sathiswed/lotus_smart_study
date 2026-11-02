# Lotus Smart Study frontend

Responsive Next.js App Router client for the Lotus multi-curriculum platform.

The interface uses the official `public/lotus_logo_new.png` brand asset and a
shared white-and-blue design system defined in `app/globals.css`. Deep navy is
used for hierarchy, green is reserved for positive states, and all existing
teacher/student routes share the same responsive navigation and controls.

## Manual setup

1. Copy `.env.example` to `.env.local` and set `NEXT_PUBLIC_API_BASE_URL` to the FastAPI `/api/v1` URL.
2. Install dependencies with the project owner's package manager.
3. Ensure the FastAPI CORS configuration allows the frontend origin with credentials.
4. The owner may then run lint/build/dev commands as part of manual verification. Codex intentionally did not run them.

Authentication uses the backend's HTTP-only `lotus_session` cookie. The browser API client always sends credentials. Teacher reference answers appear only in teacher review/evaluation routes and are absent from all student types and screens.

New students use their normalized email address as the login ID. Initial and teacher-reset passwords are temporary; the frontend confines those students to the password-change route until they choose a secure replacement. Legacy students keep their existing login identifier until a teacher supplies an email while editing the record.

## Implemented routes

- `/`: teacher/student login.
- `/teacher`: KPI dashboard.
- `/teacher/generate`: Board/Class/Subject/Textbook/Chapter generation configuration.
- `/teacher/textbooks`: private textbook upload and processing availability.
- `/teacher/batches/[id]`: edit, regenerate, approve/reject, and direct assignment.
- `/teacher/tests/[id]`: review and immutable publication.
- `/teacher/evaluations` and `/teacher/evaluations/[id]`: manual marking and result publication.
- `/teacher/students`: teacher-only student search, profile/status management, and one-time generated credentials.
- `/student`: available/completed test dashboard.
- `/student/change-password`: required first-login password change and voluntary authenticated password change.
- `/student/tests/[id]`: instructions and attempt start.
- `/student/attempts/[id]`: versioned autosave, image upload/order/removal, and idempotent submission.
- `/student/results/[id]`: published result detail without reference answers.

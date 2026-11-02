# Lotus Smart Study — Codex Development Instructions

## Source of Truth
- Read `docs/PRD.md` completely before implementation.
- Implement all 16 use cases and acceptance criteria.
- Follow the 10 development stages in the PRD.
- Do not add features explicitly excluded from the Pilot MVP.

## Technology Stack
- Frontend: Next.js, React, TypeScript
- Backend: Python FastAPI
- Database: PostgreSQL
- AI: Configurable LLM provider integration
- File storage: Private storage for student answer images

## Architecture
- Keep the architecture simple and MVP-focused.
- Use one FastAPI backend and one PostgreSQL database.
- Define shared API contracts before parallel implementation.
- Use database migrations for schema changes.
- Keep secrets and API keys in environment variables.

## Multi-Agent Execution
- Main agent owns architecture, planning, coordination, and integration.
- Delegate independent frontend, backend, AI, and review tasks to subagents.
- Parallelize only tasks without unresolved dependencies.
- Avoid multiple agents modifying the same files simultaneously.
- Maintain `docs/IMPLEMENTATION_PLAN.md` with task status and dependencies.
- Maintain `docs/DECISIONS.md` for technical decisions and unresolved requirements.

## Functional Rules
- AI generates questions only, never final student marks.
- Teachers must approve questions before publication.
- Student answers must be autosaved.
- Submitted answers must become read-only.
- Student results remain hidden until teacher publication.
- Maintain strict teacher/student role authorization.
- Support mobile-friendly photo uploads for handwritten solutions.
- Never expose teacher reference answers during an active student test.

## Development Rules
- Implement the smallest complete solution for each requirement.
- Avoid unnecessary abstractions and dependencies.
- Do not invent missing academic rules or source content.
- Record blocking decisions and ask for clarification when required.
- Continue to the next unblocked implementation task automatically.
- Do not run builds, tests, deployments, or production migrations.
- Do not modify unrelated functionality.

## Completion
- Map implemented features against all PRD use cases.
- Report completed, pending, and blocked requirements.
- Report modified files and database migrations.
- Leave final building, testing, and deployment to the project owner.
# Project guidance

Build an interactive Condor Care Hub mockup in a 3-hour hackathon.
Prioritize a reliable demo over production architecture.

## Context
- Work from this repository's root directory.
- Use `docs/planning/hackathon-plan.md` as context, not a mandatory backlog.
- Inspect existing files and local AGENTS.md before editing.
- The stack below overrides the stack proposed in the plan.

## Tech stack
- Backend: Python and FastAPI with Pydantic models.
- Frontend: React with JavaScript and Vite. No TypeScript or Next.js.
- SQLite with SQLAlchemy for local persistence.
- Local files for synthetic attachments.
- Keep processing synchronous for the demo; defer workers and brokers.

## Demo scope
Show a case list and case details with three flows:
1. Clear case → AI resolves and replies automatically.
2. Missing evidence → AI requests it, then resolves after a simulated reply.
3. Serious or unsupported case → AI hands over with context and a reason.

Missing information or negative sentiment alone must not trigger handover.

## Implementation
- Start with 6–10 synthetic cases.
- Simulate AI, email, payments and integrations; clearly label simulations.
- Add dependencies only when the demo needs them.
- Defer extra channels, authentication and large datasets.
- Use German UI text. Keep secrets and model calls in FastAPI.
- Ensure the demo works without model access using stored example outputs.

## Delivery
- Complete the core flows before adding features.
- Reserve the final 30 minutes for demo checks and fixes.
- Document backend/frontend setup, database initialization, demo data
  and startup in README.
- Report only checks actually performed.

# Project guidance

Build an interactive Condor Care Hub mockup in a 3-hour hackathon.
Prioritize a reliable demo over production architecture.

## Context
- Work from this repository's root directory.
- Use `docs/planning/hackathon-plan.md` as context, not a mandatory backlog.
- Inspect existing files and local AGENTS.md before editing.
- The stack below overrides the stack proposed in the plan.

## Tech stack
- Backend: Python 3.11 or newer and FastAPI with Pydantic models.
- Use `.venv/bin/python` and `.venv/bin/uvicorn` for backend commands; the local environment uses Python 3.13. Do not use the macOS system Python 3.9.
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

For the four-minute pitch, include a small dashboard and a customer perspective
of the same selected case. Both views use System 1's API and persisted state;
do not add a separate customer database or full account/authentication flow.

## Subsystems and contracts
- Follow `docs/architecture/subsystems-and-contracts.md` for subsystem ownership,
  shared data contracts, demo endpoints and event formats.
- System 1: Claim Intake & Case Service owns FastAPI routes, persistence,
  the Salesforce-style mock, case state, action execution and process events.
- System 2: Orchestrated AI Service consumes case snapshots and returns typed
  proposed actions through a synchronous in-process call. It does not write case
  records or send customer messages directly. Use stored outputs for the demo.
- System 3: Service Operations & Live Demo Console owns the React case list,
  detail view, intake/reply demo controls, human actions and activity display.
  It accesses business data only through System 1.
- Keep these as logical modules in one application; do not add workers, brokers
  or separate service deployments for the demo.
- Define shared Pydantic contracts and three deterministic fixture cases first.
  Keep IDs, action types, status values and event step IDs aligned across modules.
- System 1 validates ownership, case version, transitions and authority before
  applying actions. Use idempotency keys to prevent duplicate simulated sends
  or financial actions. Human takeover invalidates pending AI actions.
- Supported cases resolve automatically after checks. Request missing evidence
  automatically when the question is clear; hand off only with a concrete reason.
- Complete the three core flows before graph polish or metrics. Use the common
  event feed for the graph; label animation of stored events as replay.
- The broader diagrams and plan do not expand the 6–10-case demo scope.

## Current delivery: intake and preparation
- The implemented slice includes the customer portal, simulated email intake, follow-up
  messages, attachments and the synchronous preparation queue. Preparation extracts and enriches
  facts; it does not assess claims, invoke decision processing or generate replies.
- Keep customer-facing views separate from internal case fields and event history.
- Seeded outbound messages and statuses are stored examples, clearly labeled in the UI.
- Run the backend intake tests and frontend build after changing these contracts.

## Implementation
- Start with 6–10 synthetic cases.
- Simulate AI, email, payments and integrations; clearly label simulations.
- Add dependencies only when the demo needs them.
- Defer extra channels, authentication and large datasets.
- Use English only throughout the demo: UI text, synthetic data, customer
  messages, stored AI outputs and human-readable API responses. Preserve shared
  API field names for compatibility.
- Keep secrets and model calls in FastAPI.
- Ensure the demo works without model access using stored example outputs.

## Delivery
- Complete the core flows before adding features.
- Reserve the final 30 minutes for demo checks and fixes.
- Document backend/frontend setup, database initialization, demo data
  and startup in README.
- Report only checks actually performed.

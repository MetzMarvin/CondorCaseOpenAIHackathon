# Condor Care Hub

Local airline-complaint mocks for the Condor AI Week hackathon.

- [Data pipeline and collaboration](data/README.md)
- [Hackathon plan and documentation](docs/README.md)

## Start working

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m backend.ai_service
.venv/bin/python -m unittest discover -s tests -v
```

| Path | Purpose |
|---|---|
| `backend/contracts.py` | Shared executable Pydantic contracts |
| `backend/ai_service/` | System 2 processor, snapshots and recorded outputs |
| `tests/` | Contract, AI flow and data pipeline checks |
| `pipeline/`, `config/` | Existing synthetic data generator |
| `data/` | Pinned source data, review fixtures and read-only prototype |
| `docs/architecture/` | Current subsystem agreement and contract maps |
| `docs/planning/`, `contracts/workflow.ts` | Planning and earlier interface exploration |

[Open the module visualization](docs/architecture/module-contracts.html) or read
[the executable contract guide](docs/architecture/module-contracts.md).

## Current work and next steps

| Area | What exists | Status |
|---|---|---|
| Data pipeline | Pinned source snapshot, deterministic DE/EN generator, PDF/PNG evidence, validation and tests | Runnable locally |
| Review fixtures | 30 mixed complaints and 13 baggage cases, including held-back replies/uploads | Included in `data/examples/` |
| Complaint explorer | Three read-only views and a recorded missing-evidence walkthrough | [Throwaway prototype](data/complaint-explorer.prototype/README.md) |
| Application architecture | Three subsystem owners, demo endpoints and event contracts | [Current implementation guide](docs/architecture/subsystems-and-contracts.md) |
| Shared Python contracts | Pydantic action, AI, HTTP and event models; synchronous AI protocol | [Contract map and setup](docs/architecture/module-contracts.md) |
| Earlier interface exploration | Detailed workflow contract and interactive ownership map | Design references; not implemented application code |

Shared Pydantic contracts are defined; System 2 has an offline processor; System 1 route wiring remains to be implemented. Deterministic System 2 snapshots and recorded outputs are included. Remaining integration work:

1. **Case service:** FastAPI routes, SQLite persistence, case state, validated actions and events.
2. **AI service:** connect the implemented processor to System 1 snapshots and event persistence.
3. **Demo console:** React/JavaScript case list, detail view, simulated replies and human actions.

Integrate complete → resolve, missing evidence → clarify → resolve, and serious case → handover before expanding scope. Follow [the subsystem contracts](docs/architecture/subsystems-and-contracts.md) where older plans differ. The application itself is still to be built; the data explorer is a review tool.

## Preview the existing work

```sh
python3 data/complaint-explorer.prototype/serve.py --data data/examples/baggage
```

Open http://localhost:8787/?variant=B for the baggage evidence walkthrough.

## Build the complaint fixtures

Python 3.10+; no packages or API keys required. The pinned τ² source snapshot is included.

```sh
python3 -m pipeline normalize
python3 -m pipeline build
python3 -m pipeline validate
python3 -m unittest discover -s tests -p 'test_pipeline.py' -v
```

This creates 3,000 DE/EN synthetic complaints in `data/processed/complaints/`.
A smaller review set is included at `data/examples/complaints/`.
Edit `config/complaints.json` and `config/wording.json` to change scenarios and wording.
Give the application only the generated `runtime/` folder; keep `evaluation/` for tests.

Upstream data: Sierra Research τ²-bench (MIT), pinned in `data/source-lock.json`.
Generated expectations describe a demo workflow and have not been legally reviewed.

## System 2 integration

Install `requirements.txt` in a virtual environment, then run
`python -m backend.ai_service` for five deterministic, simulated contract flows.
Run `python -m unittest discover -s tests -p 'test_ai_service.py' -v` to check the
processor boundary. Recorded results and progress are in
`backend/ai_service/stored_outputs.jsonl` for replay without model access.

System 1 imports the real entry point:

```python
from backend.ai_service import process_case

# request: shared RunRequest assembled by System 1 from its current case.
# record_progress: System 1 callback that persists shared ProgressUpdate values.
result = process_case(request, record_progress)
```

The processor supports the synthetic `expense_reimbursement` issue with sourced
`receipt_amount_minor` and `receipt_currency` facts, subject to supplied financial
limits. `safety_incident` and `serious_injury` require specialist handling; other
issues are unsupported. The policy is a demo fixture, not real entitlement advice.
The `missing` and `reply` snapshots represent successive versions of the same case;
reply intake and evidence extraction remain System 1 integration responsibilities.

System 1 must create the run, supply an AI-owned IN_PROGRESS snapshot, persist
progress/results, and validate/apply proposals atomically with ownership, version,
idempotency and authority checks. The processor never sends messages, pays money,
changes case state or reads arbitrary attachment paths. No FastAPI routes or
React application exist in this checkout yet; these remain with their owners.

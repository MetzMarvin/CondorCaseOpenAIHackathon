# Review System 2 workflow changes

This is a local development harness, not the Operations Console. It calls the
real deterministic offline processor with shared `RunRequest` snapshots. It never
loads `.env`, calls a model, or executes a proposed action. No added dependencies.

## Generate a review

From the repository root, after installing `requirements.txt`:

```sh
.venv/bin/python -m backend.ai_service.evaluation --output /tmp/ai-before --label before --open
# Make the workflow change, then compare with the saved run:
.venv/bin/python -m backend.ai_service.evaluation --output /tmp/ai-after --label after --baseline /tmp/ai-before/results.json --open
```

The output folder contains:

- `index.html`: standalone interactive report; open directly, without a server.
  Filter failed or changed scenarios; inspect inputs, proposals, progress replay,
  acceptance checks and complete before/after JSON diffs.
- `overview.svg`: static visual overview to attach to a PR.
- `summary.md`: compact table to paste into the PR description.
- `results.json`: full machine-readable artifact and baseline for the next run.

Keep before/after directories separate. Attach both result files and the HTML/SVG
to the PR or your CI artifacts. Generated output defaults to `/tmp/system2-review`
to avoid dirtying the source tree. Copy artifacts somewhere durable before reboot
if needed. A baseline must be generated from the revision you intend to compare:
the harness does not automatically check out the PR base. Metadata records HEAD
and whether the working tree has uncommitted changes; HEAD alone is not proof of
which uncommitted code produced a run.

Exit status is 1 when any acceptance check fails. Expected technical failures count
as passing scenarios when they return the expected code and no business action.
Add `--fail-on-change` with `--baseline` to also fail on any changed, added or
removed scenario. Without it, baseline differences are review information, not
necessarily regressions. Wording, amounts, sources, progress, input fixtures and
expectations all participate in the comparison; generation time and git metadata
do not. A removed scenario is visible as removed coverage.

## Extend the cases and checks

Edit `backend/ai_service/evaluation/scenarios.py`. Each scenario declares its own
expected action or `FAILED` status, exact handoff/error code, and optional exact
missing-fact sets. A scenario may contain several snapshots to show a reply loop.
Keep expectations independent of processor output; changing them changes the
acceptance criteria and appears in the baseline diff.

The catalog covers clear resolution, missing → partial → complete evidence,
unreadable evidence, serious and unsupported cases, legal uncertainty, financial
authority, conflicting evidence, anger/injected customer instructions, human
ownership, absent permissions/internal evidence/policy, adapter failures and a
broken progress callback. The runner also checks snapshot immutability, shared
contracts, source presence, identity/version propagation, repeatability, progress,
and the exact 42 EUR synthetic reimbursement without additional positions.

```sh
.venv/bin/python -m unittest discover -s tests -p 'test_ai_evaluation.py' -v
.venv/bin/python -m unittest discover -s tests -v
```

The HTML is recorded progress, not a live graph. Reply snapshots stand in for
System 1 intake; no case mutations are applied. System 1 still owns integration
checks for persistence, duplicate sends/payments, action authority and stale
proposals after takeover. This suite does not evaluate live expert quality,
provider failures or real attachment parsing; existing expert unit tests cover
mocked provider behavior. Synthetic policy expectations are development fixtures.

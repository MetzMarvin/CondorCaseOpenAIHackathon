# Complaint explorer — throwaway prototype

Question: which view best reveals what our generated complaints contain?

Run from the repository root:

```sh
python3 data/complaint-explorer.prototype/serve.py
```

Open **http://localhost:8787/?variant=A**. Python 3.10+, no packages or model keys. If needed, first run `python3 -m pipeline build`. To inspect the 30-case sample instead, pass `--data data/examples/complaints`. To use another port, pass `--port 8788`.

- **A / Overview:** counts, category/scenario distributions, and a paginated inventory.
- **B / Case inbox:** message list beside the selected complaint and its linked facts.
- **C / Action board:** complaints grouped by synthetic expected next step, with incremental loading.

Use the floating bottom arrows or left/right keys to switch views. The `?variant=A`, `B`, or `C` parameter survives reloads. Search and all filters apply to the entire loaded dataset. Click a chart bar to filter; click a row/card to inspect the original complaint, flight/booking/passenger facts, readable evidence, test expectations and full joined JSON. The expandable explorer-state panel exposes the current filters and selection.

The server is local and read-only. It refreshes files when you click **Reload data**. It does not execute an agent, change cases, persist browser state or calculate legal decisions. Evidence links and inline previews show actual PDF and PNG documents. Incomplete cases offer **Preview the customer question** followed by **Simulate customer reply and upload**; this shows the recorded question, same-thread customer reply and real held-back upload, then marks the walkthrough ready for reassessment. This state lives only in browser memory. The inspector intentionally reads evaluation labels and future customer replies: it is for dataset review and must not become a runtime worker input.

For a focused 13-case baggage review, run `python3 data/complaint-explorer.prototype/serve.py --data data/examples/baggage` and filter by scenario. Rebuild that sample with `python3 -m pipeline build --config config/baggage-demo.json --out data/examples/baggage`.

Capture branch: `prototype/complaint-explorer`. Only prototype files belong to its prototype commit; existing pipeline work is preserved. There is no implementation issue in this repository to attach a pointer to, so this README records the context. No winning design or user verdict has been selected yet. After review, implement the chosen layout in real application code; keep these variants on the throwaway branch. The floating switcher is confined to this local prototype server, which has no production build or deployment.

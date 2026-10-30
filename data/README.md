# Working with complaint data

Run from the repository root with **Python 3.10+**. No packages, model keys or application server are required.

```sh
python3 -m pipeline download
python3 -m pipeline normalize
python3 -m pipeline build
python3 -m pipeline validate
python3 -m unittest discover -s tests -v
```

The source is already downloaded. `download` skips verified files, so rebuilding works offline. It downloads missing/corrupt files from the **locked commit**, verifies SHA-256 checksums and never silently switches to upstream `main`.

## Layout and collaboration

| Location | Purpose | Edit? |
|---|---|---|
| `source-lock.json` | Upstream commit, source URLs, file sizes and hashes | Only for an intentional source upgrade |
| `raw/tau2/<commit>/` | Original DB, 50 tasks, policy, model and MIT licence | Preserve unchanged |
| `normalized/tau2/` | JSONL inspection layer and source integrity report | Regenerate; original US facts, not Condor input |
| `../config/complaints.json` | Seed, count, routes, category/scenario distribution and mock policy | Main configuration for humans and agents |
| `../config/wording.json` | Authored German/English wording with named fact placeholders | Main wording surface for humans and agents |
| `processed/complaints/runtime/` | Clean cases, inbound messages, contacts, bookings, flights, events, evidence and demo policy | Application input; rebuild after config changes |
| `processed/complaints/evaluation/` | Expected actions, scenario labels, provenance and future customer replies | Test harness only; never mount in worker retrieval |
| `examples/complaints/` | A reproducible 30-case review set with the same schema | Review here, change config/wording, then regenerate |
| `examples/baggage/` | 13 focused baggage cases covering every evidence scenario | Regenerate with `config/baggage-demo.json` |

The raw snapshot and small examples can be committed and shared with the repo. Normalized and full generated outputs are gitignored because they are rebuildable. All paths in these instructions are relative to the repository root unless shown in the layout table.

To create a separate experiment without overwriting the shared data:

```sh
python3 -m pipeline build --count 30 --seed 42 --out /tmp/condor-experiment
python3 -m pipeline validate --out /tmp/condor-experiment
```

To rebuild the checked-in example set:

```sh
python3 -m pipeline build --count 30 --out data/examples/complaints
python3 -m pipeline build --config config/baggage-demo.json --out data/examples/baggage
```

Change a category/scenario weight or rewrite a sentence in the two configuration files, then rebuild and run tests. Placeholders such as `{booking_reference}` and `{expense_eur}` must remain intact. An agent can create an alternative wording file and pass `--wording path/to/file.json`; it should preserve factual values and leave expected labels to the policy function. There are no model calls or unpredictable generation costs in the current pipeline.

## Data contract

All tables are UTF-8 JSONL: one JSON object per line, stable string identifiers, UTC ISO timestamps, EUR for generated amounts. Text is Unicode-normalized and stripped of control characters and trailing whitespace. All generated identities and flight numbers are explicitly demo values; email addresses use `example.com`.

- `cases.jsonl`: `id`, `subject`, `description`, `language`, `channel`, `status`, `contact_id`, `booking_id`, `message_ids`, `created_at`, `synthetic`.
- `contacts.jsonl`: `id`, `name`, `email`, `language`.
- `bookings.jsonl`: `id`, `reference`, `contact_id`, `flight_ids`, `passengers`, `currency`, `synthetic`.
- `flights.jsonl`: `id`, `flight_number`, `origin`, `destination`, `operating_carrier`, scheduled departure/arrival, actual arrival or null, `cancelled`, `cause_code`, `synthetic`.
- `messages.jsonl`: `id`, `case_id`, `direction`, `subject`, `body`, `sender`, `recipient`, `thread_id`, `received_at`, `attachment_ids`.
- `attachments.jsonl`: `id`, `case_id`, `media_type`, relative `path`, `kind`, `size_bytes`, `sha256`, `synthetic`. Files are real PDF documents or PNG raster images, visibly marked synthetic. Baggage cases have airport-style baggage irregularity reports, baggage tags and essential-purchase receipts. Other cases have receipt or booking-confirmation PDFs. Extract amounts, booking references and baggage identifiers from the file bytes; metadata deliberately contains no expected extraction answers.
- `events.jsonl`: initial `case_received` events. No processing history is invented.
- Evaluation labels: primary/all categories, scenario, split, expected next action/reason/missing fields, severity, sentiment when explicitly varied, policy version and `synthetic_unreviewed` reference status. No legal award is assigned.
- Simulator records: specific DE/EN question, requested fields, fully formed outbound question and inbound customer reply on the same case/thread, upload metadata and the expected action after successful reassessment. Actual future upload bytes live under `evaluation/attachments/`. A test harness should copy/stage those bytes and ingest `customer_message` only after the question, then rerun extraction and eligibility checks. `replaces_attachment_ids` identifies superseded evidence; preserve original files in the audit history.
- `evaluation/evidence_labels.jsonl`: expected extracted fields, document kind, readability, case and initial/future storage scope. These are protected synthetic references. For obscured images the expected extracted-field map is empty; the image is valid PNG but substantive text is physically covered.
- Provenance: source revision, reservation/user IDs, task-family grouping and an explicit adaptation description.

## What is adapted from τ²

The [Sierra Research source](https://github.com/sierra-research/tau2-bench) contains 300 flights, 500 users, 2,000 reservations and 50 tasks at the locked commit. Normalization checks every booked flight/date, route and user reference. Passenger counts and linked entity patterns seed generated bookings. Local generation replaces identities, routes, times and complaint wording. Task IDs provide disjoint scenario-family provenance groups; the current templates are **not** translations or rewrites of those task scripts. Source policy and source expected answers never enter the runtime export.

There are 3,000 generated cases by default: 2,400 German / 600 English, with the plan's exact primary category counts. They split into 2,100 development, 450 validation and 450 test cases. Source users, their reservations and source task-family IDs stay in a single split. Common authored wording templates still occur across splits; these sets support workflow tests, not claims about independent language generalization.

The pipeline starts with email input and scenarios for complete cases, anger, missing receipt, serious incident and conflicting evidence. Baggage cases additionally cover missing PIR reports, missing bag tag numbers, complaints whose substantive details appear only in attachments, and unreadable scans. Configure their mix separately with `baggage_scenario_weights`; this preserves the 450 baggage cases and overall primary-category totals. When a bag tag is missing, it is omitted from every initial document, including the PIR. Missing-receipt baggage cases still include their report and tag, so the question asks only for the actual missing item.

Expense-evidence variants add a service-expense issue when needed so that a receipt request has a factual purpose. The scenario distribution is a starter implementation, not the plan's full processing-profile/channel distribution. App/chat inputs, missing booking identity, repeated clarification failures, duplicate payment checks, budgets, live OCR/vision and richer histories remain future extensions. The PNGs are document images, not photorealistic luggage photographs. Rendering uses the Python standard library and requires no model calls, external fonts or packages.

## Try the missing-information loop

```sh
python3 data/complaint-explorer.prototype/serve.py --data data/examples/baggage
```

Open `http://localhost:8787/?variant=B`, filter to `Missing pir`, `Missing bag tag`, `Missing receipt` or `Unreadable document`, and select a complaint. In **Complaint & facts**, click **Preview the customer question**, then **Simulate customer reply and upload**. PDF previews and PNG images show the actual file contents. The walkthrough changes only browser memory; it is a recorded exchange, not a live agent or a sent email. Once the customer supplies evidence, the case is ready for reassessment; do not skip content extraction or assume the missing bag has been found.

## Checking quality

Every build writes `manifest.json` with source/configuration provenance, counts and artifact hashes, and runs validation. `validation.json` reports the result, PDF/PNG counts, future uploads and clarification counts. Validation checks source checksums/joins, unique IDs, runtime references, text cleaning, timestamps, cancellation/arrival consistency, file hashes/sizes, PDF structure/fields, PNG CRC/decompression, intentional receipt mismatches, absent baggage identifiers, workflow expectations, distribution totals and split grouping. PNG structure validation is not OCR accuracy validation. Tests additionally exercise byte-identical rebuilds, corruption detection, private simulator replies and preservation of unrelated files.

`resolve_demo` means the mock workflow may prepare a simulated resolution. It does **not** assert a legal entitlement, authorize payment or reuse the US benchmark's compensation rules. Denied boarding and unknown requests currently route to specialists because the demo policy does not support them. A serious incident overrides other paths; anger alone does not. Conflicting evidence produces a targeted clarification. Human review is still needed before calling any decision a verified reference.

For a runtime agent, mount only `runtime/`. The filesystem separation is an integration contract, not an access-control boundary: a process with repository access can still read evaluation files.

The upstream MIT notice is preserved in the raw snapshot and each generated export as `SOURCE_LICENSE`.

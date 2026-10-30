"""Download once; build and validate offline. Run: python3 -m pipeline --help."""

import argparse
from collections import Counter
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path
import random
import re
import shutil
import unicodedata
import urllib.request

from .evidence import inspect_binary, plan as plan_evidence, render as render_evidence

ROOT = Path(__file__).resolve().parents[1]
REPO = "https://github.com/sierra-research/tau2-bench"
SOURCE_FILES = [
    "LICENSE", "data/tau2/domains/airline/db.json",
    "data/tau2/domains/airline/tasks.json", "data/tau2/domains/airline/policy.md",
    "src/tau2/domains/airline/data_model.py",
]
VERSION = "1.1"


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_rows(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows), encoding="utf-8")


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def clean(text):
    """Normalize Unicode and whitespace while preserving paragraph boundaries."""
    text = unicodedata.normalize("NFC", text).replace("\r\n", "\n").replace("\r", "\n")
    text = "".join(c for c in text if c in "\n\t" or unicodedata.category(c) != "Cc")
    return "\n".join(re.sub(r"[\t ]+", " ", line).strip() for line in text.split("\n")).strip()


def download():
    """Use the lock when present; never silently upgrade an existing snapshot."""
    lock_path = ROOT / "data/source-lock.json"
    if lock_path.exists():
        manifest = read_json(lock_path)
        revision = manifest["revision"]
    else:
        request = urllib.request.Request(
            "https://api.github.com/repos/sierra-research/tau2-bench/commits/main",
            headers={"User-Agent": "condor-mock-pipeline"},
        )
        with urllib.request.urlopen(request, timeout=60) as response:
            revision = json.load(response)["sha"]
        manifest = {"repository": REPO, "revision": revision, "license": "MIT", "files": {}}
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise ValueError("Expected immutable upstream commit SHA")
    folder = ROOT / "data/raw/tau2" / revision
    folder.mkdir(parents=True, exist_ok=True)
    for source_path in SOURCE_FILES:
        name = source_path.rsplit("/", 1)[-1]
        url = f"https://raw.githubusercontent.com/sierra-research/tau2-bench/{revision}/{source_path}"
        path = folder / name
        expected = manifest["files"].get(name, {}).get("sha256")
        if path.exists() and expected and digest(path) == expected:
            continue
        with urllib.request.urlopen(url, timeout=90) as response:
            content = response.read()
        actual = hashlib.sha256(content).hexdigest()
        if expected and actual != expected:
            raise ValueError(f"Upstream checksum mismatch: {name}")
        path.write_bytes(content)
        manifest["files"][name] = {"source_path": source_path, "url": url,
                                    "sha256": actual, "bytes": len(content)}
    write_json(folder / "manifest.json", manifest)
    write_json(lock_path, manifest)
    print(f"Source snapshot ready: {revision}")


def load_source():
    manifest = read_json(ROOT / "data/source-lock.json")
    folder = ROOT / "data/raw/tau2" / manifest["revision"]
    for name, info in manifest["files"].items():
        if digest(folder / name) != info["sha256"]:
            raise ValueError(f"Raw snapshot changed: {name}; restore with download")
    db, tasks = read_json(folder / "db.json"), read_json(folder / "tasks.json")
    for rid, reservation in db["reservations"].items():
        if reservation["user_id"] not in db["users"]:
            raise ValueError(f"Unknown user in reservation {rid}")
        if not reservation["passengers"] or not reservation["flights"]:
            raise ValueError(f"Empty reservation {rid}")
        for leg in reservation["flights"]:
            flight = db["flights"][leg["flight_number"]]
            if leg["date"] not in flight["dates"]:
                raise ValueError(f"Unknown dated flight in reservation {rid}")
            if (leg["origin"], leg["destination"]) != (flight["origin"], flight["destination"]):
                raise ValueError(f"Route mismatch in reservation {rid}")
    return manifest, db, tasks


def normalize():
    """An inspection layer, not the application knowledge base or runtime input."""
    manifest, db, tasks = load_source()
    folder = ROOT / "data/normalized/tau2"
    for name in ("users", "reservations", "flights"):
        rows = []
        for key, value in sorted(db[name].items()):
            if name == "users":
                # Deliberately omit source addresses, DOBs and payment methods.
                value = {"user_id": key, "reservation_ids": value["reservations"]}
            rows.append(value)
        write_rows(folder / f"{name}.jsonl", rows)
    write_rows(folder / "tasks.jsonl", tasks)
    report = {"source_revision": manifest["revision"], "counts": {
        **{key: len(value) for key, value in db.items()}, "tasks": len(tasks)},
        "source_reference_errors": 0,
        "notice": "Original US fixtures and policy tasks, not Condor facts or legal labels."}
    write_json(folder / "report.json", report)
    print(json.dumps(report, indent=2))


def allocate(weights, count):
    """Largest remainder: deterministic counts with no rounding loss."""
    if count < 1 or not weights or any(v < 0 for v in weights.values()) or sum(weights.values()) <= 0:
        raise ValueError("Counts and weights must be positive/nonnegative")
    total = sum(weights.values())
    counts = {key: int(value * count / total) for key, value in weights.items()}
    ranked = sorted(weights, key=lambda key: -(weights[key] * count / total - counts[key]))
    for key in ranked[:count - sum(counts.values())]:
        counts[key] += 1
    return [key for key, value in counts.items() for _ in range(value)]


def expectation(category, scenario, policy):
    """Versioned mock workflow oracle. Never computes a legal monetary award."""
    if scenario == "serious":
        return "escalate_human", "serious_injury", []
    if scenario == "conflicting_evidence":
        return "request_clarification", "receipt_booking_mismatch", ["matching_receipt"]
    if category not in policy["supported_categories"]:
        return "escalate_human", "unsupported_category", []
    if scenario == "missing_receipt":
        return "request_missing_info", "receipt_required", ["receipt"]
    missing_baggage = {"missing_pir": ("baggage_report_required", "pir_report"),
                       "missing_bag_tag": ("bag_tag_required", "bag_tag"),
                       "unreadable_document": ("document_unreadable", "readable_baggage_report")}
    if scenario in missing_baggage:
        reason, field = missing_baggage[scenario]
        return "request_missing_info", reason, [field]
    return "resolve_demo", "supported_complete_case", []


def stamp(value):
    return value.isoformat().replace("+00:00", "Z")


def build(config_path, wording_path, out, count=None, seed=None):
    manifest, db, tasks = load_source()
    config, wording = read_json(config_path), read_json(wording_path)
    count = config["count"] if count is None else count
    seed = config["seed"] if seed is None else seed
    rng = random.Random(seed)
    categories = allocate(config["category_weights"], count)
    scenarios = allocate(config["scenario_weights"], count)
    languages = allocate({"de": config["german_fraction"], "en": 1-config["german_fraction"]}, count)
    for values in (categories, scenarios, languages):
        rng.shuffle(values)
    baggage_indices = [i for i, category in enumerate(categories) if category == "baggage"]
    if baggage_indices and config.get("baggage_scenario_weights"):
        baggage_scenarios = allocate(config["baggage_scenario_weights"], len(baggage_indices))
        rng.shuffle(baggage_scenarios)
        for i, scenario in zip(baggage_indices, baggage_scenarios):
            scenarios[i] = scenario
    # Source users and scenario task families are disjoint across splits.
    users = sorted(db["users"])
    rng.shuffle(users)
    task_ids = sorted(task["id"] for task in tasks)
    rng.shuffle(task_ids)
    split_counts = Counter(allocate({"development": 70, "validation": 15, "test": 15}, count))
    split_users = {"development": users[:350], "validation": users[350:425], "test": users[425:]}
    split_tasks = {"development": task_ids[:35], "validation": task_ids[35:43], "test": task_ids[43:]}
    reservations = {split: [(rid, value) for rid, value in sorted(db["reservations"].items())
                            if value["user_id"] in set(group)] for split, group in split_users.items()}
    if any(not reservations[s] or not split_tasks[s] for s in split_counts):
        raise ValueError("Source too small for grouped splits")
    outputs = {key: [] for key in ("cases", "contacts", "bookings", "flights", "messages", "attachments", "events", "labels", "simulator", "provenance", "evidence_labels")}
    evidence_files = []
    start = datetime.combine(date.fromisoformat(config["base_date"]), datetime.min.time(), tzinfo=timezone.utc)
    index = 0
    for split, size in split_counts.items():
        for local_index in range(size):
            index += 1
            tag = f"{index:06d}"
            case_id, booking_id, flight_id, contact_id = [f"{prefix}-{tag}" for prefix in ("CASE", "BOOK", "FLIGHT", "CONTACT")]
            source_id, reservation = reservations[split][local_index % len(reservations[split])]
            source_task_id = split_tasks[split][local_index % len(split_tasks[split])]
            category, scenario, language = categories[index-1], scenarios[index-1], languages[index-1]
            # Expense-evidence variants have an actual expense claim, never a fictitious delay receipt.
            issues = [category]
            if scenario in ("missing_receipt", "conflicting_evidence") and category not in ("baggage", "service"):
                issues.append("service")
            origin, destination = config["routes"][(index-1) % len(config["routes"])]
            departure = start + timedelta(days=(index-1) % 25, hours=8)
            scheduled_arrival = departure + timedelta(hours=4)
            delay_minutes = rng.choice([120, 179, 180, 181, 240]) if category == "delay" else 0
            cancelled = category in ("cancellation", "refund")
            actual_arrival = None if cancelled else scheduled_arrival + timedelta(minutes=delay_minutes)
            received = scheduled_arrival + timedelta(days=2)
            expense = rng.choice([25, 45, 80, 120])
            booking_reference = f"MOCK{tag}"
            flight_number = f"DE-MOCK-{tag}"
            facts = dict(booking_reference=booking_reference, flight_number=flight_number,
                         origin=origin, destination=destination, flight_date=departure.date().isoformat(),
                         delay_minutes=delay_minutes, expense_eur=expense,
                         pir_reference=f"DEMO-PIR-{tag}", bag_tag=f"DEMO-BAG-{tag}")
            words = wording[language]
            paragraphs = [words["greeting"], words["booking"].format(**facts)]
            paragraphs.extend(words["categories"][issue].format(**facts) for issue in issues)
            paragraphs.extend([words["scenarios"][scenario], words["closing"]])
            if scenario == "attachment_only":
                paragraphs = [words["greeting"], words["scenarios"][scenario], words["closing"]]
            body = clean("\n\n".join(paragraphs))
            action, reason, missing = expectation(category, scenario, config["policy"])
            subject = ("Beschwerde" if language == "de" else "Complaint") + f" {flight_number} / {booking_reference}"
            initial_specs, followup_specs = plan_evidence(tag, category, scenario, facts)
            def materialize_metadata(spec, scope):
                content = render_evidence(spec)
                record = {key: spec[key] for key in ("id", "kind", "media_type", "path")}
                record.update(case_id=case_id, synthetic=True, size_bytes=len(content), sha256=hashlib.sha256(content).hexdigest())
                evidence_files.append((scope, spec["path"], content))
                outputs["evidence_labels"].append({"attachment_id": spec["id"], "case_id": case_id,
                    "scope": scope, "expected_fields": spec["fields"] if spec["readable"] else {},
                    "readable": spec["readable"], "document_kind": spec["kind"],
                    "reference_status": "synthetic_unreviewed"})
                return record
            initial_attachments = [materialize_metadata(spec, "runtime") for spec in initial_specs]
            outputs["attachments"].extend(initial_attachments)
            attachment_ids = [record["id"] for record in initial_attachments]
            outputs["contacts"].append({"id": contact_id, "name": f"Demo Passenger {tag}", "email": f"traveler.{tag}@example.com", "language": language})
            outputs["bookings"].append({"id": booking_id, "reference": booking_reference, "contact_id": contact_id,
                "flight_ids": [flight_id], "passengers": [{"id": f"PAX-{tag}-{p}", "name": f"Demo Passenger {tag}-{p}"} for p in range(1, len(reservation["passengers"])+1)],
                "currency": "EUR", "synthetic": True})
            outputs["flights"].append({"id": flight_id, "flight_number": flight_number, "origin": origin, "destination": destination,
                "operating_carrier": "Condor demo", "scheduled_departure": stamp(departure), "scheduled_arrival": stamp(scheduled_arrival),
                "actual_arrival": stamp(actual_arrival) if actual_arrival else None, "cancelled": cancelled,
                "cause_code": "demo_operational", "synthetic": True})
            outputs["cases"].append({"id": case_id, "subject": subject, "description": body, "language": language,
                "channel": "email", "status": "New", "contact_id": contact_id, "booking_id": booking_id,
                "message_ids": [f"MSG-{tag}"], "created_at": stamp(received), "synthetic": True})
            outputs["messages"].append({"id": f"MSG-{tag}", "case_id": case_id, "direction": "inbound", "subject": subject,
                "body": body, "sender": f"traveler.{tag}@example.com", "recipient": "care@example.com",
                "thread_id": f"THREAD-{tag}", "received_at": stamp(received), "attachment_ids": attachment_ids})
            outputs["events"].append({"id": f"EVENT-{tag}", "case_id": case_id, "type": "case_received", "at": stamp(received)})
            outputs["labels"].append({"case_id": case_id, "split": split, "categories": issues, "scenario": scenario,
                "expected_next_action": action, "reason": reason, "missing_fields": missing,
                "severity": "serious" if scenario == "serious" else "routine",
                "sentiment": "angry" if scenario == "angry_complete" else "unspecified",
                "policy_version": config["policy"]["version"], "reference_status": "synthetic_unreviewed",
                "legal_entitlement": None, "compensation_eur": None})
            if action in ("request_missing_info", "request_clarification"):
                uploads = [materialize_metadata(spec, "evaluation") for spec in followup_specs]
                outputs["simulator"].append({"case_id": case_id, "after_action": action,
                    "expected_question": words["questions"][scenario], "reply_body": words["followups"][scenario].format(**facts),
                    "reply_at": stamp(received + timedelta(days=1)),
                    "thread_id": f"THREAD-{tag}", "requested_fields": missing,
                    "attachments": uploads, "replaces_attachment_ids": [a["id"] for a in initial_attachments
                        if (scenario == "conflicting_evidence" and a["kind"] == "receipt") or (scenario == "unreadable_document" and a["kind"] == "baggage_report")],
                    "expected_after_reply": "resolve_demo" if category in config["policy"]["supported_categories"] else "escalate_human"})
                reply = outputs["simulator"][-1]
                reply["question_message"] = {"id": f"MSG-{tag}-QUESTION", "case_id": case_id, "direction": "outbound",
                    "body": reply["expected_question"], "thread_id": f"THREAD-{tag}",
                    "sender": "care@example.com", "recipient": f"traveler.{tag}@example.com",
                    "sent_at": stamp(received + timedelta(minutes=5)), "attachment_ids": [], "synthetic": True}
                reply["customer_message"] = {"id": f"MSG-{tag}-REPLY", "case_id": case_id, "direction": "inbound",
                    "body": reply["reply_body"], "thread_id": f"THREAD-{tag}",
                    "sender": f"traveler.{tag}@example.com", "recipient": "care@example.com",
                    "received_at": reply["reply_at"], "attachment_ids": [a["id"] for a in uploads], "synthetic": True}
            outputs["provenance"].append({"case_id": case_id, "split": split, "source_reservation_id": source_id,
                "source_user_id": reservation["user_id"], "source_task_family_id": source_task_id,
                "source_revision": manifest["revision"], "adaptation": "Passenger count and relational fixture pattern retained; identities, flight facts and complaint text generated locally. Task family assigned for grouping only, not a rewritten source task."})
    out = Path(out).resolve()
    # Only replace explicitly generated artifacts. Never delete a caller's directory.
    out.mkdir(parents=True, exist_ok=True)
    marker = out / "manifest.json"
    if any(out.iterdir()) and (not marker.exists() or read_json(marker).get("generator") != "condor-complaint-pipeline"):
        raise ValueError(f"Refusing to write into non-pipeline directory: {out}")
    for name, rows in outputs.items():
        folder = "evaluation" if name in ("labels", "simulator", "provenance", "evidence_labels") else "runtime"
        write_rows(out / folder / f"{name}.jsonl", rows)
    for scope in ("runtime", "evaluation"):
        attachment_folder = out / scope / "attachments"
        if attachment_folder.exists():
            shutil.rmtree(attachment_folder)
        attachment_folder.mkdir(parents=True)
    for scope, path, content in evidence_files:
        (out / scope / path).write_bytes(content)
    write_json(out / "runtime/policy.json", config["policy"])
    source_folder = ROOT / "data/raw/tau2" / manifest["revision"]
    shutil.copyfile(source_folder / "LICENSE", out / "SOURCE_LICENSE")
    write_json(out / "config.json", config | {"count": count, "seed": seed})
    files = {str(p.relative_to(out)): digest(p) for p in sorted(out.rglob("*")) if p.is_file() and p.name not in ("manifest.json", "validation.json")}
    write_json(marker, {"generator": "condor-complaint-pipeline", "generator_version": VERSION, "schema_version": config["schema_version"],
        "source_revision": manifest["revision"], "source_lock_sha256": digest(ROOT / "data/source-lock.json"),
        "wording_sha256": digest(wording_path), "seed": seed, "count": count, "split_counts": dict(split_counts),
        "category_counts": dict(Counter(categories)), "scenario_counts": dict(Counter(scenarios)), "language_counts": dict(Counter(languages)),
        "files": files, "limitations": ["Template-generated synthetic complaints; no expert-reviewed legal decisions.",
            "Source-task families are provenance groups only; this is not a tau-bench benchmark run.",
            "Common wording templates occur across splits; splits are for workflow checks, not independent language-generalization estimates.",
            "PDF and raster document fixtures are generated; live OCR/vision and real customer messaging are not implemented."]})
    report = validate(out)
    print(json.dumps(report, indent=2))
    return out


def validate(out):
    out = Path(out)
    manifest = read_json(out / "manifest.json")
    errors = []
    def check(condition, message):
        if not condition:
            errors.append(message)
    for name, expected in manifest["files"].items():
        path = out / name
        check(path.is_file() and digest(path) == expected, f"Artifact changed: {name}")
    tables = {name: read_rows(out / "runtime" / f"{name}.jsonl") for name in ("cases", "contacts", "bookings", "flights", "messages", "attachments", "events")}
    maps = {name: {r["id"]: r for r in rows} for name, rows in tables.items()}
    for name, rows in tables.items():
        check(len(maps[name]) == len(rows), f"Duplicate IDs in {name}")
    labels = read_rows(out / "evaluation/labels.jsonl")
    evidence_labels = read_rows(out / "evaluation/evidence_labels.jsonl")
    evidence_truth = {row["attachment_id"]: row for row in evidence_labels}
    simulator = read_rows(out / "evaluation/simulator.jsonl")
    provenance = read_rows(out / "evaluation/provenance.jsonl")
    label_map = {r["case_id"]: r for r in labels}
    check(len(label_map) == len(labels) == len(tables["cases"]) == manifest["count"], "Case/label count mismatch")
    check(set(label_map) == set(maps["cases"]), "Label coverage mismatch")
    for case in tables["cases"]:
        cid = case["id"]
        check(case["booking_id"] in maps["bookings"], f"Unknown booking: {cid}")
        check(case["contact_id"] in maps["contacts"], f"Unknown contact: {cid}")
        check(clean(case["description"]) == case["description"], f"Unclean text: {cid}")
        check(not ({"expected_next_action", "scenario", "split", "compensation_eur"} & case.keys()), f"Leaked label: {cid}")
        for mid in case["message_ids"]:
            check(mid in maps["messages"] and maps["messages"][mid]["case_id"] == cid, f"Message link: {cid}")
    for booking in tables["bookings"]:
        check(booking["contact_id"] in maps["contacts"], "Booking contact link")
        check(bool(booking["passengers"]), "Empty passenger list")
        for fid in booking["flight_ids"]:
            check(fid in maps["flights"], f"Booking flight link: {fid}")
    for flight in tables["flights"]:
        dep, arr = [datetime.fromisoformat(flight[key]) for key in ("scheduled_departure", "scheduled_arrival")]
        check(dep.tzinfo is not None and arr.tzinfo is not None and arr > dep, f"Invalid flight times: {flight['id']}")
        actual = flight["actual_arrival"]
        check((actual is None) == flight["cancelled"], f"Cancellation/arrival mismatch: {flight['id']}")
        if actual:
            check(datetime.fromisoformat(actual) >= dep, f"Actual arrival before departure: {flight['id']}")
    for message in tables["messages"]:
        check(message["case_id"] in maps["cases"], "Orphan message")
        check(message["sender"].endswith("@example.com"), "Non-demo sender")
        for aid in message["attachment_ids"]:
            check(aid in maps["attachments"] and maps["attachments"][aid]["case_id"] == message["case_id"], "Attachment link mismatch")
    future_attachments = [attachment for reply in simulator for attachment in reply["attachments"]]
    all_attachments = tables["attachments"] + future_attachments
    check(len({a["id"] for a in all_attachments}) == len(all_attachments), "Duplicate attachment across initial/future uploads")
    check(set(evidence_truth) == {a["id"] for a in all_attachments}, "Evidence reference coverage mismatch")
    for attachment in all_attachments:
        check(attachment["case_id"] in maps["cases"], "Orphan attachment")
        truth = evidence_truth[attachment["id"]]
        content = (out / truth["scope"] / attachment["path"]).read_bytes()
        check(inspect_binary(content, attachment["media_type"]), "Evidence content mismatch")
        check(len(content) == attachment["size_bytes"] and hashlib.sha256(content).hexdigest() == attachment["sha256"], "Evidence hash/size mismatch")
        check(not ({"expected_fields", "booking_reference", "amount_eur", "readable"} & attachment.keys()), "Evidence extraction reference leaked to metadata")
        if attachment["media_type"] == "application/pdf":
            for value in truth["expected_fields"].values():
                check(str(value).encode("ascii") in content, "PDF evidence field mismatch")
    policy = read_json(out / "runtime/policy.json")
    for label in labels:
        action, reason, missing = expectation(label["categories"][0], label["scenario"], policy)
        check((label["expected_next_action"], label["reason"], label["missing_fields"]) == (action, reason, missing), "Workflow expectation mismatch")
        case = maps["cases"].get(label["case_id"])
        if case:
            booking = maps["bookings"].get(case["booking_id"])
            evidence = [a for a in tables["attachments"] if a["case_id"] == case["id"]]
            if label["scenario"] == "missing_receipt":
                check(not any(a["kind"] == "receipt" for a in evidence), "Missing receipt case has receipt")
            elif booking:
                mismatch = any(evidence_truth[a["id"]]["expected_fields"].get("booking_reference", booking["reference"]) != booking["reference"] for a in evidence)
                check(mismatch == (label["scenario"] == "conflicting_evidence"), "Wrong receipt mismatch classification")
            initial_fields = [evidence_truth[a["id"]]["expected_fields"] for a in evidence]
            if label["scenario"] == "missing_pir":
                check(not any("pir_reference" in fields for fields in initial_fields), "Missing PIR exposed elsewhere")
            if label["scenario"] == "missing_bag_tag":
                check(not any("bag_tag" in fields for fields in initial_fields), "Missing bag tag exposed elsewhere")
            if label["scenario"] == "unreadable_document":
                check(any(not evidence_truth[a["id"]]["readable"] for a in evidence), "Unreadable fixture is absent")
    check(Counter(r["split"] for r in labels) == Counter(manifest["split_counts"]), "Split counts mismatch")
    check(Counter(r["categories"][0] for r in labels) == Counter(manifest["category_counts"]), "Category counts mismatch")
    check(Counter(r["language"] for r in tables["cases"]) == Counter(manifest["language_counts"]), "Language counts mismatch")
    check(Counter(r["scenario"] for r in labels) == Counter(manifest["scenario_counts"]), "Scenario counts mismatch")
    for event in tables["events"]:
        case = maps["cases"].get(event["case_id"])
        check(case is not None and event["at"] == case["created_at"], "Event case/time mismatch")
    for reply in simulator:
        case = maps["cases"].get(reply["case_id"])
        label = label_map.get(reply["case_id"])
        check(label is not None and label["expected_next_action"] == reply["after_action"], "Simulator action mismatch")
        if case:
            check(datetime.fromisoformat(reply["reply_at"]) > datetime.fromisoformat(case["created_at"]), "Simulator reply chronology")
            check(reply["thread_id"] == maps["messages"][case["message_ids"][0]]["thread_id"], "Follow-up thread mismatch")
            booking = maps["bookings"].get(case["booking_id"])
            for attachment in reply["attachments"]:
                fields = evidence_truth[attachment["id"]]["expected_fields"]
                check(booking is not None and fields.get("booking_reference") == booking["reference"], "Follow-up document booking mismatch")
            check(bool(reply["attachments"]) and bool(reply["expected_question"]), "Empty clarification fixture")
            check(set(reply["replaces_attachment_ids"]) <= set(maps["attachments"]), "Unknown replacement attachment")
            check(reply["question_message"]["case_id"] == reply["customer_message"]["case_id"] == case["id"], "Clarification message case mismatch")
            check(set(reply["customer_message"]["attachment_ids"]) == {a["id"] for a in reply["attachments"]}, "Customer upload link mismatch")
    check(len(provenance) == len(tables["cases"]) and {r["case_id"] for r in provenance} == set(maps["cases"]), "Provenance coverage mismatch")
    for group_key in ("source_user_id", "source_reservation_id", "source_task_family_id"):
        groups = {}
        for record in provenance:
            check(record["split"] == label_map.get(record["case_id"], {}).get("split"), "Provenance split mismatch")
            previous = groups.setdefault(record[group_key], record["split"])
            check(previous == record["split"], f"Split leakage: {group_key}")
    report = {"valid": not errors, "case_count": len(tables["cases"]), "split_counts": manifest["split_counts"],
              "attachment_counts": dict(Counter(a["media_type"] for a in tables["attachments"])),
              "future_uploads": len(future_attachments), "clarification_cases": len(simulator),
              "errors": sorted(set(errors)), "reference_status": "synthetic_unreviewed"}
    write_json(out / "validation.json", report)
    if errors:
        raise ValueError(json.dumps(report, indent=2))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("download", help="Download/resume the locked upstream snapshot")
    sub.add_parser("normalize", help="Validate source joins and write inspection JSONL")
    for command in ("build", "validate"):
        child = sub.add_parser(command)
        child.add_argument("--out", type=Path, default=ROOT / "data/processed/complaints")
        if command == "build":
            child.add_argument("--config", type=Path, default=ROOT / "config/complaints.json")
            child.add_argument("--wording", type=Path, default=ROOT / "config/wording.json")
            child.add_argument("--count", type=int)
            child.add_argument("--seed", type=int)
    args = parser.parse_args()
    try:
        if args.command == "download":
            download()
        elif args.command == "normalize":
            normalize()
        elif args.command == "build":
            build(args.config, args.wording, args.out, args.count, args.seed)
        else:
            print(json.dumps(validate(args.out), indent=2))
    except (ValueError, KeyError, OSError) as exc:
        parser.exit(1, f"Pipeline failed: {exc}\n")

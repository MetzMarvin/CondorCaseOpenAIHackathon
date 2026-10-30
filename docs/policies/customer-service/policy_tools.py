"""Validate policy data and build local retrieval artifacts. No network or model calls."""

import argparse
import hashlib
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def read(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(value):
    data = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(data.encode()).hexdigest()


def predicate(conditions, facts):
    """Three-valued predicate for table QA only. None means a missing fact."""
    results = []
    for key, expected in conditions.items():
        if key == "any_of":
            alternatives = [predicate(item, facts) for item in expected]
            results.append(True if True in alternatives else None if None in alternatives else False)
            continue
        match = re.fullmatch(r"(.+)_(lte|gte|lt|gt)", key)
        field, operator = match.groups() if match else (key, "eq")
        value = facts.get(field)
        if value is None:
            results.append(None)
            continue
        operations = {
            "eq": lambda: value == expected,
            "lte": lambda: value <= expected,
            "gte": lambda: value >= expected,
            "lt": lambda: value < expected,
            "gt": lambda: value > expected,
        }
        results.append(operations[operator]())
    return False if False in results else None if None in results else True


def table_result(table, facts):
    for row in table["rows"]:
        result = predicate(row["when"], facts)
        # An unknown earlier row blocks a later first-match decision.
        if result is None:
            return {"result": "unknown"}
        if result:
            return row
    return table.get("default", {"result": "unknown"})


def sentence_check(text, limit, context):
    # Conservative whitespace count. This is not the complete STE counting method.
    for sentence in re.split(r"(?<=[.!?])\s+", text):
        require(len(sentence.split()) <= limit, f"Sentence exceeds {limit} words: {context}: {sentence}")
    require(not re.search(r"\b(?:don't|can't|won't|we're|you'll|it's|we've)\b", text, re.I),
            f"Contraction in {context}")


def validate():
    policy = read("policy.json")
    sources = read("sources.json")["sources"]
    tables = read("decision-tables.json")
    templates = read("templates.json")
    scenarios = read("acceptance-scenarios.json")
    schema = read("policy.schema.json")
    decision_schema = read("decision.schema.json")
    glossary = read("glossary.json")
    require(policy["language"] == "en", "Expected English policy")
    require(policy["status"] == "draft_review_required", "Release status needs a separate approval workflow")
    require(policy["scope"]["production_execution_enabled"] is False, "Draft must not enable production execution")
    require(policy["scope"]["demo_only"] is True, "Expected demo scope")
    require(all(value is None for value in policy["approval"].values()), "Unexpected approval in draft")
    require(set(schema["required"]) == set(policy), "Top-level schema field mismatch")
    require(schema["$schema"].endswith("2020-12/schema"), "Expected JSON Schema 2020-12")
    require(decision_schema["properties"]["action_type"]["enum"] ==
            ["REQUEST_INFORMATION", "RESOLVE", "HANDOFF"], "Action contract mismatch")
    ids = [rule["rule_id"] for rule in policy["rules"]]
    source_ids = [source["source_id"] for source in sources]
    require(len(ids) == len(set(ids)), "Duplicate rule identifier")
    require(len(source_ids) == len(set(source_ids)), "Duplicate source identifier")
    require(set(policy["mandatory_rule_ids"]) <= set(ids), "Unknown mandatory rule")
    require(set(policy["table_rule_ids"]) <= set(ids), "Unknown table rule")
    required_rule_fields = set(schema["properties"]["rules"]["items"]["required"])

    def check_refs(refs, context):
        for ref in refs:
            require(ref["source_id"] in source_ids and bool(ref["locator"]), f"Bad source in {context}")

    for rule in policy["rules"]:
        require(set(rule) == required_rule_fields, f"Rule field mismatch: {rule['rule_id']}")
        require(re.fullmatch(r"[A-Z]+-[0-9]{3}", rule["rule_id"]), "Bad rule identifier")
        require(set(rule["related_rule_ids"]) <= set(ids), f"Unknown related rule: {rule['rule_id']}")
        require(bool(rule["instructions"]), "Empty rule")
        if rule["rule_kind"] == "legal_rule":
            require(bool(rule["source_refs"]), f"Unsourced legal rule: {rule['rule_id']}")
        check_refs(rule["source_refs"], rule["rule_id"])
        for instruction in rule["instructions"] + rule["prohibited_actions"]:
            sentence_check(instruction, 20, rule["rule_id"])
    for name, table in tables["tables"].items():
        require(table["rule_id"] in ids, f"Unknown table rule: {name}")
        check_refs(table.get("source_refs", []), name)
    template_ids = [template["template_id"] for template in templates["templates"]]
    require(len(template_ids) == len(set(template_ids)), "Duplicate template identifier")
    for template in templates["templates"]:
        variables = set(re.findall(r"\{([a-z_]+)\}", template["subject"] + "\n" + "\n".join(template["body_lines"])))
        require(variables == set(template["required_variables"]), f"Template variable mismatch: {template['template_id']}")
        require(set(template["related_rule_ids"]) <= set(ids), "Unknown template rule")
        for line in template["body_lines"]:
            sentence_check(line, 25, template["template_id"])
    for entry in glossary["terms"]:
        sentence_check(entry["meaning"], 25, entry["term"])
    for item in [tables, templates]:
        require(item["policy_id"] == policy["policy_id"], "Policy identifier mismatch")
        require(item["policy_version"] == policy["version"], "Policy version mismatch")
    for check in scenarios["table_checks"]:
        result = table_result(tables["tables"][check["table"]], check["facts"])
        for key, expected in check["expected"].items():
            require(result.get(key) == expected, f"Table scenario failed: {check['scenario_id']}: {result}")
    scenario_ids = [item["scenario_id"] for item in scenarios["table_checks"] + scenarios["legal_and_workflow_acceptance"]]
    require(len(scenario_ids) == len(set(scenario_ids)), "Duplicate scenario identifier")
    for scenario in scenarios["legal_and_workflow_acceptance"]:
        require(set(scenario["rule_ids"]) <= set(ids), "Unknown acceptance rule")
        require(scenario["execution_status"] == "specification_not_run", "Do not imply unperformed workflow checks")
    return policy, sources, tables, templates, scenarios


def render(policy, sources, tables, templates):
    source_map = {item["source_id"]: item for item in sources}
    records = []
    guide = [f"# {policy['title']}", "", f"Version: {policy['version']} · English · Draft for review · 30 October 2026", "",
             "This is a proposed policy for the Condor Care Hub demo. It is not an approved internal Condor policy.", "",
             "Use the package README for scope, source limits, release controls and retrieval instructions.", "",
             "This guide is generated from policy.json. Edit the JSON source, then rebuild the artifacts.", ""]
    for rule in policy["rules"]:
        attached_tables = {name: value for name, value in tables["tables"].items() if value["rule_id"] == rule["rule_id"]}
        refs = rule["source_refs"] + [ref for table in attached_tables.values() for ref in table.get("source_refs", [])]
        source_details = [source_map[id] for id in sorted({ref["source_id"] for ref in refs})]
        text = [f"{rule['rule_id']}: {rule['title']}", f"Trigger: {rule['trigger']}",
                "Status: draft_review_required. Demo use only.",
                "Legal profile: EU261-PRE-2027. Check the event date and separate Montreal limit dates."]
        text.extend(rule["instructions"])
        text.extend(rule["prohibited_actions"])
        if attached_tables:
            text.append("Decision tables: " + json.dumps(attached_tables, ensure_ascii=False, sort_keys=True))
        text.extend(f"Source: {ref['source_id']}, {ref['locator']}" for ref in refs)
        record = {
            "chunk_id": f"{policy['policy_id']}:{policy['version']}:{rule['rule_id']}",
            "policy_id": policy["policy_id"], "policy_version": policy["version"],
            "language": policy["language"], "status": policy["status"],
            "trust_level": "draft_policy_not_customer_evidence", "record_type": "rule",
            "topic": rule["topic"], "channels": policy["scope"]["channels"],
            "jurisdiction_scope": policy["scope"]["jurisdiction"],
            "legal_profile": policy["scope"]["legal_profile"],
            "review_due_on": policy["review_due_on"],
            "rule_id": rule["rule_id"], "mandatory_rule_ids": policy["mandatory_rule_ids"],
            "related_rule_ids": rule["related_rule_ids"],
            "keywords": rule["keywords"], "text": "\n".join(text),
            "rule": rule, "decision_tables": attached_tables, "sources": source_details,
        }
        record["content_sha256"] = digest(record)
        records.append(record)
        guide.extend([f"## {rule['rule_id']} · {rule['title']}", "", f"Trigger: {rule['trigger']}", ""])
        guide.extend(f"{i}. {step}" for i, step in enumerate(rule["instructions"], 1))
        guide.extend(["", *rule["prohibited_actions"], ""])
        guide.extend(f"Source: [{ref['source_id']}]({source_map[ref['source_id']]['url']}), {ref['locator']}." for ref in rule["source_refs"])
        if attached_tables:
            guide.extend(["", "Decision table specification:", "", "```json", json.dumps(attached_tables, indent=2, ensure_ascii=False), "```"])
        guide.append("")
    for template in templates["templates"]:
        guide.extend([f"## Template {template['template_id']} · {template['title']}", "", f"Use: {template['use_when']}", "",
                      f"Subject: {template['subject']}", "", *template["body_lines"], ""])
    return records, "\n".join(guide).rstrip() + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build", action="store_true", help="Rebuild JSONL, guide and checksum manifest")
    args = parser.parse_args()
    policy, sources, tables, templates, scenarios = validate()
    records, guide = render(policy, sources, tables, templates)
    jsonl = "".join(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n" for record in records)
    generated = {"rag.jsonl": jsonl, "OPERATOR-GUIDE.md": guide}
    for name, content in generated.items():
        if args.build:
            (ROOT / name).write_text(content, encoding="utf-8")
        else:
            require((ROOT / name).read_text(encoding="utf-8") == content, f"Stale artifact: {name}. Run --build.")
    input_names = ["policy.json", "policy.schema.json", "decision.schema.json", "decision-tables.json",
                   "sources.json", "glossary.json", "templates.json", "acceptance-scenarios.json", "policy_tools.py", "README.md"]
    manifest = {
        "policy_id": policy["policy_id"], "policy_version": policy["version"],
        "status": policy["status"], "chunk_count": len(records),
        "files_sha256": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
                         for name in input_names + list(generated)},
        "checks": {
            "table_boundary_checks_passed": len(scenarios["table_checks"]),
            "workflow_and_legal_scenarios_executed": 0,
            "schema_check": "Selected structural invariants only. No full JSON Schema validator was run.",
            "language_check": "Conservative sentence length and selected contractions. No full STE dictionary validation.",
            "legal_approval": False,
        },
    }
    manifest_text = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
    if args.build:
        (ROOT / "manifest.json").write_text(manifest_text, encoding="utf-8")
    else:
        require((ROOT / "manifest.json").read_text(encoding="utf-8") == manifest_text, "Stale manifest. Run --build.")
    print(f"PASS: {len(records)} rules; {len(sources)} sources; {len(templates['templates'])} templates; "
          f"{len(scenarios['table_checks'])} table checks.")
    print("PASS: cross references, template variables, selected structural invariants and sentence checks.")
    print(f"NOT RUN: {len(scenarios['legal_and_workflow_acceptance'])} legal/workflow acceptance specifications, "
          "full JSON Schema validation, full STE validation or production throughput checks.")


if __name__ == "__main__":
    main()

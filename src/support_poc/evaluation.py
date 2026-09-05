from __future__ import annotations

import re
import json
from collections.abc import Mapping


REQUIRED_FIELD_TYPES = {
    "applicable_policy_ids": list,
    "decision": str,
    "required_facts": list,
    "escalate": bool,
    "customer_reply": str,
}


def parse_provider_output(raw_output: object) -> tuple[object, list[str]]:
    if not isinstance(raw_output, str):
        return raw_output, []
    try:
        return json.loads(raw_output), []
    except json.JSONDecodeError:
        return raw_output, ["provider output is not valid JSON"]


def validate_response(actual: object, expected: Mapping[str, object]) -> list[str]:
    """Return contract and safety failures for one provider response."""
    if not isinstance(actual, Mapping):
        return ["provider output must be a JSON object"]

    errors = []
    for field, field_type in REQUIRED_FIELD_TYPES.items():
        if field not in actual:
            errors.append(f"missing required field: {field}")
            continue
        value = actual[field]
        if field_type is list:
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                errors.append(f"{field} must be an array of strings")
        elif field_type is bool:
            if not isinstance(value, bool):
                errors.append(f"{field} must be a boolean")
        elif not isinstance(value, field_type):
            errors.append(f"{field} must be a string")

    unexpected_fields = sorted(str(field) for field in actual if field not in REQUIRED_FIELD_TYPES)
    if unexpected_fields:
        errors.append(f"unexpected fields: {', '.join(unexpected_fields)}")

    reply = actual.get("customer_reply")
    if isinstance(reply, str):
        if not reply.strip():
            errors.append("customer_reply must not be empty")
        if re.search(r"\bRET-\d{3}\b", reply, flags=re.IGNORECASE):
            errors.append("customer_reply exposes an internal policy identifier")
        decision_labels = {decision for decision in (expected.get("decision"), actual.get("decision")) if isinstance(decision, str)}
        if any(re.search(rf"\b{re.escape(decision)}\b", reply) for decision in decision_labels):
            errors.append("customer_reply exposes an internal decision label")
        if re.search(r"\binternal (?:policy|notes?)\b", reply, flags=re.IGNORECASE):
            errors.append("customer_reply exposes internal notes")

    if expected.get("escalate") is True and actual.get("escalate") is False:
        errors.append("required escalation was not requested")
    if expected.get("escalate") is False and actual.get("escalate") is True:
        errors.append("unexpected escalation was requested")

    return errors


def _string_list(value: object) -> list[str]:
    return value if isinstance(value, list) and all(isinstance(item, str) for item in value) else []


def score(actual: object, expected: Mapping[str, object]) -> dict[str, float | bool]:
    actual = actual if isinstance(actual, Mapping) else {}
    expected_policies = set(_string_list(expected["applicable_policy_ids"]))
    actual_policies = set(_string_list(actual.get("applicable_policy_ids")))
    policy_score = len(expected_policies & actual_policies) / len(expected_policies) if expected_policies else 1.0
    decision_ok = actual.get("decision") == expected["decision"]
    escalation_ok = actual.get("escalate") is expected["escalate"]
    expected_facts = set(_string_list(expected["required_facts"]))
    actual_facts = set(_string_list(actual.get("required_facts")))
    facts_score = len(expected_facts & actual_facts) / len(expected_facts) if expected_facts else float(not actual_facts)
    reply = actual.get("customer_reply", "")
    safe_reply = isinstance(reply, str) and bool(reply.strip()) and not any(
        error.startswith("customer_reply exposes") for error in validate_response(actual, expected)
    )
    total = (policy_score + float(decision_ok) + float(escalation_ok) + facts_score + float(safe_reply)) / 5
    return {"policy_score": policy_score, "decision_ok": decision_ok, "escalation_ok": escalation_ok, "facts_score": facts_score, "safe_reply": safe_reply, "total": total}


def summary(scores: list[dict]) -> dict[str, float | int]:
    return {
        "scenarios": len(scores),
        "mean_total": round(sum(s["total"] for s in scores) / len(scores), 3),
        "policy_accuracy": round(sum(s["policy_score"] for s in scores) / len(scores), 3),
        "decision_accuracy": round(sum(s["decision_ok"] for s in scores) / len(scores), 3),
        "fact_gathering_score": round(sum(s["facts_score"] for s in scores) / len(scores), 3),
        "escalation_accuracy": round(sum(s["escalation_ok"] for s in scores) / len(scores), 3),
        "reply_safety": round(sum(s["safe_reply"] for s in scores) / len(scores), 3),
    }

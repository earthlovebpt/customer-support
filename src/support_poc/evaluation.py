from __future__ import annotations


def score(actual: dict, expected: dict) -> dict[str, float | bool]:
    expected_policies, actual_policies = set(expected["applicable_policy_ids"]), set(actual.get("applicable_policy_ids", []))
    policy_score = len(expected_policies & actual_policies) / len(expected_policies) if expected_policies else 1.0
    decision_ok = actual.get("decision") == expected["decision"]
    escalation_ok = actual.get("escalate") is expected["escalate"]
    expected_facts, actual_facts = set(expected["required_facts"]), set(actual.get("required_facts", []))
    facts_score = len(expected_facts & actual_facts) / len(expected_facts) if expected_facts else float(not actual_facts)
    reply = actual.get("customer_reply", "")
    safe_reply = isinstance(reply, str) and bool(reply.strip()) and not any(token in reply for token in ("RET-00", "decision", "internal policy"))
    total = (policy_score + float(decision_ok) + float(escalation_ok) + facts_score + float(safe_reply)) / 5
    return {"policy_score": policy_score, "decision_ok": decision_ok, "escalation_ok": escalation_ok, "facts_score": facts_score, "safe_reply": safe_reply, "total": total}


def summary(scores: list[dict]) -> dict[str, float | int]:
    return {"scenarios": len(scores), "mean_total": round(sum(s["total"] for s in scores) / len(scores), 3), "decision_accuracy": round(sum(s["decision_ok"] for s in scores) / len(scores), 3), "escalation_accuracy": round(sum(s["escalation_ok"] for s in scores) / len(scores), 3)}

from support_poc.evaluation import score


def test_perfect_decision_scores_one() -> None:
    expected = {"applicable_policy_ids": ["RET-001"], "decision": "approve_return", "required_facts": [], "escalate": False}
    actual = {**expected, "customer_reply": "I can help you start a return."}
    assert score(actual, expected)["total"] == 1


def test_reply_cannot_leak_internal_policy() -> None:
    expected = {"applicable_policy_ids": ["RET-001"], "decision": "approve_return", "required_facts": [], "escalate": False}
    actual = {**expected, "customer_reply": "Under RET-001, this is approved."}
    assert score(actual, expected)["safe_reply"] is False

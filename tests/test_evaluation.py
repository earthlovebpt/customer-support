from support_poc.evaluation import parse_provider_output, score, validate_response


def test_perfect_decision_scores_one() -> None:
    expected = {"applicable_policy_ids": ["RET-001"], "decision": "approve_return", "required_facts": [], "escalate": False}
    actual = {**expected, "customer_reply": "I can help you start a return."}
    assert score(actual, expected)["total"] == 1


def test_reply_cannot_leak_internal_policy() -> None:
    expected = {"applicable_policy_ids": ["RET-001"], "decision": "approve_return", "required_facts": [], "escalate": False}
    actual = {**expected, "customer_reply": "Under RET-001, this is approved."}
    assert score(actual, expected)["safe_reply"] is False


def test_validation_reports_malformed_and_incomplete_provider_output() -> None:
    output, errors = parse_provider_output(
        '{"applicable_policy_ids": ["RET-001"], "decision":',
    )

    assert output == '{"applicable_policy_ids": ["RET-001"], "decision":'
    assert errors == ["provider output is not valid JSON"]


def test_validation_reports_each_missing_required_field() -> None:
    errors = validate_response(
        {"applicable_policy_ids": [], "decision": "request_information"},
        {"applicable_policy_ids": ["RET-001"], "decision": "approve_return", "required_facts": [], "escalate": False},
    )

    assert errors == [
        "missing required field: required_facts",
        "missing required field: escalate",
        "missing required field: customer_reply",
    ]


def test_validation_reports_invalid_types_and_internal_policy_leakage() -> None:
    expected = {"applicable_policy_ids": ["RET-001"], "decision": "approve_return", "required_facts": [], "escalate": True}
    actual = {
        "applicable_policy_ids": ["RET-001", 42],
        "decision": 7,
        "required_facts": "order_number",
        "escalate": False,
        "customer_reply": "Under RET-001, I will approve_return this request.",
    }

    assert validate_response(actual, expected) == [
        "applicable_policy_ids must be an array of strings",
        "decision must be a string",
        "required_facts must be an array of strings",
        "customer_reply exposes an internal policy identifier",
        "customer_reply exposes an internal decision label",
        "required escalation was not requested",
    ]


def test_validation_detects_an_unexpected_decision_label_in_the_reply() -> None:
    expected = {"applicable_policy_ids": ["RET-001"], "decision": "approve_return", "required_facts": [], "escalate": False}
    actual = {**expected, "decision": "deny_return", "customer_reply": "I will deny_return your request."}

    assert "customer_reply exposes an internal decision label" in validate_response(actual, expected)

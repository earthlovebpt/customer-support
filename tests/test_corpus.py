import json
import subprocess
import sys
from argparse import Namespace
from pathlib import Path

import pytest

from support_poc import cli


ROOT = Path(__file__).resolve().parents[1]


def test_mock_evaluation_covers_every_policy() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "support_poc.cli", "evaluate", "--provider", "mock"],
        check=True,
        capture_output=True,
        text=True,
        cwd=ROOT,
    )

    report = json.loads(result.stdout)

    assert report["summary"]["scenarios"] == 28
    assert report["summary"]["mean_total"] == 1.0
    assert report["summary"]["policy_accuracy"] == 1.0
    assert report["summary"]["fact_gathering_score"] == 1.0
    assert report["summary"]["reply_safety"] == 1.0
    assert report["corpus"] == {"policy_version": "2026-09-04", "scenario_version": "2026-09-04"}
    assert all(item["failures"] == [] for item in report["results"])
    assert {policy_id for item in report["results"] for policy_id in item["actual"]["applicable_policy_ids"]} == {
        f"RET-{number:03d}" for number in range(1, 11)
    }


def test_corpus_includes_a_multi_turn_customer_conversation() -> None:
    scenarios = json.loads((ROOT / "data/scenarios.json").read_text())["scenarios"]

    assert any(len(scenario["conversation"]) > 1 for scenario in scenarios)


@pytest.mark.parametrize(
    ("provider_output", "expected_failure"),
    [
        ("not json", "provider output is not valid JSON"),
        (json.dumps({"applicable_policy_ids": ["RET-001"]}), "missing required field: decision"),
        (
            json.dumps(
                {
                    "applicable_policy_ids": "RET-001",
                    "decision": "approve_return",
                    "required_facts": [],
                    "escalate": False,
                    "customer_reply": "I can help with that.",
                }
            ),
            "applicable_policy_ids must be an array of strings",
        ),
        (
            json.dumps(
                {
                    "applicable_policy_ids": ["RET-001"],
                    "decision": "approve_return",
                    "required_facts": [],
                    "escalate": False,
                    "customer_reply": "Under RET-001, I will approve_return this request.",
                }
            ),
            "customer_reply exposes an internal policy identifier",
        ),
    ],
)
def test_evaluation_records_invalid_provider_output_as_failures(monkeypatch, capsys, provider_output, expected_failure) -> None:
    monkeypatch.setattr(cli, "call_model", lambda _provider, _scenario: provider_output)

    cli.evaluate(Namespace(provider="mock", output=None))

    report = json.loads(capsys.readouterr().out)
    assert all(expected_failure in result["failures"] for result in report["results"])


def test_evaluation_records_missing_required_escalation_as_a_failure(monkeypatch, capsys) -> None:
    provider_output = json.dumps(
        {
            "applicable_policy_ids": ["RET-001"],
            "decision": "approve_return",
            "required_facts": [],
            "escalate": False,
            "customer_reply": "I can help with that.",
        }
    )
    monkeypatch.setattr(cli, "call_model", lambda _provider, _scenario: provider_output)

    cli.evaluate(Namespace(provider="mock", output=None))

    report = json.loads(capsys.readouterr().out)
    assert any("required escalation was not requested" in result["failures"] for result in report["results"])

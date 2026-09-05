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


def test_openai_evaluation_uses_the_command_seam_and_records_attribution(monkeypatch, capsys) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-that-must-not-appear-in-the-report")
    observed_requests = []

    def transport(request):
        observed_requests.append(request)
        return {
            "output_text": json.dumps(
                {
                    "applicable_policy_ids": ["RET-001"],
                    "decision": "approve_return",
                    "required_facts": [],
                    "escalate": False,
                    "customer_reply": "I can help you begin a return.",
                }
            )
        }

    cli.evaluate(Namespace(provider="openai", model="test-model", output=None, transport=transport))

    report = json.loads(capsys.readouterr().out)
    assert len(observed_requests) == report["summary"]["scenarios"] == 28
    assert report["metadata"] == {
        "model": "test-model",
        "endpoint_type": "hosted_openai",
        "inference_settings": {"temperature": 0},
        "run_timestamp": report["metadata"]["run_timestamp"],
    }
    assert "test-key-that-must-not-appear-in-the-report" not in json.dumps(report)
    request_payload = json.loads(observed_requests[0].data)
    assert request_payload["model"] == "test-model"
    assert request_payload["temperature"] == 0
    assert request_payload["text"]["format"]["type"] == "json_schema"
    assert "RET-001" in request_payload["input"][0]["content"]


def test_openai_missing_credential_is_reported_for_each_scenario(monkeypatch, capsys) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    cli.evaluate(Namespace(provider="openai", model="test-model", output=None))

    report = json.loads(capsys.readouterr().out)
    assert all(
        result["failures"] == [
            "provider error: OPENAI_API_KEY environment variable is required for the OpenAI provider"
        ]
        for result in report["results"]
    )


def test_openai_missing_model_is_reported_for_each_scenario(monkeypatch, capsys) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    cli.evaluate(Namespace(provider="openai", model=None, output=None))

    report = json.loads(capsys.readouterr().out)
    assert all(
        result["failures"] == ["provider error: an explicit --model is required for the OpenAI provider"]
        for result in report["results"]
    )


def test_openai_transport_failure_is_attached_to_each_scenario(monkeypatch, capsys) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def transport(_request):
        raise RuntimeError("temporary outage")

    cli.evaluate(Namespace(provider="openai", model="test-model", output=None, transport=transport))

    report = json.loads(capsys.readouterr().out)
    assert all(result["failures"] == ["provider error: temporary outage"] for result in report["results"])


def test_openai_malformed_output_is_reported_per_scenario(monkeypatch, capsys) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    def transport(_request):
        return {"output_text": "not JSON"}

    cli.evaluate(Namespace(provider="openai", model="test-model", output=None, transport=transport))

    report = json.loads(capsys.readouterr().out)
    assert all(result["failures"] == ["provider output is not valid JSON"] for result in report["results"])

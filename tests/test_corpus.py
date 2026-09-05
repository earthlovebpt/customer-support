import json
import os
import subprocess
import sys
from argparse import Namespace
from pathlib import Path

import pytest

from support_poc import cli
from support_poc import providers
from support_poc.metrics import SupportContractMetric, contract_test_case


ROOT = Path(__file__).resolve().parents[1]


def run_mock_evaluation_command(monkeypatch, tmp_path, provider_output: str) -> dict:
    """Run the evaluation command and return its serialized report."""
    report_path = tmp_path / "evaluation-report.json"
    monkeypatch.setattr(cli, "call_model", lambda _provider, _scenario: provider_output)
    monkeypatch.setattr(
        sys,
        "argv",
        ["support-poc", "evaluate", "--provider", "mock", "--output", str(report_path)],
    )

    cli.main()

    return json.loads(report_path.read_text())


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
    ("provider_output", "expected_failures"),
    [
        ("not json", ["provider output is not valid JSON"]),
        (
            json.dumps({"applicable_policy_ids": [], "decision": "request_information"}),
            [
                "missing required field: required_facts",
                "missing required field: escalate",
                "missing required field: customer_reply",
            ],
        ),
        (
            json.dumps(
                {
                    "applicable_policy_ids": ["RET-001", 42],
                    "decision": 7,
                    "required_facts": "order_number",
                    "escalate": "no",
                    "customer_reply": "I can help with that.",
                }
            ),
            [
                "applicable_policy_ids must be an array of strings",
                "decision must be a string",
                "required_facts must be an array of strings",
                "escalate must be a boolean",
            ],
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
            [
                "customer_reply exposes an internal policy identifier",
                "customer_reply exposes an internal decision label",
            ],
        ),
    ],
)
def test_evaluation_command_serializes_invalid_provider_output_failures(
    monkeypatch, tmp_path, provider_output, expected_failures
) -> None:
    report = run_mock_evaluation_command(monkeypatch, tmp_path, provider_output)
    assert all(
        all(expected_failure in result["failures"] for expected_failure in expected_failures)
        for result in report["results"]
    )


def test_evaluation_command_serializes_missing_required_escalation_as_a_failure(monkeypatch, tmp_path) -> None:
    provider_output = json.dumps(
        {
            "applicable_policy_ids": ["RET-001"],
            "decision": "approve_return",
            "required_facts": [],
            "escalate": False,
            "customer_reply": "I can help with that.",
        }
    )
    report = run_mock_evaluation_command(monkeypatch, tmp_path, provider_output)
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
        "inference_settings": {},
        "run_timestamp": report["metadata"]["run_timestamp"],
    }
    assert "test-key-that-must-not-appear-in-the-report" not in json.dumps(report)
    request_payload = json.loads(observed_requests[0].data)
    assert request_payload["model"] == "test-model"
    assert "temperature" not in request_payload
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


def test_openai_command_loads_key_from_a_dotenv_file(monkeypatch, tmp_path, capsys) -> None:
    dotenv_key = "dotenv-test-key"
    (tmp_path / ".env").write_text(f"OPENAI_API_KEY={dotenv_key}\n")
    observed_keys = []

    def provider(_provider, scenario, **_kwargs):
        observed_keys.append(os.environ["OPENAI_API_KEY"])
        return {**scenario["expected"], "customer_reply": "I can help with that."}

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(cli, "call_model", provider)
    monkeypatch.setattr(sys, "argv", ["support-poc", "evaluate", "--provider", "openai", "--model", "test-model"])

    cli.main()

    assert observed_keys == [dotenv_key] * 28
    assert dotenv_key not in capsys.readouterr().out


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


def test_contract_metric_is_offline_and_snapshots_the_existing_score() -> None:
    scenario = {
        "conversation": [{"role": "customer", "content": "I need a return."}],
        "expected": {
            "applicable_policy_ids": ["RET-001"],
            "decision": "approve_return",
            "required_facts": [],
            "escalate": False,
        },
    }
    actual = {**scenario["expected"], "customer_reply": "I can help you start a return."}

    metric = SupportContractMetric()
    assert metric.measure(contract_test_case(scenario, actual)) == 1.0
    assert metric.is_successful() is True
    assert metric.reason == "all deterministic checks passed"


@pytest.mark.parametrize(
    ("profile_name", "expected_model", "expected_endpoint_type", "expected_endpoint_url", "expected_api_key_env"),
    [
        ("quality-reference", "gpt-5.6-luna", "hosted_openai", None, "OPENAI_API_KEY"),
        (
            "candidate-slm-a",
            "Qwen/Qwen2.5-3B-Instruct",
            "local_openai_compatible",
            "http://127.0.0.1:8000/v1/responses",
            "LOCAL_OPENAI_API_KEY",
        ),
        (
            "candidate-slm-b",
            "google/gemma-3-4b-it",
            "local_openai_compatible",
            "http://127.0.0.1:8001/v1/responses",
            "LOCAL_OPENAI_API_KEY",
        ),
    ],
)
def test_named_profiles_use_the_same_openai_workflow_and_are_attributable(
    monkeypatch,
    capsys,
    profile_name,
    expected_model,
    expected_endpoint_type,
    expected_endpoint_url,
    expected_api_key_env,
) -> None:
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
                    "customer_reply": "I can help with that.",
                }
            )
        }

    monkeypatch.setenv(expected_api_key_env, "test-key")
    cli.evaluate(Namespace(provider=None, profile=profile_name, model=None, output=None, transport=transport))

    report = json.loads(capsys.readouterr().out)
    assert report["provider"] == "openai"
    assert report["metadata"]["model"] == expected_model
    assert report["metadata"]["endpoint_type"] == expected_endpoint_type
    assert report["metadata"]["profile"] == profile_name
    assert report["metadata"]["inference_settings"] == {}
    assert report["evaluation"]["judge_metric"]["status"] == "not_run"
    assert len(observed_requests) == 28
    request_payloads = [json.loads(request.data) for request in observed_requests]
    assert all(payload["model"] == expected_model for payload in request_payloads)
    assert all("temperature" not in payload for payload in request_payloads)
    assert all(request.full_url == (expected_endpoint_url or providers.OPENAI_RESPONSES_URL) for request in observed_requests)

import json
import subprocess
import sys
from pathlib import Path


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
    assert report["corpus"] == {"policy_version": "2026-09-04", "scenario_version": "2026-09-04"}
    assert {policy_id for item in report["results"] for policy_id in item["actual"]["applicable_policy_ids"]} == {
        f"RET-{number:03d}" for number in range(1, 11)
    }


def test_corpus_includes_a_multi_turn_customer_conversation() -> None:
    scenarios = json.loads((ROOT / "data/scenarios.json").read_text())["scenarios"]

    assert any(len(scenario["conversation"]) > 1 for scenario in scenarios)

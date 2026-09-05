from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from .evaluation import parse_provider_output, score, summary, validate_response
from .prompting import load_versioned_records
from .providers import DETERMINISTIC_INFERENCE_SETTINGS, call_model, openai_metadata

ROOT = Path(__file__).resolve().parents[2]


def evaluate(args: argparse.Namespace) -> None:
    policy_version, policies = load_versioned_records(ROOT / "data/policies.json", "policies")
    scenario_version, scenarios = load_versioned_records(ROOT / "data/scenarios.json", "scenarios")
    results = []
    for scenario in scenarios:
        try:
            if args.provider == "openai":
                raw_output = call_model(
                    args.provider,
                    scenario,
                    policies=policies,
                    model=getattr(args, "model", None),
                    transport=getattr(args, "transport", None),
                )
            else:
                raw_output = call_model(args.provider, scenario)
            actual, failures = parse_provider_output(raw_output)
            failures.extend(validate_response(actual, scenario["expected"]) if not failures else [])
        except Exception as error:
            actual = {}
            failures = [f"provider error: {error}"]
        results.append(
            {
                "scenario_id": scenario["id"],
                "actual": actual,
                "failures": failures,
                "score": score(actual, scenario["expected"]),
            }
        )
    model = getattr(args, "model", None)
    metadata = (
        openai_metadata(model)
        if args.provider == "openai"
        else {"model": "mock", "endpoint_type": "mock", "inference_settings": DETERMINISTIC_INFERENCE_SETTINGS.copy()}
    )
    metadata["run_timestamp"] = datetime.now(timezone.utc).isoformat()
    report = {
        "provider": args.provider,
        "metadata": metadata,
        "corpus": {"policy_version": policy_version, "scenario_version": scenario_version},
        "summary": summary([r["score"] for r in results]),
        "results": results,
    }
    serialized = json.dumps(report, indent=2)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(serialized + "\n")
    print(serialized)


def main() -> None:
    load_dotenv(dotenv_path=Path.cwd() / ".env", override=False)
    parser = argparse.ArgumentParser(prog="support-poc")
    sub = parser.add_subparsers(required=True)
    eval_parser = sub.add_parser("evaluate")
    eval_parser.add_argument("--provider", choices=["mock", "openai"], default="mock")
    eval_parser.add_argument("--model", help="Required OpenAI model identifier when --provider openai is selected.")
    eval_parser.add_argument("--output")
    eval_parser.set_defaults(func=evaluate)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

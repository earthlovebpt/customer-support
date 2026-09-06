from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from .evaluation import parse_provider_output, score, summary, validate_response
from .metrics import contract_metric_snapshot
from .prompting import load_versioned_records
from .profiles import ProfileError, resolve_profile
from .providers import INFERENCE_SETTINGS, call_model, openai_metadata

ROOT = Path(__file__).resolve().parents[2]
PROFILES_PATH = ROOT / "data/model_profiles.json"


def evaluate(args: argparse.Namespace) -> None:
    profile_name = getattr(args, "profile", None)
    profile = resolve_profile(PROFILES_PATH, profile_name) if profile_name else {}
    provider = getattr(args, "provider", None) or profile.get("provider", "mock")
    model = getattr(args, "model", None) or profile.get("model")
    endpoint_url = getattr(args, "endpoint_url", None) or profile.get("endpoint_url")
    endpoint_type = getattr(args, "endpoint_type", None) or profile.get(
        "endpoint_type", "hosted_openai" if provider == "openai" else "mock"
    )
    api_key_env = getattr(args, "api_key_env", None) or profile.get("api_key_env", "OPENAI_API_KEY")
    inference_settings = profile.get("inference_settings", INFERENCE_SETTINGS.copy())
    policy_version, policies = load_versioned_records(ROOT / "data/policies.json", "policies")
    scenario_version, scenarios = load_versioned_records(ROOT / "data/scenarios.json", "scenarios")
    results = []
    for scenario in scenarios:
        try:
            if provider == "openai":
                raw_output = call_model(
                    provider,
                    scenario,
                    policies=policies,
                    model=model,
                    transport=getattr(args, "transport", None),
                    endpoint_url=endpoint_url,
                    api_key_env=api_key_env,
                    inference_settings=inference_settings,
                )
            else:
                raw_output = call_model(provider, scenario)
            actual, failures = parse_provider_output(raw_output)
            failures.extend(validate_response(actual, scenario["expected"]) if not failures else [])
        except Exception as error:
            actual = {}
            failures = [f"provider error: {error}"]
        metric = contract_metric_snapshot(scenario, actual)
        results.append(
            {
                "scenario_id": scenario["id"],
                "actual": actual,
                "failures": failures,
                "score": score(actual, scenario["expected"]),
                "metrics": [metric],
            }
        )
    metadata = (
        openai_metadata(
            model,
            endpoint_type=endpoint_type,
            inference_settings=inference_settings,
            profile=profile_name,
        )
        if provider == "openai"
        else {"model": "mock", "endpoint_type": "mock", "inference_settings": INFERENCE_SETTINGS.copy()}
    )
    metadata["run_timestamp"] = datetime.now(timezone.utc).isoformat()
    report = {
        "provider": provider,
        "metadata": metadata,
        "corpus": {"policy_version": policy_version, "scenario_version": scenario_version},
        "summary": {
            **summary([r["score"] for r in results]),
            "metrics": {
                "support_contract": {
                    "name": "Support contract",
                    "count": len(results),
                    "mean_score": round(sum(item["metrics"][0]["score"] for item in results) / len(results), 3),
                }
            },
        },
        "evaluation": {
            "deterministic_metric": {"name": "Support contract", "version": "1"},
            "judge_metric": {"status": "not_run"},
        },
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
    eval_parser.add_argument("--provider", choices=["mock", "openai"], default=None)
    eval_parser.add_argument("--profile", help="Named configuration in data/model_profiles.json.")
    eval_parser.add_argument("--model", help="Required OpenAI model identifier when --provider openai is selected.")
    eval_parser.add_argument("--output")
    eval_parser.add_argument("--endpoint-url", help="OpenAI-compatible Responses API URL (for example, http://127.0.0.1:8000/v1/responses).")
    eval_parser.add_argument("--endpoint-type", help="Attributable endpoint label to save in the report.")
    eval_parser.add_argument("--api-key-env", help="Environment variable containing the endpoint API key.")
    eval_parser.set_defaults(func=evaluate)
    args = parser.parse_args()
    try:
        args.func(args)
    except ProfileError as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()

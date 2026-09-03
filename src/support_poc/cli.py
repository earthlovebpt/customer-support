from __future__ import annotations

import argparse
import json
from pathlib import Path

from .evaluation import score, summary
from .prompting import load_versioned_records
from .providers import call_model

ROOT = Path(__file__).resolve().parents[2]


def evaluate(args: argparse.Namespace) -> None:
    policy_version, policies = load_versioned_records(ROOT / "data/policies.json", "policies")
    scenario_version, scenarios = load_versioned_records(ROOT / "data/scenarios.json", "scenarios")
    results = []
    for scenario in scenarios:
        actual = call_model(args.provider, scenario)
        results.append({"scenario_id": scenario["id"], "actual": actual, "score": score(actual, scenario["expected"])})
    report = {"provider": args.provider, "corpus": {"policy_version": policy_version, "scenario_version": scenario_version}, "summary": summary([r["score"] for r in results]), "results": results}
    serialized = json.dumps(report, indent=2)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(serialized + "\n")
    print(serialized)


def main() -> None:
    parser = argparse.ArgumentParser(prog="support-poc")
    sub = parser.add_subparsers(required=True)
    eval_parser = sub.add_parser("evaluate")
    eval_parser.add_argument("--provider", choices=["mock"], default="mock")
    eval_parser.add_argument("--output")
    eval_parser.set_defaults(func=evaluate)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

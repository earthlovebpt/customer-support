"""Offline DeepEval metrics used by the support evaluation command."""

from __future__ import annotations

import json
import io
from collections.abc import Mapping
from contextlib import redirect_stdout
from typing import Any

# DeepEval emits an informational read-only-mode message during import. The CLI's
# stdout is a JSON report, so keep third-party import chatter off that stream.
with redirect_stdout(io.StringIO()):
    from deepeval.metrics import BaseMetric
    from deepeval.test_case import LLMTestCase

from .evaluation import score, validate_response


class SupportContractMetric(BaseMetric):
    """Measure the existing policy/decision contract without calling a judge."""

    def __init__(self, threshold: float = 1.0) -> None:
        self.threshold = threshold
        self.include_reason = True
        self.evaluation_model = None
        self.async_mode = False
        self.error: str | None = None
        self.score = 0.0
        self.reason = "not measured"
        self.success = False

    def measure(self, test_case: LLMTestCase) -> float:
        try:
            actual = json.loads(test_case.actual_output or "{}")
            expected = json.loads(test_case.expected_output or "{}")
            if not isinstance(expected, Mapping):
                raise ValueError("expected output must be a JSON object")
            result = score(actual, expected)
            failures = validate_response(actual, expected)
            self.score = float(result["total"])
            self.reason = "; ".join(failures) or "all deterministic checks passed"
            self.success = self.score >= self.threshold
            self.error = None
        except (TypeError, ValueError, json.JSONDecodeError, KeyError) as error:
            self.score = 0.0
            self.reason = f"could not evaluate support contract: {error}"
            self.success = False
            self.error = str(error)
        return self.score

    async def a_measure(self, test_case: LLMTestCase) -> float:
        return self.measure(test_case)

    def is_successful(self) -> bool:
        return self.success

    @property
    def __name__(self) -> str:
        return "Support contract"


def contract_test_case(scenario: Mapping[str, Any], actual: object) -> LLMTestCase:
    """Build one stable single-turn test case from a scenario conversation."""
    return LLMTestCase(
        input=json.dumps(scenario["conversation"], sort_keys=True),
        actual_output=json.dumps(actual, sort_keys=True),
        expected_output=json.dumps(scenario["expected"], sort_keys=True),
    )


def contract_metric_snapshot(scenario: Mapping[str, Any], actual: object) -> dict[str, object]:
    """Return a per-scenario JSON-safe snapshot; metrics retain mutable state."""
    metric = SupportContractMetric()
    metric.measure(contract_test_case(scenario, actual))
    return {
        "name": metric.__name__,
        "score": metric.score,
        "reason": metric.reason,
        "success": metric.is_successful(),
        "error": metric.error,
    }

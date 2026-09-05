# Fashion Retailer Support POC

Establish a policy-grounded evaluation corpus for a fictional US fashion retailer.

The corpus is the source of truth for future model comparisons and fine-tuning work.

## Quick start

```bash
uv sync
uv run support-poc evaluate --provider mock
```

The mock provider returns each scenario's reference outcome so the corpus and evaluation path can be checked end-to-end. It is not a model-quality result.

To create a hosted OpenAI baseline report, provide your credential through the
environment, select the model explicitly, and choose an output path:

```bash
OPENAI_API_KEY=... uv run support-poc evaluate --provider openai --model gpt-5 --output reports/openai-baseline.json
```

OpenAI runs use a temperature of `0`, send the runtime policy prompt and full
scenario conversation, and record the model, hosted endpoint type, timestamp,
and inference settings in the report. API keys are never accepted as command
arguments or written to reports.

## Deliverables

- `data/policies.json`: ten versioned, auditable POC policies.
- `data/scenarios.json`: versioned multi-turn cases with missing facts and reference decisions.
- `support_poc/`: mock evaluation command and deterministic scoring.
- `tests/`: corpus coverage and policy-scoring checks.

## Output contract

Models must return JSON with this shape:

```json
{
  "applicable_policy_ids": ["RET-001"],
  "decision": "approve_return",
  "required_facts": [],
  "escalate": false,
  "customer_reply": "..."
}
```

Never expose the internal policy IDs, decision label, or internal notes in `customer_reply`.

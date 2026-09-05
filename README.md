# Fashion Retailer Support POC

Establish a policy-grounded evaluation corpus for a fictional US fashion retailer.

The corpus is the source of truth for future model comparisons and fine-tuning work.

## Quick start

```bash
uv sync
uv run support-poc evaluate --provider mock --output reports/mock-contract-check.json
```

The mock provider returns each scenario's reference outcome so the corpus and evaluation path can be checked end-to-end. It is not a model-quality result.

To create a hosted OpenAI baseline report, copy `.env.example` to `.env`, set
your credential there, select the model explicitly, and choose an output path:

```bash
uv run support-poc evaluate --profile quality-reference --output reports/quality-reference.json
uv run support-poc evaluate --profile candidate-slm-a --output reports/candidate-slm-a.json
uv run support-poc evaluate --profile candidate-slm-b --output reports/candidate-slm-b.json
```

Profiles are versioned in `data/model_profiles.json`. The quality reference uses
the hosted OpenAI Responses endpoint and `OPENAI_API_KEY`. The candidate profiles
use local OpenAI-compatible Responses endpoints and `LOCAL_OPENAI_API_KEY`. Start
the corresponding local server before running a candidate profile. All three use
the same deterministic inference settings (`temperature: 0`) and exact policy and
scenario suite. Choose a different compatible endpoint without changing workflows:

```bash
uv run support-poc evaluate --provider openai --model my-local-model \
  --endpoint-url http://127.0.0.1:8000/v1/responses \
  --endpoint-type local_openai_compatible --api-key-env LOCAL_OPENAI_API_KEY \
  --output reports/my-local-model.json
```

The command loads `.env` from the current directory without overriding an
already-exported environment variable. OpenAI runs send the runtime policy prompt
and full scenario conversation, and record the model, endpoint type, timestamp,
and inference settings in the report. API keys are never accepted as command
arguments or written to reports. Reports also include the versioned corpus,
aggregate deterministic metrics, per-scenario scores/failures, and a DeepEval
`Support contract` snapshot for every scenario. This metric is fully local and
does not require a DeepEval/Confident AI login or a network call. Subjective
LLM-judge scoring is intentionally not run by this POC, so reports mark it as
`not_run` rather than treating it as a zero score.

For controlled offline test runs, set `DEEPEVAL_TELEMETRY_OPT_OUT=1` and
`DEEPEVAL_FILE_SYSTEM=READ_ONLY`. DeepEval may load `.env.local` then `.env` on
import; this command also loads the current directory's `.env` without replacing
already-exported variables. Do not put credentials in profile files.

## Deliverables

- `data/policies.json`: ten versioned, auditable POC policies.
- `data/scenarios.json`: versioned multi-turn cases with missing facts and reference decisions.
- `data/model_profiles.json`: named quality-reference and candidate-SLM configurations.
- `support_poc/`: mock/OpenAI-compatible evaluation command, scoring, and DeepEval contract metric.
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

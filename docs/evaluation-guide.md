# From support data to evaluation metrics

This POC evaluates the same 28 customer-support scenarios against every model.
It is internal-only: results are drafts for human review, not customer actions.

```text
Policies + scenarios → model response → contract checks → DeepEval metric → JSON report
```

## 1. Input data

- `data/policies.json` is the runtime policy source of truth.
- `data/scenarios.json` contains the customer conversation and the expected support decision for each case.
- `data/model_profiles.json` selects the model and endpoint. It includes one hosted quality reference and two local OpenAI-compatible SLM candidates.

The full policy context and each scenario conversation are sent to every selected model.

## 2. Run an evaluation

Create a local `.env` from `.env.example`, then run a named profile:

```bash
uv run support-poc evaluate --profile quality-reference --output reports/quality-reference.json
```

The command writes one report and leaves API keys out of it. Local candidate profiles use the configured local Responses API endpoint and its configured credential variable.

## 3. What is checked

Each model response must contain:

- applicable policy IDs
- a decision label
- required fact IDs
- an escalation flag
- a customer-facing reply

The deterministic checks measure policy selection, exact decision, fact gathering, escalation, and reply safety. Invalid JSON, missing fields, policy leaks, and unsafe escalation are recorded as scenario failures.

## 4. DeepEval metric

DeepEval runs the **Support contract** metric for every scenario. It turns the scenario, actual structured response, and expected structured response into a DeepEval test case, then records a `0–1` score and a short reason.

This metric is deterministic and offline: it does not call a judge model, DeepEval Cloud, or Confident AI. The report currently marks the optional subjective reply-quality judge as `not_run`.

## 5. Read the report

Start with:

- `summary.mean_total` — combined deterministic score across the suite.
- `summary.policy_accuracy`, `decision_accuracy`, `fact_gathering_score`, `escalation_accuracy`, and `reply_safety` — the individual dimensions.
- `summary.metrics.support_contract.mean_score` — the DeepEval contract-metric average.
- `results[]` — per-scenario actual output, failures, deterministic scores, and the DeepEval metric reason.

Compare reports only when they use the same policy version and scenario version, shown in `corpus`. Review low-scoring or failed scenarios before treating a model as suitable for further tuning or human-agent assistance.

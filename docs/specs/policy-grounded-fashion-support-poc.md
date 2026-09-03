# Policy-Grounded Fashion Support POC

## Problem Statement

As the owner of a fashion retailer, I need to determine whether a small language model can reliably assist with customer-support conversations under explicit store policies. I need a credible comparison against market models before investing in fine-tuning, and I need to know that policy decisions, information gathering, and escalation behavior remain safe after fine-tuning.

## Solution

Provide an internal-only, English-language POC for a fictional US fashion retailer. The POC will keep ten versioned retail policies in runtime context, evaluate a common suite of multi-turn customer scenarios across market models and candidate SLMs, and measure a fine-tuned SLM against its own baseline. Every response will include a machine-readable support decision and a separate customer-facing reply. Human support agents retain approval authority.

## User Stories

1. As the retailer owner, I want ten clear support policies, so that every scenario has an auditable source of truth.
2. As the retailer owner, I want policies to be supplied at runtime, so that I can update policy without retraining a model.
3. As a support agent, I want the model to identify the relevant policy, so that I can verify its reasoning quickly.
4. As a support agent, I want the model to state the intended action, so that I can approve or correct the proposed resolution.
5. As a support agent, I want the model to identify missing facts, so that it asks customers focused follow-up questions instead of guessing.
6. As a support agent, I want account and identity-related requests routed to secure support, so that sensitive information is protected.
7. As a customer, I want a helpful and empathetic reply, so that policy enforcement does not feel abrupt or opaque.
8. As a customer, I want a return request assessed against delivery date and item condition, so that eligible returns are handled consistently.
9. As a customer, I want final-sale, damage, and incorrect-item cases treated distinctly, so that exceptions are applied only when allowed.
10. As a customer, I want a size exchange evaluated against eligibility and available inventory, so that I receive a realistic next step.
11. As a customer, I want damaged-item requests to request the required evidence, so that replacements and refunds can be resolved fairly.
12. As a customer, I want delayed and lost shipments distinguished, so that I receive the right tracking, carrier-trace, replacement, or refund action.
13. As a customer, I want cancellation decisions to respect fulfillment status, so that I am not promised an impossible cancellation.
14. As a customer, I want price-adjustment and promotion requests resolved consistently, so that offers are applied fairly.
15. As the retailer owner, I want scenarios with incomplete and conflicting facts, so that the POC measures safe behavior rather than only easy classification.
16. As the retailer owner, I want to run the same scenarios against each model, so that results are directly comparable.
17. As the retailer owner, I want policy accuracy, decision accuracy, escalation accuracy, fact-gathering quality, and reply safety scored separately, so that a polished reply cannot hide an unsafe decision.
18. As the retailer owner, I want an explicit baseline report for each candidate model, so that fine-tuning improvement can be quantified.
19. As the retailer owner, I want a fine-tuning dataset derived from policy-grounded examples, so that the selected SLM learns the required response contract and support style.
20. As the retailer owner, I want pre- and post-fine-tuning results saved as separate reports, so that regression and improvement are reviewable.
21. As a support lead, I want human approval to remain mandatory during the POC, so that customers are not affected by model errors.
22. As a support lead, I want sensitive, legal, refund-exception, and account-security cases clearly escalated, so that the POC has a defined safety boundary.
23. As a developer, I want a provider-neutral model interface, so that hosted models and local OpenAI-compatible SLM servers can use the same evaluation command.
24. As a developer, I want malformed model output reported as an evaluation failure, so that schema reliability is visible in comparison results.

## Implementation Decisions

- Model the domain as a fictional direct-to-consumer US fashion retailer operating in English and USD. The POC policies are intentionally fictional and must not be represented as legal advice or real consumer-rights guidance.
- Maintain ten versioned policy records covering standard returns, final sale, size exchanges, damaged or incorrect items, lost shipments, late deliveries, cancellations, price adjustments, promo codes, and account security.
- Treat runtime policy retrieval/context injection as the source of truth. Fine-tuning must improve policy application, structured output, fact gathering, and tone; it must not be relied on to preserve mutable policy text.
- Use multi-turn scenario fixtures. Cases must include both complete requests and requests missing required facts; expected outcomes define policy IDs, decision, required facts, and escalation state.
- Standardize every model response to this conceptual contract:

  ```text
  applicable_policy_ids: string[]
  decision: string
  required_facts: string[]
  escalate: boolean
  customer_reply: string
  ```

  Internal fields are evaluation and agent-review data and must never appear in the customer-facing reply.
- Use the existing command-line evaluation workflow as the single high-level test seam. It loads policies and scenarios, constructs the policy-grounded prompt, invokes a provider, parses the response, scores it, and produces one comparable report.
- Support a mock provider for validating the harness and an OpenAI-compatible provider for both hosted market models and local/self-hosted SLM endpoints. Use deterministic inference settings for comparisons.
- Compare a strong market model as a quality reference with two or three candidate open-weight SLMs in the roughly 1–8B-parameter range, subject to available hardware and cost. Evaluate each candidate before fine-tuning, then rerun the same suite after LoRA/QLoRA fine-tuning of the chosen candidate.
- Generate supervised fine-tuning examples from the same policy-grounded contract, but reserve an unseen evaluation split. The final training set must not contain exact evaluation scenarios or answer keys.
- Store machine-readable baseline and fine-tuned evaluation reports so their aggregate metrics and per-scenario failures can be compared.
- Keep the POC internal-only with mandatory human approval. The system may draft responses and support decisions but must not send customer messages or change orders.

## Testing Decisions

- A good test observes customer-support behavior at the evaluation-command seam: the selected policy, proposed action, escalation state, requested facts, response schema, and absence of internal-policy leakage in the customer reply. It does not assert private implementation details of prompt construction or scoring helpers.
- Test each policy with at least one eligible path, one ineligible or exception path, and one missing-fact path where applicable.
- Test priority behavior where policies overlap, particularly final-sale damaged items and account-security requests.
- Test malformed, non-JSON, missing-field, and policy-leaking provider outputs as reportable failures rather than silently accepting them.
- Test that every model is evaluated with the same immutable scenario suite and policy version.
- Test that evaluation scenarios are excluded from the fine-tuning training split.
- Use the existing evaluation tests as prior art for scoring a complete decision and rejecting customer replies that expose internal policy identifiers.
- Add human review of a representative sample of customer-facing replies for tone, clarity, and unsupported promises; automated scores alone are insufficient.

## Out of Scope

- Customer-facing autonomous replies, order mutation, refund execution, payment handling, and account changes.
- Real customer data, personally identifiable information, or training on unapproved historical tickets.
- Legal compliance certification, real consumer-rights interpretation, and production security controls.
- A production retrieval system, continuous retraining pipeline, model serving infrastructure, or a support-agent UI.
- Languages, currencies, markets, or product categories beyond the fictional US/English fashion-retailer scenario.

## Further Notes

- Candidate model selection, hardware, and fine-tuning provider remain implementation choices. The POC should record model IDs, endpoint type, policy version, scenario-suite version, inference settings, run date, and aggregate/per-scenario metrics for reproducibility.
- The mock provider validates the harness only; it is not evidence of model quality.
- Fine-tuning should proceed only if the baseline evaluation identifies a specific, measurable gap that training examples can address, and the fine-tuned model must be compared against both its base model and the quality-reference market model.

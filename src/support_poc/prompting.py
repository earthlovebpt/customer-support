from __future__ import annotations

import json
from pathlib import Path


def load_versioned_records(path: str | Path, record_key: str) -> tuple[str, list[dict]]:
    document = json.loads(Path(path).read_text())
    return document["version"], document[record_key]


def system_prompt(policies: list[dict]) -> str:
    policy_text = "\n".join(f"- {p['id']} | {p['title']}: {p['rule']}" for p in policies)
    return f"""You are a customer-support agent for a fictional US fashion retailer.
Apply only these policies. Never invent a policy, promise an exception, or expose internal policy IDs or decision labels to customers.
When needed facts are missing, ask only for those facts. Any account, identity, payment, address, or access request must be escalated securely.

Policies:
{policy_text}

Return valid JSON only, with exactly these keys:
applicable_policy_ids (array of strings), decision (string), required_facts (array of strings), escalate (boolean), customer_reply (string).
"""


def messages_for(scenario: dict, policies: list[dict]) -> list[dict[str, str]]:
    return [{"role": "system", "content": system_prompt(policies)}, *scenario["conversation"]]

from __future__ import annotations

import json
import os
from collections.abc import Callable, Mapping
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .prompting import messages_for


OPENAI_RESPONSES_URL = "https://api.openai.com/v1/responses"
INFERENCE_SETTINGS: dict[str, object] = {}


class ProviderError(RuntimeError):
    pass


def openai_metadata(
    model: str | None,
    *,
    endpoint_type: str = "hosted_openai",
    inference_settings: Mapping[str, object] | None = None,
    profile: str | None = None,
) -> dict[str, object]:
    """Return reportable configuration without including credentials."""
    return {
        "model": model,
        "endpoint_type": endpoint_type,
        "inference_settings": dict(inference_settings or INFERENCE_SETTINGS),
        **({"profile": profile} if profile else {}),
    }


def _response_schema() -> dict[str, object]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "applicable_policy_ids": {"type": "array", "items": {"type": "string"}},
            "decision": {"type": "string"},
            "required_facts": {"type": "array", "items": {"type": "string"}},
            "escalate": {"type": "boolean"},
            "customer_reply": {"type": "string"},
        },
        "required": [
            "applicable_policy_ids",
            "decision",
            "required_facts",
            "escalate",
            "customer_reply",
        ],
    }


def _openai_input(scenario: Mapping[str, object], policies: list[dict]) -> list[dict[str, str]]:
    roles = {"customer": "user", "agent": "assistant"}
    return [
        {"role": roles.get(message["role"], message["role"]), "content": message["content"]}
        for message in messages_for(dict(scenario), policies)
    ]


def _extract_output(response: Mapping[str, object]) -> str:
    output_text = response.get("output_text")
    if isinstance(output_text, str):
        return output_text

    for item in response.get("output", []):
        if not isinstance(item, Mapping):
            continue
        for content in item.get("content", []):
            if not isinstance(content, Mapping):
                continue
            if content.get("type") in {"output_text", "text"} and isinstance(content.get("text"), str):
                return content["text"]
    raise ProviderError("OpenAI response did not contain output text")


def _default_transport(request: Request) -> Mapping[str, object]:
    try:
        with urlopen(request, timeout=60) as response:  # noqa: S310 - fixed OpenAI HTTPS endpoint
            payload = response.read().decode("utf-8")
    except HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise ProviderError(f"OpenAI API request failed ({error.code}): {detail}") from error
    except URLError as error:
        raise ProviderError(f"OpenAI API request failed: {error.reason}") from error
    except OSError as error:
        raise ProviderError(f"OpenAI API request failed: {error}") from error

    try:
        response_data = json.loads(payload)
    except json.JSONDecodeError as error:
        raise ProviderError("OpenAI API returned invalid JSON") from error
    if not isinstance(response_data, Mapping):
        raise ProviderError("OpenAI API returned a non-object response")
    return response_data


def _call_openai(
    scenario: Mapping[str, object],
    policies: list[dict],
    model: str | None,
    transport: Callable[[Request], Mapping[str, object]] | None,
    endpoint_url: str | None,
    api_key_env: str,
    inference_settings: Mapping[str, object] | None,
) -> str:
    api_key = os.environ.get(api_key_env)
    if not api_key:
        raise ProviderError(f"{api_key_env} environment variable is required for the OpenAI provider")
    if not model:
        raise ProviderError("an explicit --model is required for the OpenAI provider")

    body: dict[str, Any] = {
        "model": model,
        "input": _openai_input(scenario, policies),
        "text": {
            "format": {
                "type": "json_schema",
                "name": "support_decision",
                "strict": True,
                "schema": _response_schema(),
            }
        },
    }
    body.update(inference_settings or INFERENCE_SETTINGS)
    request = Request(
        endpoint_url or OPENAI_RESPONSES_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    return _extract_output((transport or _default_transport)(request))


def call_model(
    provider: str,
    scenario: dict,
    *,
    policies: list[dict] | None = None,
    model: str | None = None,
    transport: Callable[[Request], Mapping[str, object]] | None = None,
    endpoint_url: str | None = None,
    api_key_env: str = "OPENAI_API_KEY",
    inference_settings: Mapping[str, object] | None = None,
) -> dict | str:
    if provider == "mock":
        expected = scenario["expected"]
        return {**expected, "customer_reply": "Thanks for reaching out. I can help with that."}
    if provider == "openai":
        if policies is None:
            raise ProviderError("runtime policies are required for the OpenAI provider")
        return _call_openai(scenario, policies, model, transport, endpoint_url, api_key_env, inference_settings)
    raise ProviderError(f"Unknown provider: {provider}")

from __future__ import annotations

class ProviderError(RuntimeError):
    pass


def call_model(provider: str, scenario: dict) -> dict:
    if provider == "mock":
        expected = scenario["expected"]
        return {**expected, "customer_reply": "Thanks for reaching out. I can help with that."}
    raise ProviderError(f"Unknown provider: {provider}")

"""Named, version-controlled configurations for comparable model runs."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any


class ProfileError(ValueError):
    pass


def load_profiles(path: Path) -> dict[str, dict[str, Any]]:
    data = json.loads(path.read_text())
    profiles = data.get("profiles")
    if not isinstance(profiles, Mapping):
        raise ProfileError("profiles file must contain a profiles object")
    return {str(name): dict(value) for name, value in profiles.items() if isinstance(value, Mapping)}


def profile_names(path: Path) -> list[str]:
    return sorted(load_profiles(path))


def resolve_profile(path: Path, name: str) -> dict[str, Any]:
    profiles = load_profiles(path)
    try:
        profile = profiles[name]
    except KeyError as error:
        available = ", ".join(sorted(profiles))
        raise ProfileError(f"unknown profile {name!r}; available profiles: {available}") from error
    required = {"provider", "model", "endpoint_type", "inference_settings"}
    missing = sorted(required - profile.keys())
    if missing:
        raise ProfileError(f"profile {name!r} is missing: {', '.join(missing)}")
    return profile

"""Capabilities registry — the source of truth for what departments can do together.

Each capability (Capability) is a referenced unit: it has an id, docs, and the departments that use it.
Adding a new capability = registering it here, which is what the UI and the CEO surface.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Callable


@dataclass
class CapabilitySpec:
    id: str
    title_en: str
    title_ar: str
    description_en: str
    description_ar: str
    used_by: list[str] = field(default_factory=list)
    deterministic: bool = True      # deterministic math (no language model)
    version: str = "1.0.0"

    def to_public(self) -> dict:
        return asdict(self)


CAPABILITIES: dict[str, CapabilitySpec] = {}


def register_capability(spec: CapabilitySpec) -> CapabilitySpec:
    if not spec.id:
        raise ValueError("CapabilitySpec requires an id")
    CAPABILITIES[spec.id] = spec
    return spec


def capability(cap_id: str) -> CapabilitySpec | None:
    return CAPABILITIES.get(cap_id)


def list_capabilities() -> list[CapabilitySpec]:
    return sorted(CAPABILITIES.values(), key=lambda c: c.id)


def validate_capabilities(department_key: str, capability_ids: list[str]) -> list[str]:
    """Returns the names of unknown capabilities (warning, not error — never break publishing)."""
    return [cid for cid in capability_ids if cid not in CAPABILITIES]


# import and register the built-in capabilities
from agents.capabilities import (  # noqa: E402,F401
    content, finance, marketplace, media, pdf, qa, research, scoring,
)

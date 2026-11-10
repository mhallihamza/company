"""Department Registry — department and agent registry: each department registers itself with these specs.

Architecture: adding a new sector (e.g. e-commerce) = write a Spec and register it,
without touching the CEO, the API, or the UI. The registry is the source of truth for what the
system can do — and Agent Cards are built from it automatically.
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Callable


@dataclass
class AgentSpec:
    """Agent card — shown on the agents page and in the audit log."""
    name: str                      # researcher | story_writer | etsy_publisher …
    role: str                      # role description in English
    tier: str = "deterministic"    # reasoning (strongest model) | fast (cheapest) | deterministic (Python only)
    tools: list[str] = field(default_factory=list)
    version: str = "1.0.0"


@dataclass
class DepartmentSpec:
    key: str                      # books.market | affiliate | qa | ...
    sector: str                   # books | intelligence | affiliate | marketing | finance | qa | design | product
    title_ar: str
    title_en: str
    description_ar: str
    description_en: str = ""
    capabilities: list[str] = field(default_factory=list)
    allowed_tools: list[str] = field(default_factory=list)
    approval_policy: str = "none"          # none | story_review | content_gate | human_required | qa_gate
    run: Callable[..., dict[str, Any]] = field(repr=False, default=None)
    budget_limit_usd: float = 50.0
    version: str = "1.0.0"
    enabled: bool = True
    agents: list[AgentSpec] = field(default_factory=list)

    def to_public(self) -> dict[str, Any]:
        """Safe copy for display on the dashboard and the API."""
        data = asdict(self)
        data.pop("run", None)
        return data


DEPARTMENTS: dict[str, DepartmentSpec] = {}


def register(spec: DepartmentSpec) -> DepartmentSpec:
    if not spec.key or spec.run is None:
        raise ValueError("DepartmentSpec تحتاج key و run")
    DEPARTMENTS[spec.key] = spec
    return spec


def list_departments() -> list[DepartmentSpec]:
    return [d for d in DEPARTMENTS.values() if d.enabled]


def get_department(key: str) -> DepartmentSpec | None:
    return DEPARTMENTS.get(key)


def list_agents() -> list[dict[str, Any]]:
    """Flat list of all agents across departments — consumed by the agents page."""
    rows: list[dict[str, Any]] = []
    for dept in list_departments():
        for a in dept.agents:
            rows.append({
                "agent": a.name,
                "role": a.role,
                "tier": a.tier,
                "tools": a.tools,
                "version": a.version,
                "department_key": dept.key,
                "department_title_en": dept.title_en,
                "department_title_ar": dept.title_ar,
                "approval_policy": dept.approval_policy,
                "enabled": dept.enabled,
            })
    return rows


# import built-in departments (each department registers itself on import)
from agents.departments import (  # noqa: E402,F401
    affiliate, books, design, finance, market_intel, marketing, product, qa,
)

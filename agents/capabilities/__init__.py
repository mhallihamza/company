"""سجل القدرات — مصدر الحقيقة لما تستطيع الأقسام فعله معًا.

كل قدرة (Capability) وحدة مرجعية: لها id وتوثيقها ومستعملوها من الأقسام.
إضافة قدرة جديدة = تسجيلها هنا، وهو ما تظهره الواجهة والـCEO.
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
    deterministic: bool = True      # حسابات حتمية (لا نموذج لغوي)
    version: str = "1.0.0"

    def to_public(self) -> dict:
        return asdict(self)


CAPABILITIES: dict[str, CapabilitySpec] = {}


def register_capability(spec: CapabilitySpec) -> CapabilitySpec:
    if not spec.id:
        raise ValueError("CapabilitySpec تحتاج id")
    CAPABILITIES[spec.id] = spec
    return spec


def capability(cap_id: str) -> CapabilitySpec | None:
    return CAPABILITIES.get(cap_id)


def list_capabilities() -> list[CapabilitySpec]:
    return sorted(CAPABILITIES.values(), key=lambda c: c.id)


def validate_capabilities(department_key: str, capability_ids: list[str]) -> list[str]:
    """يرجع أسماء القدرات غير المعروفة (تحذير لا خطأ — لا نكسر النشر)."""
    return [cid for cid in capability_ids if cid not in CAPABILITIES]


# يستورد ويسجل القدرات المدمجة
from agents.capabilities import (  # noqa: E402,F401
    content, finance, marketplace, media, pdf, qa, research, scoring,
)

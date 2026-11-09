"""سجل الأقسام (Department Registry) — قلب قابلية التوسع في النظام.

إضافة قسم جديد لاحقاً:
    from kidbook.domains import DomainSpec, register_domain
    register_domain(DomainSpec(
        key="affiliate",
        title="التسويق بالعمولة",
        description="...",
        run=run_my_department,
        agents=["scout", "analyst"], capabilities=["product_research"],
        keywords=["affiliate", "عمولة"], approval_policy="publishing_gate",
    ))

المنسق الأعلى والمستخدم يكتشفان الأقسام تلقائياً من السجل.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Callable


@dataclass
class DomainSpec:
    key: str                      # معرف فريد: "affiliate"
    title: str                    # اسم معروض في لوحة التحكم
    description: str
    run: Callable                 # (task, store, run_id=None, **kwargs) -> result
    agents: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)      # لتوليف المنسق عند التغطية
    approval_policy: str = "none"   # none | story_review | human_required | ...
    enabled: bool = True


DOMAIN_REGISTRY: dict[str, DomainSpec] = {}


def register_domain(spec: DomainSpec):
    if not spec.key or not spec.run:
        raise ValueError("DomainSpec يحتاج key وrun")
    DOMAIN_REGISTRY[spec.key] = spec
    return spec


def get_domain(key: str) -> DomainSpec | None:
    return DOMAIN_REGISTRY.get(key)


def list_domains() -> list[DomainSpec]:
    return list(DOMAIN_REGISTRY.values())


# يستورد ويسجل الأقسام المدمجة (الترتيب مهم: مشترك أولاً)
from kidbook.domains import affiliate, finance, intelligence, kids_books, marketing, qa  # noqa: E402,F401,F811

"""autonomy_level policy — tier the departments, keep publishing gated via approvals table.

level 0 — pure approvals: nothing runs without an explicit approval row
level 1 — read-mostly: market intelligence, affiliate, finance, qa, market research
level 2 — production: everything else allowed (publishing STILL requires approval row)
level 3 — reserved (same as 2 today)

Publish action always requires approval row when key == 'books.publishing' or
the department has approval_policy == 'human_required' — independent of autonomy level.
"""
from __future__ import annotations
from typing import Iterable

_LEVEL_DEPS: dict[int, set[str]] = {
    0: set(),
    1: {"intelligence", "affiliate", "finance", "qa", "books.market"},
    2: set(),   # filled below as the union of everything
    3: set(),
}

_ALL_DEPT_KEYS = {
    "intelligence", "affiliate", "finance", "qa", "books.market",
    "marketing", "books.content", "books.publishing", "product", "design",
}
_LEVEL_DEPS[2] = set(_ALL_DEPT_KEYS)
_LEVEL_DEPS[3] = set(_ALL_DEPT_KEYS)


def department_allowed(level: int, key: str) -> bool:
    chosen = _LEVEL_DEPS.get(int(level), set())
    return key in chosen


def allowed_departments(level: int) -> Iterable[str]:
    return sorted(_LEVEL_DEPS.get(int(level), set()))

"""Evidence validation module â€” validates LLM-generated briefs against stored evidence.

Any number appearing in the brief must match the captured evidence (numeric tolerance 1e-6).
No "sales"/"revenue" claims when the only demand proxy is favorers. Any brief that fails the
validator is rejected; it never reaches the shortlist.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

_NUMBER_RE = re.compile(r"-?\d{1,3}(?:,\d{3})+|\-?\d+(?:\.\d+)?")
_SALES_WORDS = re.compile(r"\b(sales|selling|sold|revenue|profitable|profit|earnings|conversions?)\b", re.I)


@dataclass
class ValidationResult:
    ok: bool
    violations: list[str] = field(default_factory=list)
    brief: dict[str, Any] = field(default_factory=dict)


def _tolerance_eq(a: Any, b: Any, tol: float = 1e-6) -> bool:
    try:
        return abs(float(a) - float(b)) < tol
    except (TypeError, ValueError):
        return str(a).strip().lower() == str(b).strip().lower()


def _numbers_in_text(text: str) -> list[float]:
    out: list[float] = []
    for m in _NUMBER_RE.finditer(text):
        tok = m.group(0).replace(",", "")
        try:
            out.append(float(tok))
        except ValueError:
            continue
    return out


def _collect_evidence_numbers(evidence: dict) -> set[float]:
    nums: set[float] = set()
    def walk(node: Any):
        if node is None:
            return
        if isinstance(node, (int, float)):
            nums.add(float(node)); return
        if isinstance(node, str):
            try:
                nums.add(float(node))
                return
            except ValueError:
                return
        if isinstance(node, dict):
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for x in node:
                walk(x)
    walk(evidence)
    return nums


def validate_brief(brief_json: str | dict, evidence: dict) -> ValidationResult:
    """
    Args:
        brief_json: raw LLM output string (JSON) OR a dict.
        evidence:   the stored evidence dict for this opportunity.

    Rules:
      * cited_evidence[].value must equal stored evidence for the cited field
      * any number in why_this_one must exist in evidence or sub-scores
      * no "sales" / "revenue" claims if favorers are the only demand proxy
    """
    if isinstance(brief_json, str):
        text = brief_json.strip()
        try:
            brief = json.loads(text)
        except json.JSONDecodeError:
            try:
                brief = json.loads(_extract_json_object(text))
            except Exception:  # noqa: BLE001
                return ValidationResult(False, ["brief is not valid JSON"], {})
    else:
        brief = brief_json

    violations: list[str] = []

    # Required fields
    for key in ("concept", "title", "tags", "why_this_one", "cited_evidence"):
        if key not in brief:
            violations.append(f"missing required field: {key}")

    # Cited evidence â€” each {field, value} must equal stored evidence
    cited = brief.get("cited_evidence") or []
    if cited and not isinstance(cited, list):
        violations.append("cited_evidence must be a list of {field, value}")
    else:
        for i, c in enumerate(cited):
            if not isinstance(c, dict) or "field" not in c or "value" not in c:
                violations.append(f"cited_evidence[{i}] malformed (requires {field, value})")
                continue
            field, value = c["field"], c["value"]
            # look up the field loosely (top-level first, then nested under sub_scores / evidence keys)
            actual = _lookup_field(evidence, field)
            if actual is None:
                violations.append(f"cited field '{field}' not found in stored evidence")
                continue
            if not _tolerance_eq(value, actual):
                violations.append(f"cited field '{field}' value mismatch: claimed {value}, stored {actual}")

    # Numbers in why_this_one must live in evidence / sub-scores / cited values
    ev_nums = _collect_evidence_numbers(evidence)
    cited_nums = {float(c.get("value", 0)) for c in cited if isinstance(c, dict)}
    allowed = ev_nums | cited_nums
    why = str(brief.get("why_this_one", ""))
    for num in _numbers_in_text(why):
        if not any(abs(num - a) < 1e-6 for a in allowed):
            violations.append(f"number {num} in why_this_one not present in stored evidence")

    # No sales/revenue claims with favorers-only evidence
    ev_str = json.dumps(evidence, ensure_ascii=False).lower()
    has_favor = ("favorers" in ev_str) or ("favorite" in ev_str) or ("favor" in ev_str)
    has_sales_signal = ("sales" in ev_str) or ("sold" in ev_str) or ("revenue" in ev_str)
    if has_favor and not has_sales_signal:
        hits = _SALES_WORDS.findall(why + " " + str(brief.get("concept", "")))
        if hits:
            violations.append(
                f"claims sales/revenue ({sorted(set(hits))}) with favorers-only evidence â€” use 'favorites' instead")

    ok = not violations
    return ValidationResult(ok=ok, violations=violations, brief=brief)


def _extract_json_object(text: str) -> str:
    m = re.search(r"\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}", text, re.DOTALL)
    if m:
        return m.group(0)
    return text


def _lookup_field(obj: dict, field: str):
    if not isinstance(obj, dict):
        return None
    if field in obj:
        return obj[field]
    # nested: sub_scores, evidence dict-within-dict, and other flat buckets
    for key, value in obj.items():
        if isinstance(value, dict):
            r = _lookup_field(value, field)
            if r is not None:
                return r
    return None

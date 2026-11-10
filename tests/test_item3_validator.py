"""Item 3 — evidence validator: LLM explainer cannot invent numbers."""
import json

import pytest

from agents.validation import validate_brief


def _make_evidence(**kw) -> dict:
    base = {
        "avg_interest": 78,
        "trend": "rising",
        "total_listings": 312,
        "avg_favorers_top25": 124,
        "avg_price_top25": 6.99,
        "competition": "medium",
        "sub_scores": {"demand": 8.0, "competition": 5.0, "margin": 7.0, "feasibility": 8.0, "timing": 7.0},
        "score": 7.4,
    }
    base.update(kw)
    return base


def test_valid_brief_passes():
    ev = _make_evidence()
    brief = {
        "concept": "Dinosaur coloring + story hybrid",
        "title": "Dino Under the Desert Sky",
        "tags": ["dinosaur", "coloring", "stories"],
        "why_this_one": "Interest is rising to 78 with 124 favorites across 312 listings.",
        "cited_evidence": [
            {"field": "avg_interest", "value": 78},
            {"field": "avg_favorers_top25", "value": 124},
            {"field": "total_listings", "value": 312},
        ],
    }
    out = validate_brief(brief, ev)
    assert out.ok, out.violations


def test_changed_cited_number_fails():
    ev = _make_evidence()
    brief = {
        "concept": "x",
        "title": "x",
        "tags": [],
        "why_this_one": "Interest is rising to 99.",  # wrong on purpose
        "cited_evidence": [{"field": "avg_interest", "value": 99}],
    }
    out = validate_brief(brief, ev)
    assert not out.ok
    assert any("avg_interest" in v for v in out.violations)


def test_invented_number_fails():
    ev = _make_evidence()
    brief = {
        "concept": "x",
        "title": "x",
        "tags": [],
        "why_this_one": "It will sell 1,500,000 copies in week one.",
        "cited_evidence": [{"field": "avg_interest", "value": 78}],
    }
    out = validate_brief(brief, ev)
    assert not out.ok
    assert any("1500000" in v for v in out.violations)


def test_sales_wording_with_favorers_only_fails():
    ev = _make_evidence()
    brief = {
        "concept": "x",
        "title": "x",
        "tags": [],
        "why_this_one": "Proven seller with great revenue per book.",
        "cited_evidence": [{"field": "avg_interest", "value": 78}],
    }
    out = validate_brief(brief, ev)
    assert not out.ok
    assert any("sales/revenue" in v.lower() or "sales" in v.lower() for v in out.violations)


def test_malformed_json_rejected():
    out = validate_brief("this is not json", _make_evidence())
    assert not out.ok
    assert any("json" in v.lower() for v in out.violations)


def test_missing_field_rejected():
    brief = {"concept": "x"}
    out = validate_brief(brief, _make_evidence())
    assert not out.ok
    assert any("missing required field" in v for v in out.violations)

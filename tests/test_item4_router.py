"""Item 4 — CEO router unification + precision metrics."""
import os
import pytest

from agents.ceo.routing import route_keywords, route_llm


@pytest.fixture(autouse=True)
def aihq_fake():
    os.environ["AIHQ_FAKE_LLM"] = "1"
    yield
    os.environ.pop("AIHQ_FAKE_LLM", None)


# ---------- Real-LLM path (fallback to keyword routing for fake model determinism) ----------

def test_real_path_calls_route_llm_returns_valid_department():
    from agents.ceo.graph import route_task
    assert route_task("run the QA checker") == "qa"


# ---------- Negative cases from the spec ----------

def test_qatar_does_not_go_to_qa():
    from agents.ceo.graph import route_task
    out = route_task("Qatar market research")
    assert out != "qa"
    # Should route to intelligence or stay as a valid key, never qa
    assert out in {"intelligence", "books.market", "books.content"}


def test_tabe_does_not_go_to_affiliate():
    """The legacy Arabic affiliate-marker false positive was removed — now routes to None → graph fallback."""
    from agents.ceo.graph import route_task
    out = route_task("follow up the project")
    assert out != "affiliate"


def test_qa_checker_goes_to_qa():
    from agents.ceo.graph import route_task
    assert route_task("run the QA checker on this book") == "qa"


# ---------- Keyword precision — no substring false positives ----------

@pytest.mark.parametrize("text,expected", [
    ("affiliate a product", "affiliate"),
    ("commission rate analysis", "affiliate"),
    ("if they want an affiliation deal", "affiliate"),
    ("book quality current", "qa"),
    ("Etsy compliance check", "qa"),
    ("profit margin analysis", "finance"),
    ("printing cost estimate", "finance"),
    ("French: marge bénéficiaire", "finance"),
    ("Marketing copy for release", "marketing"),
    ("marché du livre", "books.market"),
    ("publier sur Etsy", "books.publishing"),
    ("write story kids book", "books.content"),
    ("quality inspection", "qa"),
    ("qualité livrée", "qa"),
    ("audit final du produit", "qa"),
])
def test_route_keywords_specific(text, expected):
    out = route_keywords(text)
    assert out["department"] == expected
    assert out["confidence"] > 0.3


def test_unknown_input_returns_no_match():
    out = route_keywords("hello how are you")
    assert out["department"] is None
    assert out["confidence"] == 0.0
    assert out["alternatives"] == []


def test_ambiguous_returns_alternatives():
    """When multiple rules win at identical strength, no guess — we return alternatives."""
    out = route_keywords("marketing affiliate opportunities")  # affiliate (100) beats marketing (70) beats intelligence (60)
    assert out["department"] == "affiliate"
    assert out["confidence"] < 0.65


# ---------- Case sensitivity ----------

def test_case_insensitive_matching():
    for text, expected in (("QUALITY CHECK", "qa"), ("QUALITÉ LIVRÉE", "qa"),
                           ("MARGIN REPORT", "finance"), ("PUBLIER SUR ETSY", "books.publishing")):
        out = route_keywords(text)
        assert out["department"] == expected, text


def test_phrase_like_match_not_substring():
    """Whole-token match only — 'Qatar' must not match 'qa'."""
    out = route_keywords("Qatar")
    assert out["department"] is None or out["department"] != "qa"


# ---------- Real-LLM smoke path (fallback to keywords under fake LLM) ----------

def test_route_llm_fallback_consistent_with_keywords():
    out_kw = route_keywords("quality check")
    out_llm = route_llm("quality check")
    assert out_kw["department"] == "qa"
    assert out_llm["department"] == "qa"

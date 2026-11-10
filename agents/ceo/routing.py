"""CEO routing — single source of truth for keyword / LLM routing.

Graph (agents/ceo/graph.py) and llm.py import from here — NO inline keyword lists.

Matching rules:
  * Latin: word-boundary matching (case-insensitive).
  * French: word-boundary matching (case-insensitive).

Unmatched input or equally-strong multiple matches → structured result with
confidence=0 and an `alternatives` list, never a guess.
"""
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Any

_WORD = re.compile(r"\b[A-Za-zÀ-ÖØ-öø-ÿ][\w'’-]*\b", re.UNICODE)


@dataclass(frozen=True)
class RouteRule:
    key: str                       # department key
    en: tuple[str, ...]
    fr: tuple[str, ...]
    phrases: tuple[str, ...] = ()  # multi-word phrases, matched verbatim (case-insensitive)
    specificity: int = 50


RULES: tuple[RouteRule, ...] = (
    RouteRule("affiliate",
              en=("affiliate", "commission", "association", "partner program"),
              fr=("affiliation", "affilier", "affilié", "commission", "programme d'affiliation"),
              specificity=100),

    RouteRule("qa",
              en=("qa", "quality", "inspection", "preflight", "compliance", "audit"),
              fr=("qa", "qualité", "contrôle", "conformité", "audit", "inspection"),
              specificity=90),

    RouteRule("finance",
              en=("finance", "fees", "margin", "profit", "price", "pricing", "cost"),
              fr=("financier", "marge", "bénéfice", "prix", "coût"),
              specificity=80),

    RouteRule("marketing",
              en=("marketing", "seo", "pinterest", "social media", "listing"),
              fr=("marketing", "seo", "pinterest", "réseau social"),
              specificity=70),

    RouteRule("intelligence",
              en=("intelligence", "opportunity", "niche", "trend", "research"),
              fr=("intelligence", "opportunité", "niche", "tendance"),
              specificity=60),

    RouteRule("books.market",
              en=("competitor", "bestseller", "niche"),
              fr=("concurrent", "niche", "marché"),
              specificity=50,
              phrases=("book market", "marché du livre", "marché livre")),

    RouteRule("books.publishing",
              en=("publish", "etsy", "kdp", "listing", "upload"),
              fr=("publier", "etsy", "kdp", "mettre en ligne"),
              specificity=40),

    RouteRule("books.content",
              en=("story", "content", "write", "author"),
              fr=("histoire", "écrit", "contenu", "roman"),
              specificity=30),

    RouteRule("product",
              en=("product", "candidate", "concept"),
              fr=("produit", "candidat", "concept"),
              specificity=20),
)

_RULES_BY_KEY = {r.key: r for r in RULES}


def _tokens_lat(text: str) -> list[str]:
    return _WORD.findall(text.lower())


def _find_matches(text: str) -> list[tuple[float, RouteRule, list[str]]]:
    """Return matched rules with (weight, rule, matched_keys), sorted by weight desc."""
    lower = text.lower()
    tokens = _tokens_lat(lower)

    matches: list[tuple[float, RouteRule, list[str]]] = []
    for rule in RULES:
        hits: list[str] = []
        for kw in rule.en:
            if kw.lower() in tokens:
                hits.append(kw)
        for kw in rule.fr:
            if kw.lower() in tokens:
                hits.append(kw)
        # phrase match (case-insensitive, word boundaries on both ends)
        for p in rule.phrases:
            if p and p.lower() in lower:
                if re.search(rf"\b{re.escape(p)}\b", lower):
                    hits.append(p)
        hits = sorted(set(h.lower() for h in hits))
        if not hits:
            continue
        weight = rule.specificity
        matches.append((weight, rule, hits))
    matches.sort(key=lambda x: (-x[0], -x[1].specificity))
    return matches


def route_keywords(task: str) -> dict[str, Any]:
    """Keyword-based routing — deterministic, no LLM."""
    matches = _find_matches(task)
    if not matches:
        return {"department": None, "confidence": 0.0, "alternatives": [], "matches": []}
    top_weight = matches[0][0]
    tied = [m for m in matches if m[0] == top_weight]
    # ambiguity: two rules won at identical strength → no guess
    if len(tied) > 1:
        return {
            "department": None,
            "confidence": top_weight / (top_weight + 1.0),
            "alternatives": [m[1].key for m in tied],
            "matches": [{"department": m[1].key, "weight": m[0], "hits": m[2]} for m in matches],
        }
    best = matches[0]
    # confidence scales with the gap to the runner-up
    rest_max = matches[1][0] if len(matches) > 1 else 0
    confidence = (best[0]) / (best[0] + rest_max + 1.0)
    return {
        "department": best[1].key,
        "confidence": round(confidence, 3),
        "alternatives": [m[1].key for m in matches[1:4]],
        "matches": [{"department": m[1].key, "weight": m[0], "hits": m[2]} for m in matches],
    }


def route_llm(task: str, valid_keys: list[str] | None = None):
    """LLM-constrained classification with keyword fallback."""
    import re as _re
    import json
    from agents.llm import get_chat_model
    from langchain_core.messages import HumanMessage, SystemMessage

    valid = valid_keys or [r.key for r in RULES]
    model = get_chat_model(temperature=0, max_tokens=60)
    sys = (
        "[ROLE:orchestrator]\n"
        "You route the founder's instruction to ONE department.\n"
        f"Valid departments: {valid}.\n"
        'Reply with a single JSON object: {"department": "<one-of-valid>"}.\n'
        "Prefer no guess when unsure: reply {\"department\":\"unknown\"}."
    )
    raw = model.invoke([SystemMessage(content=sys), HumanMessage(content=task)]).content
    try:
        picked = json.loads(_re.search(r"\{.*?\}", str(raw), _re.S).group(0))["department"]
    except Exception:  # noqa: BLE001
        picked = None
    if picked in valid:
        return {"department": picked, "confidence": 0.7, "alternatives": [], "matches": []}
    # fall back to keywords
    kw = route_keywords(task)
    if kw["department"]:
        kw["confidence"] = min(kw["confidence"], 0.65)   # keyword fallback beats LLM hallucination but below real LLM
    return kw

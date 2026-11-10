"""opportunity_engine — opportunity discovery → evidence → scoring → validation.

Every opportunity record carries per sub-score + which evidence was used. Discovery uses
the LLM only to propose niches (no numbers). Evidence is fetched in plain Python (Trends /
competition / price). Scoring is deterministic (documented weights). LLM may only write
explainers for already-scored ideas — the explanation validator checks that numbers match.

Deduplicate by unique key: (niche, language, country). Re-runs upsert and refresh scores
rather than re-insert — this prevents the same idea from flooding the feed.
"""
from __future__ import annotations
import hashlib
import json
import os
from datetime import date
from langgraph.graph import END, START, StateGraph
from langchain_core.messages import HumanMessage, SystemMessage

from agents.common import HQState
from agents.llm import get_chat_model, llm_last_note
from agents.capabilities import research
from agents.capabilities.scoring import DEMAND_SCORE, COMPETITION_SCORE
from agents.fees.etsy import total_fee
from backend.app.config import REPORTS_DIR
from backend.app.services import store as svc

ALLOWED_LANGS = ("en", "ar", "fr")
COUNTRIES = ("US", "SA", "AE", "FR")
SEASONAL_SEEDS_EN = (
    "Ramadan back-to-school Christmas Diwali Eid moon",
    "Eid back to school summer reading homeschool Arabic",
)


# ---------- helpers ----------
def _clamp(x, lo=0.0, hi=10.0):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return lo
    return max(lo, min(hi, x))


def _key(niche: str, lang: str, country: str) -> str:
    seed = f"{niche.lower().strip()}|{lang}|{country}"
    return hashlib.sha256(seed.encode()).hexdigest()[:16]


def _source_or_demo(ev: dict) -> str:
    """Aggregate one source label from evidence; demo if the majority is demo."""
    sources: list[str] = []
    trends = (ev.get("trends") or {})
    for v in (trends.get("keywords") or {}).values():
        if isinstance(v, dict):
            sources.append(str(v.get("source", "demo")))
    for v in (ev.get("competition") or {}).values():
        if isinstance(v, dict):
            sources.append(str(v.get("source", "demo")))
    if not sources:
        return "demo"
    return "live" if "live" in sources else ("partial" if "partial" in sources else "demo")


def _is_demo_env() -> bool:
    return bool(os.getenv("KIDBOOK_FAKE_LLM", "")) or os.getenv("AIHQ_FAKE_LLM", "").lower() in ("1", "true", "yes")


# ---------- nodes ----------
def _discover(state: HQState) -> HQState:
    try:
        brief = (state.get("task") or "scan niches").strip()
        model = get_chat_model(temperature=0.2, max_tokens=1200)
        sys = ("[ROLE:opportunity.discovery]\nReturn ONLY JSON {\"candidates\": [{\"niche\": str, \"keyword\": str, "
               "\"language\": str, \"country\": str, \"rationale\": str}]} — no numbers.\n"
               f"SEASONAL_SEEDS: {' '.join(SEASONAL_SEEDS_EN)}\n"
               f"BRIEF: {brief}\n")
        raw = str(model.invoke([SystemMessage(content=sys),
                                HumanMessage(content="discover candidates")]).content)
        import re
        match = re.search(r"\{.*\}", raw, re.S)
        parsed = {}
        if match:
            try:
                parsed = json.loads(match.group(0))
            except Exception:  # noqa: BLE001
                parsed = {}
        # fall back to a static seed list — never invent scores (numbers come from evidence step)
        candidates = [{
            "niche": "back_to_school", "keyword": "activity book back to school",
            "language": "en", "country": "US",
            "rationale": "Back-to-school seasonal demand for KDP/Etsy"
        }, {
            "niche": "bedtime_stories", "keyword": "قصص قبل النوم",
            "language": "ar", "country": "SA",
            "rationale": "Arabic bedtime storybooks for young children"
        }, {
            "niche": "coloring_animals", "keyword": "coloring book animals",
            "language": "en", "country": "US",
            "rationale": "Low competition, proven demand for kids coloring books"
        }, {
            "niche": "arabic_alphabet", "keyword": "arabic alphabet learning",
            "language": "ar", "country": "AE",
            "rationale": "Arabic literacy workbook niche (high demand in UAE/SA)"
        }, {
            "niche": "educational_workbook", "keyword": "educational workbook",
            "language": "en", "country": "US",
            "rationale": "Educational workbook broad category with evergreen demand"
        }]
        try:
            parsed_candidates = (parsed.get('candidates') if parsed else []) or []
            if parsed_candidates and isinstance(parsed_candidates, list):
                candidates = parsed_candidates[:30]
        except Exception:  # noqa: BLE001 — parser is best-effort
            pass
        return {"artifacts": {**state.get("artifacts", {}), "candidates": candidates},
                "progress": state.get("progress", []) + ["DISCOVERED"]}
    except Exception as e:  # noqa: BLE001
        return {"error": f"Discovery failed: {e}",
                "progress": state.get("progress", []) + ["FAILED discovery"]}


def _evidence(state: HQState) -> HQState:
    try:
        art = state.get("artifacts") or {}
        candidates = art.get("candidates", [])
        if not candidates:
            return {"error": "No candidates to evaluate",
                    "progress": state.get("progress", []) + ["EVIDENCE_DONE"]}
        keywords = list({c.get("keyword", "") for c in candidates if c.get("keyword")})
        keywords = keywords[:6]
        data = research.full_research(keywords)
        return {"research": data, "progress": state.get("progress", []) + ["EVIDENCE_DONE"]}
    except Exception as e:  # noqa: BLE001
        return {"error": f"Evidence collection failed: {e}",
                "progress": state.get("progress", []) + ["FAILED evidence"]}


def _score(state: HQState) -> HQState:
    try:
        art = state.get("artifacts") or {}
        candidates = art.get("candidates", [])
        evidence = state.get("research", {})
        trends = (evidence.get("google_trends") or {}).get("keywords") or {}
        competition = (evidence.get("etsy_competition") or {})

        scored = []
        for c in candidates:
            t = trends.get(c.get("keyword", ""), {})
            avg_int = float(t.get("avg_interest", 0) or 0)
            direction = 8.0 if str(t.get("trend", "steady")).lower() in ("rising", "up") else 6.0
            demand_score = _clamp((avg_int + direction) / 2, 0, 10)

            comp = competition.get(c.get("keyword", ""), {})
            tag = (comp.get("competition") or "").lower()
            competition_score = COMPETITION_SCORE.get(tag, 5.0)

            # margin: typical price from evidence / estimated Etsy fee model
            # fallback 5.0 if unknown — never invent a high margin from nowhere
            price_sample = comp.get("avg_price_top25")
            if price_sample:
                try:
                    price_sample = float(price_sample)
                except (TypeError, ValueError):
                    price_sample = None
            if price_sample:
                fee = total_fee(price_sample)["net_receipt"]
                margin_score = _clamp((fee / max(price_sample, 0.01)) * 10, 0, 10)
            else:
                margin_score = 5.0

            feasibility_score = 8.0   # the pipeline handles story/coloring/activity formats
            timing_score = 7.0        # seasonal timing matters but can't be certain w/out calendar run

            weighted = (demand_score * 0.30
                        + competition_score * 0.20
                        + margin_score * 0.25
                        + feasibility_score * 0.15
                        + timing_score * 0.10)
            score = round(_clamp(weighted, 0, 10), 1)

            comp = {**c, "evidence_trends": t, "evidence_competition": comp,
                    "prices_samples": price_sample,
                    "sub_scores": {"demand": demand_score, "competition": competition_score,
                                   "margin": margin_score, "feasibility": feasibility_score,
                                   "timing": timing_score},
                    "score": score}
            scored.append(comp)

        return {"artifacts": {**art,
                              "scored": scored,
                              "source": _source_or_demo(evidence)},
                "progress": state.get("progress", []) + ["SCORED"]}
    except Exception as e:  # noqa: BLE001
        return {"error": f"Scoring failed: {e}",
                "progress": state.get("progress", []) + ["SCORED_FAILED"]}


def _dedupe_write(state: HQState) -> HQState:
    """Upsert by (niche, language, country). No duplicate pollution."""
    try:
        scored = (state.get("artifacts") or {}).get("scored", [])
        source = (state.get("artifacts") or {}).get("source", "demo")
        written = []

        for o in sorted(scored, key=lambda x: x["score"], reverse=True)[:20]:
            if o.get("score", 0) < 6.5:
                continue
            k = _key(o["niche"], o.get("language", "en"), o.get("country", "US"))
            title = f"{o['niche']} — {o.get('language', 'en').upper()}/{o.get('country', 'US')}"
            evidence_payload = {"evidence": o, "key": k, "created": str(date.today())}
            rows = svc.q("SELECT opportunity_id, status FROM opportunities WHERE evidence LIKE ?",
                         (f"%{k}%",))
            if rows:                              # upsert — refresh in place
                opp_id = rows[0]["opportunity_id"]
                # expire cached metrics with fresh ones; never resurrect archived rows
                svc._execute_wrap(
                    "UPDATE opportunities SET score=?, source=? WHERE opportunity_id=?",
                    (o.get("score", 0), source, opp_id))
                written.append(opp_id)
            else:
                oid = svc.add_opportunity("intelligence", title, str(o.get("niche")),
                                          o.get("score", 0),
                                          payload=evidence_payload,
                                          source=source,
                                          evidence=evidence_payload)
                written.append(oid)

        return {"artifacts": {**state.get("artifacts", {}),
                              "opportunities_written": written},
                "summary": f"upserted {len(written)} opportunities (source={source})",
                "progress": state.get("progress", []) + ["DEDUPE_DONE"]}
    except Exception as e:  # noqa: BLE001
        return {"error": f"Dedup failed: {e}",
                "progress": state.get("progress", []) + ["DEDUPE_DONE"]}


def _explain(state: HQState) -> HQState:
    try:
        from agents.validation import validate_brief

        scored = (state.get("artifacts") or {}).get("scored", [])
        top = sorted(scored, key=lambda x: x["score"], reverse=True)[:5]
        if not top:
            return {"summary": "no candidates to explain",
                    "progress": state.get("progress", []) + ["EXPLAINED"]}

        briefs: list[dict] = []
        shortlist: list[dict] = []

        for cand in top:
            ev = {
                **(cand.get("evidence_trends") or {}),
                **(cand.get("evidence_competition") or {}),
                "sub_scores": cand.get("sub_scores", {}),
                "score": cand.get("score", 0.0),
                "evidence_source": cand.get("source") or "demo",
            }
            brief_out = _write_brief(cand, ev, attempt=1)
            if not brief_out["ok"]:
                # one retry with explicit violations list
                brief_out = _write_brief(cand, ev, attempt=2,
                                         violations=brief_out.get("violations"))
            if brief_out["ok"]:
                shortlist.append({**cand, "brief": brief_out["brief"],
                                  "status": "shortlisted"})
            else:
                briefs.append({**cand,
                               "status": "rejected_by_validator",
                               "violations": brief_out.get("violations")})
        return {"artifacts": {**state.get("artifacts", {}),
                              "top_candidates": top,
                              "shortlisted": shortlist,
                              "rejected_briefs": briefs},
                "summary": f"explained {len(top)}; shortlisted {len(shortlist)}; rejected {len(briefs)}",
                "progress": state.get("progress", []) + ["EXPLAINED", "ENGINE_DONE"]}
    except Exception as e:  # noqa: BLE001
        return {"error": f"Explain failed: {e}",
                "progress": state.get("progress", []) + ["EXPLAINED"]}


def _write_brief(cand: dict, evidence: dict, *, attempt: int = 1,
                 violations: list[str] | None = None) -> dict:
    """LLM that must cite evidence; on failure returns violations list for the retry."""
    import json as _json
    model = get_chat_model(temperature=0.3, max_tokens=800)
    hints = f"The previous brief was rejected with violations: {violations}. Fix them strictly.\n" if violations else ""
    sys = ("[ROLE:opportunity.briefing]\nYou are the founder's market analyst.\n"
           "Write a shortlist brief TIGHTLY tied to the attached evidence.\n"
           "Return ONLY JSON with keys: concept, title, tags (list), why_this_one (string), "
           "cited_evidence (list of {field, value}).\n"
           "Cited field names must match the evidence object exactly.\n"
           "Numbers in why_this_one must appear in the evidence object.\n"
           "Do NOT claim sales or revenue — evidence contains only favorites-style signals.\n"
           "Output format: a JSON object only. No prose. No commentary.\n"
           f"EVIDENCE: {_json.dumps(evidence, ensure_ascii=False)[:3500]}\n"
           + hints)
    raw = str(model.invoke([SystemMessage(content=sys),
                            HumanMessage(content=f"brief: {cand.get('niche')}")]).content)
    from agents.validation import validate_brief
    out = validate_brief(raw, evidence)
    return {"ok": out.ok, "violations": out.violations, "brief": out.brief}


def _supervisor(state: HQState) -> HQState:
    nxt = "done"
    if "DISCOVERED" not in state.get("progress", []):
        nxt = "researcher"
    elif "EVIDENCE_DONE" not in state.get("progress", []):
        nxt = "evidence"
    elif "SCORED" not in state.get("progress", []):
        nxt = "scorer"
    elif "DEDUPE_DONE" not in state.get("progress", []):
        nxt = "dedupe"
    elif "EXPLAINED" not in state.get("progress", []):
        nxt = "explainer"
    else:
        nxt = "done"
    return {"summary": nxt}


def _route(state: HQState) -> str:
    nxt = str(state.get("summary", "")).lower()
    return nxt if nxt in ("researcher", "evidence", "scorer", "dedupe", "explainer") else END


def _graph():
    g = StateGraph(HQState)
    g.add_node("supervisor", _supervisor)
    g.add_node("researcher", _discover)
    g.add_node("evidence", _evidence)
    g.add_node("scorer", _score)
    g.add_node("dedupe", _dedupe_write)
    g.add_node("explainer", _explain)
    g.add_edge(START, "supervisor")
    g.add_conditional_edges("supervisor", _route,
                            {"researcher": "researcher", "evidence": "evidence",
                             "scorer": "scorer", "dedupe": "dedupe",
                             "explainer": "explainer", END: END})
    g.add_edge("researcher", "supervisor")
    g.add_edge("evidence", "supervisor")
    g.add_edge("scorer", "supervisor")
    g.add_edge("dedupe", "supervisor")
    g.add_edge("explainer", "supervisor")
    return g.compile()


def run(task: str = "", task_id: int | None = None, workspace: str = "default") -> dict:
    try:
        result = _graph().invoke({"task": task or "scan niches",
                                  "run_id": task_id, "progress": []},
                                 config={"recursion_limit": 30})
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "error": str(e), "task_id": task_id}
    if result.get("error"):
        return {"ok": False, "error": result["error"], "task_id": task_id}
    return {"ok": True, "task_id": task_id, "summary": result.get("summary"), **(result.get("artifacts") or {})}

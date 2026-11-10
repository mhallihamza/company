"""مصنع النماذج + غلاف مرن + نموذج محوري حتمي للاختبارات.

المزود: LLM_PROVIDER = mistral | anthropic | openai | fake
الوضع التجريبي: AIHQ_FAKE_LLM=1 أو غياب المفاتيح.

أي فشل نموذج حي (تجاوز الحد، شبكة، مفتاح) يرتد فورًا للنموذج الحتمي،
وتُسجَّل الملاحظة في llm_last_note() بدل أن يتعطل القسم.
"""
from __future__ import annotations
import json
import os
import re
import threading
from typing import Any, List, Optional

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult

_note_lock = threading.Lock()
_last_note = "لم يُستخدم النموذج بعد"

# ---- token usage accounting (measured from provider metadata when available) ----
_usage_lock = threading.Lock()
_usage_accum: dict[str, Any] | None = None


def reset_usage_counter() -> None:
    global _usage_accum
    with _usage_lock:
        _usage_accum = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0,
                        "calls": 0, "measured_calls": 0}


def _read_usage_from_message(message: Any) -> dict[str, int] | None:
    """Extract (input_tokens, output_tokens, total_tokens) from a langchain AIMessage.

    langchain-core 0.3+ exposes message.usage_metadata; OpenAI providers mirror it in
    response_metadata['token_usage'] / ['usage']. Mistral exposes usage_metadata too.
    Returns None when the provider did not return usage data.
    """
    try:
        um = getattr(message, "usage_metadata", None)
        if isinstance(um, dict):
            inp = um.get("input_tokens", um.get("prompt_tokens"))
            out = um.get("output_tokens", um.get("completion_tokens"))
            tot = um.get("total_tokens")
            if tot is None and (inp is not None or out is not None):
                tot = int(inp or 0) + int(out or 0)
            if tot is not None:
                return {"input_tokens": int(inp or 0), "output_tokens": int(out or 0),
                        "total_tokens": int(tot)}
        md = getattr(message, "response_metadata", None) or {}
        if isinstance(md, dict):
            tu = md.get("token_usage") or md.get("usage") or md.get("usage_metadata")
            if isinstance(tu, dict):
                inp = tu.get("input_tokens", tu.get("prompt_tokens"))
                out = tu.get("output_tokens", tu.get("completion_tokens"))
                tot = tu.get("total_tokens")
                if tot is None and (inp is not None or out is not None):
                    tot = int(inp or 0) + int(out or 0)
                if tot is not None:
                    return {"input_tokens": int(inp or 0), "output_tokens": int(out or 0),
                            "total_tokens": int(tot)}
    except Exception:  # noqa: BLE001 — usage parsing must never crash generation
        return None
    return None


def _record_usage(result: "ChatResult | None") -> None:
    global _usage_accum
    totals = None
    if result is not None:
        try:
            message = result.generations[0].message
            totals = _read_usage_from_message(message)
        except Exception:  # noqa: BLE001
            totals = None
    with _usage_lock:
        acc = _usage_accum or {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0,
                               "calls": 0, "measured_calls": 0}
        acc["calls"] += 1
        if totals:
            acc["measured_calls"] += 1
            acc["input_tokens"] += totals["input_tokens"]
            acc["output_tokens"] += totals["output_tokens"]
            acc["total_tokens"] += totals["total_tokens"]
        _usage_accum = acc


def usage_snapshot() -> dict[str, Any] | None:
    """Snapshot of LLM calls made since reset_usage_counter().

    Returns None when no call was made at all.
    tokens are None when the provider returned no usage metadata (never a fake 0).
    """
    with _usage_lock:
        acc = dict(_usage_accum) if _usage_accum else None
    if not acc or acc["calls"] == 0:
        return None
    if acc["measured_calls"] == 0:
        return {"calls": acc["calls"], "measured_calls": 0,
                "input_tokens": None, "output_tokens": None, "total_tokens": None,
                "source": "unmeasured"}
    return {"calls": acc["calls"], "measured_calls": acc["measured_calls"],
            "input_tokens": acc["input_tokens"],
            "output_tokens": acc["output_tokens"],
            "total_tokens": acc["total_tokens"],
            "source": "measured"}


def llm_last_note() -> str:
    with _note_lock:
        return _last_note


def _note(msg: str) -> None:
    global _last_note
    with _note_lock:
        _last_note = msg


def fake_llm() -> BaseChatModel:
    return ScriptedChatModel()


# ---------------- النموذج الحتمي (للاختبار/العرض دون شبكة) ----------------
class ScriptedChatModel(BaseChatModel):
    """يجيب إجابات حتمية حسب دور الرسالة ([ROLE:name]) — لا شبكة ولا مفاتيح."""

    @property
    def _llm_type(self) -> str:
        return "scripted-fake"

    def _generate(self, messages: List[BaseMessage], stop: Optional[List[str]] = None,
                  run_manager: Any = None, **kwargs: Any) -> ChatResult:
        role = _role(messages)
        full = "\n".join(str(m.content) for m in messages)
        user = "\n".join(str(m.content) for m in messages
                         if not isinstance(m, SystemMessage))
        # المنسق يفهم مهمة المستخدم فقط؛ المشرفون يقرؤون كل السياق
        content = _ROLES.get(role, lambda t: t)(user if role == "orchestrator" else full)
        _record_usage(None)   # fake model: calls counted, but nothing is measured
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content))])


def _role(messages: List[BaseMessage]) -> str:
    for m in messages:
        if isinstance(m, SystemMessage):
            mch = re.search(r"\[ROLE:([^\]]+)\]", str(m.content))
            if mch:
                return mch.group(1).strip()
    return "general"


def _orch(text: str) -> str:
    """Fake-LLM orchestrator — delegates to the single routing source."""
    from agents.ceo.routing import route_keywords
    from agents.registry import get_department, DEPARTMENTS
    routed = route_keywords(text)
    dept = routed.get("department")
    if dept in DEPARTMENTS:
        return json.dumps({"domain": dept}, ensure_ascii=False)
    return json.dumps({"domain": "books.content"}, ensure_ascii=False)


def _story_json(text: str) -> str:
    idea = (re.search(r"IDEA:\s*(.+)", text) or re.search(r"اكتب\s+(.+)", text))
    title = idea.group(1).strip()[:60] if idea else "قصة عجيبة"
    return json.dumps({
        "title": f"قِصّة {title}",
        "character_sheet": "طفل صغير لطيف بملابس ملونة وأسلوب رسوم دافئة",
        "style": "soft watercolor children's book illustration, rounded shapes",
        "pages": [{"text": f"في الصفحة {i+1}: مغامرة صغيرة مليئة بابتسامة.",
                   "image_prompt": f"scene {i+1} for {title}, warm watercolor"}
                  for i in range(12)],
        "etsy": {"title": f"{title} — Arabic Kids Story Book",
                 "description": "قصة أطفال مصوّرة بالعربية بقيم إيجابية وازدراء.",
                 "tags": ["arabic kids book", "قصص أطفال", "arabic story"][:13]},
    }, ensure_ascii=False)


def _affiliate_scout(text: str) -> str:
    return json.dumps({
        "candidates": [
            {"product": "كتب أطفال قصص عربية بسعر مناسب", "est_price": 12.0,
             "commission": 8.0, "cookie_days": 14, "demand": "high", "competition": "medium",
             "program_hint": "Amazon Associates"},
            {"product": "Arbeitsheft Arabisch Alphabet",
             "est_price": 9.5, "commission": 10.0, "cookie_days": 30,
             "demand": "rising", "competition": "low",
             "program_hint": "impact.com"},
        ],
        "sources": "public trends; no private affiliate feeds",
    }, ensure_ascii=False)


_ROLES = {
    # التوجيه الرئيسي (CEO)
    "orchestrator": _orch,
    # مشرفو الأقسام
    "books.market.supervisor": lambda t: (
        '{"next":"researcher"}' if "RESEARCH_DONE" not in t
        else '{"next":"reporter"}' if "REPORT_DONE" not in t
        else '{"next":"done"}'),
    "books.content.supervisor": lambda t: (
        '{"next":"story_writer"}' if "STORY_DONE" not in t
        else '{"next":"illustrator"}' if "IMAGES_DONE" not in t
        else '{"next":"pdf_builder"}' if "PDF_DONE" not in t
        else '{"next":"done"}'),
    "books.publishing.supervisor": lambda t: (
        '{"next":"etsy_publisher"}' if "PUBLISH_DONE" not in t else '{"next":"done"}'),
    "intelligence.supervisor": lambda t: (
        '{"next":"researcher"}' if "SCAN_DONE" not in t
        else '{"next":"scorer"}' if "SCORE_DONE" not in t
        else '{"next":"done"}'),
    "affiliate.supervisor": lambda t: (
        '{"next":"scout"}' if "RESEARCH_DONE" not in t
        else '{"next":"analyst"}' if "ANALYSIS_DONE" not in t
        else '{"next":"done"}'),
    "marketing.supervisor": lambda t: (
        '{"next":"copywriter"}' if "COPY_DONE" not in t else '{"next":"done"}'),
    "finance.supervisor": lambda t: (
        '{"next":"calculator"}' if "CALC_DONE" not in t else '{"next":"done"}'),
    "qa.supervisor": lambda t: (
        '{"next":"checker"}' if "CHECKS_DONE" not in t else '{"next":"done"}'),
    "product.supervisor": lambda t: (
        '{"next":"validator"}' if "VALIDATED" not in t else '{"next":"done"}'),
    # الوكلاء
    "story_writer": _story_json,
    "report_writer": lambda t: (
        "### تقرير اتجاهات كتب الأطفال (وضع تجريبي)\n\n"
        "- تلوين حيوانات 3-6: طلب صاعد، منافسة متوسطة — درجة 7.2/10\n"
        "- أبجديتي العربية المصوّرة: طلب ثابت، منافسة منخفضة — درجة 7.0/10\n"
        "- قصص قبل النوم: طلب عالي، منافسة عالية — درجة 6.0/10\n\n"
        "تنبيه: تحليل تجريبي؛ للإنتاج الحقيقي تحتاج مفاتيح Google Trends/Etsy."),
    "intelligence.scorer": lambda t: json.dumps({
        "opportunities": [
            {"title": "DEMO — Coloring animals (test scaffold)", "niche": "coloring", "score": 7.5},
            {"title": "DEMO — Arabic alphabet workbook (test scaffold)", "niche": "educational", "score": 7.0},
        ],
        "notes": "Demo engine (AIHQ_FAKE_LLM=1) — tagged source=demo in the DB, never promoted to live. Set ETSY keys for live evidence.",
    }, ensure_ascii=False),
    "affiliate.scout": _affiliate_scout,
    "marketing.copywriter": lambda t: json.dumps({
        "seo_keywords": ["arabic kids book", "arabic bedtime story", "كتب أطفال عربية"],
        "description": "قصص مصوّرة بالعربية للأطفال من 3-6 سنوات بقيم إيجابية.",
        "pinterest": ["بوستر القصة ومخططها", "وصية الآباء بالقراءة قبل النوم"],
        "calendar": ["السبت: نشر بوستر", "الأربعاء: ملخص القصة"],
        "disclaimer": "اقتراح محتوى يحتاج موافقتك قبل النشر",
    }, ensure_ascii=False),
}


# ---------------- الغلاف المرن ----------------
class ResilientChatModel(BaseChatModel):
    """نموذج حي يرتجل للنموذج الحتمي عند أي عطل — بدون أن يتعطل قسم كامل."""

    primary: Any
    fallback: Any

    @property
    def _llm_type(self) -> str:
        try:
            return f"resilient({self.primary._llm_type})"  # noqa: SLF001
        except Exception:  # noqa: BLE001
            return "resilient"

    def _generate(self, messages: List[BaseMessage], stop: Optional[List[str]] = None,
                  run_manager: Any = None, **kwargs: Any) -> ChatResult:
        try:
            result = self.primary._generate(messages, stop=stop, run_manager=run_manager, **kwargs)
            _note("live: real model used")
            _record_usage(result)
            return result
        except Exception as e:  # noqa: BLE001
            _note(f"live model failed ({str(e)[:120]}) → deterministic fallback")
            # fallback (scripted) counts itself as an unmeasured call
            return self.fallback._generate(messages, stop=stop, run_manager=run_manager, **kwargs)


def get_chat_model(temperature: float = 0.4, max_tokens: int = 4000) -> BaseChatModel:
    if os.getenv("AIHQ_FAKE_LLM", "").lower() in ("1", "true", "yes"):
        return fake_llm()

    provider = os.getenv("LLM_PROVIDER", "mistral").lower()
    model = os.getenv("LLM_MODEL", "")
    try:
        if provider == "mistral":
            if not os.getenv("MISTRAL_API_KEY"):
                return fake_llm()
            from langchain_mistralai import ChatMistralAI
            return ResilientChatModel(
                primary=ChatMistralAI(model=model or "mistral-small-latest",
                                      temperature=temperature, max_tokens=max_tokens),
                fallback=fake_llm())
        if provider == "anthropic":
            if not os.getenv("ANTHROPIC_API_KEY"):
                return fake_llm()
            from langchain_anthropic import ChatAnthropic
            return ResilientChatModel(
                primary=ChatAnthropic(model=model or "claude-sonnet-4-5",
                                      temperature=temperature, max_tokens=max_tokens),
                fallback=fake_llm())
        if provider == "openai":
            if not os.getenv("OPENAI_API_KEY"):
                return fake_llm()
            from langchain_openai import ChatOpenAI
            return ResilientChatModel(
                primary=ChatOpenAI(model=model or "gpt-4o-mini",
                                   temperature=temperature, max_tokens=max_tokens),
                fallback=fake_llm())
    except ImportError:
        _note(f"المزود {provider} غير مثبت → النمط الحتمي")
        return fake_llm()

    _note(f"مزود غير معروف {provider} → النمط الحتمي")
    return fake_llm()


def mode_label() -> str:
    if os.getenv("AIHQ_FAKE_LLM", "").lower() in ("1", "true", "yes"):
        return "demo (no live model)"
    return f"live:{os.getenv('LLM_PROVIDER', 'mistral')}"

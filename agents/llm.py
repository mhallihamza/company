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
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content))])


def _role(messages: List[BaseMessage]) -> str:
    for m in messages:
        if isinstance(m, SystemMessage):
            mch = re.search(r"\[ROLE:([^\]]+)\]", str(m.content))
            if mch:
                return mch.group(1).strip()
    return "general"


def _orch(text: str) -> str:
    low = text.lower()
    rules = [
        ("affiliate", ("affiliate", "عمولة", "تابع", "commission")),
        ("qa", ("qa", "جودة", "فحص", "امتثال", "preflight")),
        ("finance", ("finance", "رسوم", "هامش", "ربح", "ربحية", "عائد", "تكلفة",
                     "margin", "profit", "usd", "price", "pricing", "سعر")),
        ("marketing", ("marketing", "تسويق", "seo", "pinterest", "كلمات مفتاحية")),
        ("intelligence", ("intelligence", "فرصة", "فرص", "opportunity", "مسح")),
        ("books.market", ("trend", "السوق", "سوق", "تحليل سوق", "market", "منافس")),
        ("books.publishing", ("publish", "انشر", "نشر", "ارفع", "رفع", "etsy", "kdp")),
    ]
    for domain, words in rules:
        if any(w in low for w in words):
            return json.dumps({"domain": domain}, ensure_ascii=False)
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
            {"title": "كتاب تلوين حيوانات للأطفال 3-6", "niche": "coloring", "score": 7.5},
            {"title": "أبجديتي العربية الأولى", "niche": "educational", "score": 7.0},
        ],
        "notes": "درجات مبنية على إشارات مختلقة للوضع التجريبي",
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
            return result
        except Exception as e:  # noqa: BLE001
            _note(f"live model failed ({str(e)[:120]}) → deterministic fallback")
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

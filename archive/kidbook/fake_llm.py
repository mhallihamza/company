"""نموذج لغوي وهمي حتمي (Scripted Fake) للاختبار دون اتصال ودون مفاتيح.

يقرأ من SystemMessage الوسم [ROLE:اسم] ويقرر الاستجابة بناءً على الرسائل
الموجودة في المحادثة، فيحاكي بدقة قرارات المشرف/الكاتب التي يؤديها
النموذج الحقيقي — لكن بشكل ثابت وقابل للاختبار في كل مرة.
"""
from __future__ import annotations
import json
import re
from typing import Any, List, Optional

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult


def _role(messages: List[BaseMessage]) -> str:
    for m in messages:
        if isinstance(m, SystemMessage):
            match = re.search(r"\[ROLE:([\w.\-]+)\]", str(m.content))
            if match:
                return match.group(1)
    return "generic"


def _all_text(messages: List[BaseMessage]) -> str:
    return "\n".join(str(m.content) for m in messages)


def _story_json(idea: str, pages: int) -> str:
    """قصة آمنة للأطفال تتضمن الفكرة — ثابتة البنية حتى تنجح الاختبارات دائماً."""
    idea_clean = idea.strip().rstrip(".")
    page_texts = []
    for i in range(pages):
        tag = i + 1
        page_texts.append({
            "text": f"كان يا ما كان، في قرية جميلة، صديقٌ صغير يتعلّم عن «{idea_clean}». وهذه هي الصفحة رقم {tag} من مغامرته.",
            "image_prompt": f"a round friendly sun smiling over green hills with a tiny rabbit looking at a picture about {idea_clean}, page {tag}",
        })
    data = {
        "title": f"حكاية {idea_clean[:38]}",
        "character_sheet": "أرنب صغير بني اللون، معطف أزرق سماوي بأزرار صفراء، عينان سوداوتان مستديرتان، أذن واحدة ملتوية إلى الأمام، ذيل أبيض مروحي الشكل، لا يتغير شكله في أي صفحة",
        "style": "soft watercolor illustration, warm bright colors, gentle rounded shapes, storybook style",
        "pages": page_texts,
        "etsy": {
            "title": f"قصص أطفال بالعربية — {idea_clean[:60]}",
            "description": f"كتاب قصص مصوّر للأطفال من 3 إلى 6 سنوات عن «{idea_clean}». قصة دافئة بقيم إيجابية، مناسبة للمطبعة الرقمية والمكتبات المدرسية.",
            "tags": ["قصص أطفال", "كتاب عربي", "قبل النوم", "children book", "arabic kids",
                     "قصة مصورة", "تعليم القراءة", "كتاب رقمي", "PDF تحميل", "هدايا أطفال",
                     "أنشطة عائلية", "قصص ما قبل المدرسة", "قصص دافئة"],
        },
    }
    return json.dumps(data, ensure_ascii=False)


def _report(research_blob: str) -> str:
    return (
        "### تقرير السوق (وضع تجريبي)\n\n"
        "**البيانات المستخدمة:** نتائج أدوات Google Trends وEtsy المرفقة في السياق.\n\n"
        f"```\n{research_blob[:1200]}\n```\n\n"
        "#### التصنيف وفق الفرصة\n"
        "| النيش | الإشارة | الدرجة |\n|---|---|---|\n"
        "| قصص قبل النوم (عربي) | طلب عالٍ وبيانات الاستعلام مرفقة | 6/10 |\n"
        "| كتاب تلوين حيوانات | طلب منخفض لكنه صاعد | 7/10 |\n"
        "| تعلم الأبجدية | صاعد تدريجياً | 6/10 |\n\n"
        "#### أفضل 3 أفكار في النيش الأعلى\n"
        "1. «أرنوبة تتعلم المشاركة» — 3-6 سنوات — شخصية ثابتة تُبني ألفة مع الطفل\n"
        "2. «ليالي الزعتر» — قصص قصيرة قبل النوم بالعربية الفصحى المبسطة\n"
        "3. «أبجديتي الأولى» — كتاب تفاعلي للقراءة المبكرة\n\n"
        "**ملاحظة:** هذه معاينة بدون اتصال بالنماذج اللغوية؛ شغّل بمفاتيح Mistral/Anthropic للحصول على تحليل عميق.\n"
    )


def _decide(role: str, full_text: str, user_text: str) -> str:
    text = _DECISIONS.get(role)
    if not text:
        return json.dumps({"result": "ok"}, ensure_ascii=False)
    # المنسق يقرأ نص المستخدم فقط (كلمات المهمة)، والمشرفون يقرؤون كل السياق
    source = user_text if role == "orchestrator" else full_text
    return text(source)


_ORCH_RULES = [
    ("affiliate", ("affiliate", "عمولة", "تابع", "commission", "associate")),
    ("qa", ("qa", "جودة", "فحص", "امتثال", "preflight", "تحقق")),
    ("finance", ("finance", "رسوم", "هامش", "عائد", "تكلفة", "أرباح", "ربح")),
    ("marketing", ("marketing", "تسويق", "seo", "pinterest", "كلمات مفتاحية", "وصف المنتج")),
    ("intelligence", ("intelligence", "فرصة", "فرص", "opportunity", "أفكار أعمال", "مسح")),
    ("kids_books.market", ("trend", "السوق", "سوق", "تحليل", "market", "منافس", "niche")),
    ("kids_books.publishing", ("publish", "انشر", "نشر", "رفع", "etsy", "kdp")),
]


def _orch_route(text: str) -> str:
    low = text.lower()
    for domain, kws in _ORCH_RULES:
        if any(k in low for k in kws):
            return domain
    return "kids_books.content"


_DECISIONS = {
    "orchestrator": lambda text: json.dumps(
        {"domain": _orch_route(text)},
        ensure_ascii=False),

    "market.supervisor": lambda text: (
        json.dumps({"next": "researcher"}) if "RESEARCH_DONE" not in text
        else json.dumps({"next": "reporter"}) if "REPORT_DONE" not in text
        else json.dumps({"next": "done"})),

    "content.supervisor": lambda text: (
        json.dumps({"next": "story_writer"}) if "STORY_DONE" not in text
        else json.dumps({"next": "illustrator"}) if "IMAGES_DONE" not in text
        else json.dumps({"next": "pdf_builder"}) if "PDF_DONE" not in text
        else json.dumps({"next": "done"})),

    "publishing.supervisor": lambda text: (
        json.dumps({"next": "etsy_publisher"}) if "PUBLISH_DONE" not in text
        else json.dumps({"next": "done"})),

    "report_writer": lambda text: _report(
        re.search(r"RESEARCH_DATA:\s*(\{.*)", text, re.S).group(1)
        if re.search(r"RESEARCH_DATA:\s*(\{.*)", text, re.S) else text),

    "story_writer": lambda text: _story_json(
        re.search(r"IDEA:\s*(.+)", text).group(1).strip()
        if re.search(r"IDEA:\s*(.+)", text) else "حكاية لطيفة",
        int(re.search(r"PAGES:\s*(\d+)", text).group(1))
        if re.search(r"PAGES:\s*(\d+)", text) else 12),

    # ---- أقسام AI Business HQ الجديدة ----
    "affiliate.supervisor": lambda text: (
        json.dumps({"next": "researcher"}) if "RESEARCH_DONE" not in text
        else json.dumps({"next": "analyst"}) if "ANALYSIS_DONE" not in text
        else json.dumps({"next": "done"})),
    "affiliate.scout": lambda text: json.dumps({
        "candidates": [
            {"product": "Dinosaur activity books for kids (4-7)", "commission": 8, "cookie_days": 14,
             "demand": "high", "competition": "medium"},
            {"product": "Arabic kids alphabet workbooks", "commission": 10, "cookie_days": 30,
             "demand": "rising", "competition": "low"},
            {"product": "Islamic bedtime story boxed sets", "commission": 6, "cookie_days": 7,
             "demand": "steady", "competition": "high"},
        ], "sources": "public web (trends + marketplace scans); no private affiliate feeds"},
        ensure_ascii=False),
    "intelligence.supervisor": lambda text: (
        json.dumps({"next": "researcher"}) if "SCAN_DONE" not in text
        else json.dumps({"next": "scorer"}) if "SCORE_DONE" not in text
        else json.dumps({"next": "done"})),
    "intelligence.scorer": lambda text: json.dumps({
        "opportunities": [
            {"title": "كتاب تلوين حيوانات للأطفال 3-6", "score": 7.5, "niche": "coloring"},
            {"title": "أبجديتي العربية الأولى مع صوتيات", "score": 7.0, "niche": "educational"},
            {"title": "قصص قبل النوم مغامرات الأرنب نور", "score": 6.5, "niche": "bedtime"},
        ], "notes": "scores blend trends + competition; not sales guarantees"},
        ensure_ascii=False),
    "marketing.supervisor": lambda text: (
        json.dumps({"next": "copywriter"}) if "COPY_DONE" not in text
        else json.dumps({"next": "done"})),
    "marketing.copywriter": lambda text: json.dumps({
        "seo_keywords": ["arabic kids book", "arabic story book for children", "قصص أطفال",
                          "كتب أطفال عربية", "arabic bedtime story"],
        "description": "كتاب قصص مصوّر بالعربية للأطفال من 3 إلى 6 سنوات — قيم إيجابية وشخصية ثابتة وقصص قصيرة قبل النوم. مناسب للطباعة وKDP وEtsy.",
        "pinterest": ["بوستر: «أرنوبة تتعلم المشاركة» — ثبات الشخصية عبر الصفحات",
                      "دليل الآباء: كيف تقرأ 10 دقائق قبل النوم كل ليلة"],
        "calendar": ["السبت نشر بوستر القصة", "الاثنين مراجعات حقيقية (بعد تفعيلها)",
                      "الأربعاء هدية تلوين مجانية"],
        "disclaimer": "اقتراح محتوى فقط؛ لا أرقام مبيعات مفبركة ولا وعود بدخل."},
        ensure_ascii=False),
    "finance.supervisor": lambda text: (
        json.dumps({"next": "calculator"}) if "CALC_DONE" not in text
        else json.dumps({"next": "done"})),
    "finance.calculator": lambda text: json.dumps({
        "etsy": {"listing_fee": 0.20, "transaction_fee_pct": 6.5, "payment_processing_pct": 3.0},
        "kdp": {"paperback_60_pct_royalty_min": 0.60, "delivery_fee_per_mb": 0.15},
        "example_unit_economics": {"price": 4.99, "platform_fees_units": 0.55, "print_units": 0.0,
                                    "margin_before_ads_units": 4.44, "note": "digital = no print cost"},
        "assumptions": "USD; print cost applies only to paperback, not KDP eBook/Etsy digital download"},
        ensure_ascii=False),
    "qa.supervisor": lambda text: (
        json.dumps({"next": "checker"}) if "CHECKS_DONE" not in text
        else json.dumps({"next": "done"})),
}


class ScriptedChatModel(BaseChatModel):
    """يحاكي النموذج الحقيقي في كل دور داخل الرسوم البيانية."""

    def _generate(
        self,
        messages: List[BaseMessage],
        stop: Optional[List[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        role = _role(messages)
        full = _all_text(messages)
        user = "\n".join(str(m.content) for m in messages if not isinstance(m, SystemMessage))
        content = _decide(role, full, user)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content))])

    @property
    def _llm_type(self) -> str:
        return "scripted-fake"

"""AI Business HQ — لوحة قيادة «شركة» إدارة أعمال بقسم/CEO (النسخة 2).
شغّل: .\\.venv\\Scripts\\streamlit run app.py
كل ما يظهر للمؤسس بالعربية، وكل تشغيلة تُسجَّل في قاعدة البيانات.
"""
import json
import os
from datetime import date
from pathlib import Path

import streamlit as st

from kidbook import config, engine   # noqa: E402
from kidbook.db import get_store     # noqa: E402
from kidbook.domains import DOMAIN_REGISTRY, list_domains  # noqa: E402
from kidbook.llm import llm_last_note, mode_label  # noqa: E402

# ---------- ثابتات الواجهة ----------
AR_STATUS = {
    "story_draft": ("📝 مسودة نصية", "orange"),
    "images_ready": ("🎨 صور جاهزة", "blue"),
    "pdf_ready": ("📄 PDF جاهز", "blue"),
    "draft_etsy": ("🪟 مسودة Etsy", "violet"),
    "published": ("🚀 منشور", "green"),
    "pending": ("⏳ بانتظار قرارك", "orange"),
    "approved": ("✅ معتمد", "green"),
    "rejected": ("❌ مرفوض", "red"),
    "new": ("🆕 جديدة", "blue"),
    "watching": ("👀 تحت المراقبة", "gray"),
    "pursuing": ("🎯 نتابعها", "green"),
    "archived": ("🗄️ مؤرشف", "gray"),
    "success": ("✅", "green"), "failed": ("❌", "red"), "running": ("⏱ قيد التنفيذ", "blue"),
}


def tag(status: str) -> str:
    label, color = AR_STATUS.get(status, (status, "gray"))
    return f":{color}-background[{label}]"


def safe(fn, *a, **kw):
    try:
        return fn(*a, **kw)
    except Exception as e:  # noqa: BLE001
        st.error(f"خطأ: {e}")
        return None


def show_result(out: dict, title: str = "نتيجة التشغيلة"):
    if not isinstance(out, dict):
        st.error("لا نتيجة")
        return
    if out.get("ok"):
        st.success(out.get("summary") or "تم")
    else:
        st.error(out.get("error") or "فشل")
    with st.expander(f"🔧 {title} — تفاصيل (JSON)"):
        st.json(out, expanded=False)


st.set_page_config(page_title="AI Business HQ", page_icon="🏢",
                   layout="wide", initial_sidebar_state="expanded")
st.markdown(
    """<style>.stApp{direction:rtl;text-align:right} .stMetric{text-align:right}</style>""",
    unsafe_allow_html=True)

# ---------- الشريط الجانبي ----------
with st.sidebar:
    st.markdown("## 🏢 AI Business HQ")
    st.caption(f"اليوم: {date.today().isoformat()} · "
               f"قاعدة البيانات: {safe(get_store().backend_label, '؟')} · "
               f"النموذج: {mode_label()}")
    st.divider()
    st.markdown("### الأقسام المسجلة")
    for spec in list_domains():
        pol = {"none": "حر", "story_review": "مراجعة القصة", "human_required": "يجب موافقتك",
               "content_gate": "قبل النشر", "gate": "بوابة فحص"}.get(spec.approval_policy,
                                                                     spec.approval_policy)
        st.markdown(f"**{spec.title}**\n\n:key: {spec.key} · الصلاحية: {pol}")
    st.divider()
    st.markdown("### 🧭 مهام سريعة")
    quick = st.radio("اختر مهمة جاهزة",
                     ["— اختر —", "تقرير السوق", "مسح الفرص", "بحث عمولة",
                      "حزمة تسويق", "تحليل مالي"],
                     label_visibility="collapsed")
    if st.button("▶ نفّذ المهمة المختارة"):
        mapping = {"تقرير السوق": engine.analyze_market,
                   "مسح الفرص": engine.run_intelligence,
                   "بحث عمولة": engine.run_affiliate,
                   "حزمة تسويق": engine.run_marketing,
                   "تحليل مالي": engine.run_finance}
        if quick in mapping:
            with st.spinner("القسم يشتغل..."):
                show_result(mapping[quick](), quick)
        else:
            st.warning("اختر مهمة أولاً")

store = get_store()
stats = safe(store.stats, {}) or {}
tabs = st.tabs(["🏠 القيادة", "🚀 الأقسام", "📚 الكتب", "💰 الفرص",
                "✅ الموافقات", "📈 التقارير", "🧱 البنية", "⚙️ الإعدادات"])

# =====================================================================
# 1) القيادة — الموجز + قناة CEO
# =====================================================================
with tabs[0]:
    st.title("🏢 AI Business HQ")
    st.caption("نظام تشغيل أعمال بالذكاء الاصطناعي — أنت المؤسس، والـ CEO يدير الأقسام")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("📚 كتب جاهزة للنشر", stats.get("books_pdf_ready", 0))
    c2.metric("🚀 منشورة", stats.get("books_published", 0))
    c3.metric("💰 فرص مسجلة", stats.get("opportunities", 0))
    c4.metric("✅ موافقات معلقة", stats.get("approvals_pending", 0))
    c5.metric("🗂 عدد التشغيلات", stats.get("runs", 0))

    st.divider()
    st.subheader("🤖 تحدث إلى CEO الشركة")
    task = st.text_area("ماذا تريد؟ CEO يفهم هدفك، يوجه المهمة إلى القسم المناسب، ويعود إليك بالنتيجة",
                        placeholder="مثال: حلل السوق هذا الأسبوع · ابحث عن منتجات عمولة لكتب الأطفال · "
                                    "احسب هامش كتاب سعره 9.5 دولار 24 صفحة",
                        label_visibility="collapsed")
    if st.button("🚀 أرسل إلى CEO"):
        if task.strip():
            with st.spinner("CEO يوجه المهمة إلى القسم المناسب..."):
                out = safe(engine.run_task, task.strip()) or {"ok": False, "error": "لا نتيجة"}
            st.markdown(f"**🧭 CEO وجه المهمة إلى:** `{out.get('domain', '?')}`")
            show_result(out, "ربط CEO")
        else:
            st.warning("اكتب المهمة أولاً")
    st.info(f"🩺 حالة النموذج: {llm_last_note()}")

    st.subheader("🕒 آخر التشغيلات")
    for run in reversed((safe(store.list_runs, 12) or [])):
        st.markdown(f"- `{run.get('id')}` **{run.get('run_type')}** → `{run.get('domain')}` "
                    f"{tag(run.get('status', ''))} · {run.get('started_at', '')}")

# =====================================================================
# 2) الأقسام (التشغيل اليدوي لكل قسم)
# =====================================================================
with tabs[1]:
    st.title("🚀 أقسام الشركة الذكية")
    st.caption("كل قسم = مشرف (supervisor) + وكلاؤ متحكمون. اضغط تنفيذ لتراه يشتغل فعلاً")

    # --- ذكاء السوق ---
    with st.expander("🧠 ذكاء السوق — مسح الفرص وتسجيلها", expanded=False):
        brief_i = st.text_input("تكليف اختياري (سلة النيشات افتراضية)", key="int_brief")
        if st.button("▶ نفّذ مسح الفرص", key="int_run"):
            with st.spinner("الباحث يكتشف، المُسعّر يرتب..."):
                show_result(engine.run_intelligence(brief_i), "ذكاء السوق")

    # --- التسويق بالعمولة ---
    with st.expander("🧲 التسويق بالعمولة — اكتشاف منتجات وتقييم عمولات", expanded=False):
        af = st.text_input("نيش (أو اتركه فارغاً للاقتراح العام)")
        if st.button("▶ نفّذ بحث العمولة", key="af_run"):
            with st.spinner("Scout يجمع المرشحين، ثم Analyst يحسب الوحدة الاقتصادية..."):
                show_result(engine.run_affiliate(af), "بحث التسويق بالعمولة")

    # --- التسويق ---
    with st.expander("📣 التسويق وSEO — حزمة محتوى كاملة", expanded=False):
        mk = st.text_input("وصف المنتج/الكتاب التي تحتاج حزمة تسويق",
                           placeholder="كتاب قصص عربية للأطفال 3-6")
        if st.button("▶ نفّذ حزمة التسويق", key="mk_run"):
            if mk.strip():
                with st.spinner("copywriter يجهز كلمات SEO وأفكار Pinterest وتقويم الترويج..."):
                    show_result(engine.run_marketing(mk.strip()), "التسويق")
            else:
                st.warning("اكتب الوصف أولاً")

    # --- المالية ---
    with st.expander("💵 المالية والهوامش — رسوم Etsy/KDP وحساب صافي", expanded=False):
        fin = st.text_input("المطالبة (السعر/الصفحات بالكلمات أو أرقام)",
                            placeholder="كتاب 9.5 دولار 24 صفحة")
        if st.button("▶ نفّذ التحليل المالي", key="fin_run"):
            with st.spinner("حاسبة Python — بلا نموذج لغوي في الأرقام"):
                show_result(engine.run_finance(fin), "المالية")

    # --- الجودة ---
    with st.expander("🛡 الجودة والامتثال — بوابة فحص قبل النشر", expanded=False):
        slugs = [p.name for p in config.BOOKS_DIR.iterdir() if p.is_dir()] \
            if config.BOOKS_DIR.exists() else []
        qa_slug = st.selectbox("اختر كتاباً للفحص", slugs or ["(لا يوجد كتب)"])
        if st.button("▶ نفّذ فحص الجودة", key="qa_run") and qa_slug != "(لا يوجد كتب)":
            with st.spinner("المدقق يفحص سلامة PDF والصور وحدود حقول Etsy..."):
                show_result(engine.run_qa(qa_slug), "الجودة")

    # --- سوبريسور الكتب ---
    with st.expander("📖 قسم الكتب — السوق/المحتوى/النشر", expanded=False):
        b1, b2, b3 = st.columns(3)
        if b1.button("📊 تقرير السوق"):
            with st.spinner(""):
                show_result(engine.analyze_market(), "تقرير السوق")
        idea_b = b2.text_input("فكرة قصة جديدة", key="idea_b",
                               placeholder="أرنوبة تتعلم المشاركة")
        if b2.button("✍️ اكتب قصة") and idea_b.strip():
            with st.spinner("الكاتب يعمل — ستوقف للمراجعة بعد إخراج story.json"):
                show_result(engine.create_story(idea_b.strip()), "قصة")
        slb = b3.selectbox("بناء PDF لكتاب", slugs or ["(لا يوجد)"], key="build_slug")
        if b3.button("📐 ابنِ الكتاب") and slb != "(لا يوجد)":
            with st.spinner("رسم + PDF..."):
                show_result(engine.build_book(slb), "بناء")

# =====================================================================
# 3) الكتب
# =====================================================================
with tabs[2]:
    st.title("📚 مكتبة الكتب")
    books = safe(store.list_books, []) or []
    if books:
        for b in books:
            with st.expander(f"{tag(b['status'])} **{b['title'] or b['slug']}** — `{b['slug']}`",
                             expanded=False):
                st.caption(b.get("idea", ""))
                c1, c2, c3 = st.columns([1, 2, 1])
                c1.write(tag(b["status"]))
                if b.get("pdf_path") and Path(b["pdf_path"]).exists():
                    c2.markdown(f"[📄 تحميل PDF](file://{b['pdf_path']})")
                    c2.write(f"الحجم: {Path(b['pdf_path']).stat().st_size//1024} KB")
                if b.get("etsy_listing_id"):
                    c3.write(f"مسودة Etsy: `{b['etsy_listing_id']}`")

                story_file = config.BOOKS_DIR / b["slug"] / "story.json"
                if story_file.exists():
                    edited = st.text_area("story.json (حرر ثم احفظ)", key=f"e{b['slug']}",
                                          value=story_file.read_text(encoding="utf-8"),
                                          height=250)
                    c4, c5, c6 = st.columns(3)
                    if c4.button("💾 احفظ التعديلات", key=f"s{b['slug']}"):
                        try:
                            parsed = json.loads(edited)
                            story_file.write_text(
                                json.dumps(parsed, ensure_ascii=False, indent=2),
                                encoding="utf-8")
                            st.success("حُفظ — استخدم «ابنِ الكتاب» لإعادة البناء")
                        except Exception as e:  # noqa: BLE001
                            st.error(f"JSON غير صالح: {e}")
                    if c5.button("🛡 فحص الجودة", key=f"q{b['slug']}"):
                        show_result(engine.run_qa(b["slug"]), "QA")
                    if c6.button("✋ اطلب موافقة نشر", key=f"p{b['slug']}"):
                        show_result(engine.request_publish(b["slug"]), "طلب نشر")
    else:
        st.info("لا كتب بعد — اكتب قصة من تبويب الأقسام")

# =====================================================================
# 4) الفرص
# =====================================================================
with tabs[3]:
    st.title("💰 الفرص المسجلة")
    st.caption("من: ذكاء السوق (تقارير) و التسويق بالعمولة (منتجات). لا أرقام مبيعات وهمية")
    sec_col, _ = st.columns([1, 3])
    sector = sec_col.selectbox("القطاع", ["الكل", "intelligence", "affiliate"])
    opps = safe(store.list_opportunities,
                None if sector == "الكل" else sector, None, 200) or []
    if opps:
        for o in opps:
            with st.expander(f"{tag(o['status'])} **{o['title']}** — {o.get('score', '؟')}/10",
                             expanded=False):
                st.write(f"النيش: {o.get('niche', '—')} · القطاع: `{o['sector']}` "
                         f"· {o.get('created_at', '')}")
                payload = o.get("payload")
                if payload:
                    try:
                        st.json(payload if isinstance(payload, dict) else json.loads(payload),
                                expanded=False)
                    except Exception:  # noqa: BLE001
                        st.code(str(payload))
                a, b_, c_ = st.columns(3)
                for val, name, key in (("pursuing", "🎯 نتابعها", "pu"),
                                       ("watching", "👀 مراقبة", "wa"),
                                       ("archived", "🗄️ أرشفة", "arc")):
                    if st.button(name, key=f"{key}{o['id']}"):
                        safe(store.decide_opportunity, o["id"], val)
                        st.rerun()
    else:
        st.info("لا فرص — نفّذ مسح ذكاء السوق أو بحث التسويق بالعمولة")

# =====================================================================
# 5) الموافقات — بوابة الحكم البشري
# =====================================================================
with tabs[4]:
    st.title("✅ بوابة الموافقات")
    st.caption("لا يرفع شيء على Etsy إلا بعد موافقتك هنا — حتى مسودات MOCK")
    pendings = safe(store.list_approvals, "pending", 100) or []
    st.metric("⏳ بانتظار قرارك", len(pendings))
    for a in pendings:
        with st.expander(f"⏳ طلب #{a['id']} — نظام النشر لـ`{a['ref']}` "
                         f"({a['kind']})", expanded=True):
            st.write(f"📝 {a.get('note') or ''} · أُنشئ {a['created_at']}")
            note = st.text_input("ملاحظة (اختياري)", key=f"nn{a['id']}")
            c1, c2 = st.columns(2)
            if c1.button("✅ اعتمد ونفّذ", key=f"ap{a['id']}", type="primary"):
                with st.spinner("الناشر يرفع الرفع (أو Mock في وضع التجربة)"):
                    show_result(engine.decide_publish(a["id"], "approve", note),
                                "اعتماد")
                st.rerun()
            if c2.button("❌ ارفض", key=f"rj{a['id']}"):
                show_result(engine.decide_publish(a["id"], "reject", note), "رفض")
                st.rerun()

    st.subheader("📜 سجل القرارات")
    hist = safe(store.list_approvals, None, 60) or []
    if hist:
        for a in hist:
            st.markdown(f"- {tag(a['status'])} #{a['id']} `{a['kind']}` — `{a['ref']}` "
                        f"· {a['created_at']}")

# =====================================================================
# 6) التقارير
# =====================================================================
with tabs[5]:
    st.title("📈 التقارير (PDF/MD)")
    reports = safe(store.list_reports, 100) or []
    if not reports:
        st.info("لا تقارير بعد")
    for r in reversed(reports[-60:]):
        with st.expander(f"📄 {Path(r.get('path', 'بدون')).name} — "
                         f"{r.get('created_at', '')}", expanded=False):
            if r.get("path") and Path(r["path"]).exists():
                st.download_button("⬇ تحميل",
                                   Path(r["path"]).read_bytes(),
                                   file_name=Path(r["path"]).name,
                                   key=f"d{r['id']}")
            st.markdown((r.get("content") or "")[:4000])

# =====================================================================
# 7) البنية
# =====================================================================
with tabs[6]:
    st.title("🧱 بنية الشركة (Department Registry)")
    st.caption("كل قسم = DomainSpec في السجل. إضافة قطاع جديد = تسجيل بسيط دون لمس المحرك أو CEO")
    rows = []
    for spec in list_domains():
        rows.append({"المفتاح": spec.key, "القسم": spec.title,
                     "الوكلاء": " ، ".join(spec.agents),
                     "القدرات": " ، ".join(spec.capabilities),
                     "سياسة الموافقة": spec.approval_policy,
                     "الكلمات الموجهة": " ، ".join(spec.keywords)})
    st.dataframe(rows, use_container_width=True)

    st.subheader("كيف تضيف قسم شركة جديد؟")
    st.code("""from kidbook.domains import DomainSpec, register_domain

def run_e_commerce(task, store, run_id=None):
    ...  # supervisor + وكلاء مثل بقية الأقسام

register_domain(DomainSpec(
    key="ecommerce", title="التجارة الإلكترونية",
    description="بحث منتجات وموردات Amazon.",
    run=run_e_commerce,
    agents=["sourcer", "analyst"],
    capabilities=["product_research"],
    keywords=["ecommerce", "منتجات"],
    approval_policy="none",
))""", language="python")
    st.caption("الـ CEO يكتشف القسم الجديد تلقائياً ويوجه إليه المهام — دون أي تغيير في المحرك.")

# =====================================================================
# 8) الإعدادات
# =====================================================================
def env_badge(name):
    val = os.getenv(name, "")
    return "✅ مضبوط" if val else "➖ يحتاج مفتاحاً"

with tabs[7]:
    st.title("⚙️ الإعدادات والحالة")
    c1, c2 = st.columns(2)
    c1.markdown(f"**🪨 قاعدة البيانات:** {store.backend_label}")
    c1.markdown(f"**🧠 مزود LLM:** {mode_label()}")
    c1.markdown(f"**🩺 آخر ملاحظة نموذج:** {llm_last_note()}")
    c2.markdown(f"**🔑 MISTRAL_API_KEY** {env_badge('MISTRAL_API_KEY')}")
    c2.markdown(f"**🔑 ETSY_API_KEY** {env_badge('ETSY_API_KEY')}")
    c2.markdown(f"**🔑 DATABASE_URL** {env_badge('DATABASE_URL')}")
    st.divider()
    st.subheader("📁 المسارات")
    st.code(f"books: {config.BOOKS_DIR}\nreports: {config.REPORTS_DIR}\n"
            f"data: {config.SQLITE_PATH}\nfonts: {config.ARABIC_FONT}")
    st.subheader("تشغيلات قاعدة البيانات الأخيرة")
    try:
        with store._cur() as cur:  # noqa: SLF001
            cur.execute("SELECT id, run_type, domain, status, started_at "
                        "FROM kidbook_runs ORDER BY id DESC LIMIT 30")
            st.dataframe([dict(r) for r in cur.fetchall()], use_container_width=True)
    except Exception as e:  # noqa: BLE001
        st.warning(f"تعذّر العرض: {e}")

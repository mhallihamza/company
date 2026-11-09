"""AI Business HQ — واجهة الأوامر (CLI) فوق محرك kidbook.engine.

الاستخدام:
    python main.py trends                    تقرير اتجاهات السوق (قسم الكتب)
    python main.py intelligence [تكليف]       مسح الفرص وتسجيلها في قاعدة البيانات
    python main.py affiliate [نيش]            منتجات عمولة + وحدة اقتصادية حتمية
    python main.py marketing "وصف المنتج"     حزمة SEO/وصف/Pinterest/تقويم
    python main.py finance "9.5 دولار 24 صفحة"  رسوم Etsy/KDP والهوامش (حتمية)
    python main.py make "أرنب صغير يتعلم المشاركة"   قصة → مراجعة → صور+PDF
    python main.py build <slug>               المرحلة الثانية بعد تعديل story.json
    python main.py qa <slug>                  فحص جودة حتمي (PASS/FAIL)
    python main.py publish <slug>             طلب موافقة نشر (لا رفع دون قرارك)
    python main.py approvals                  قائمة الموافقات المعلّقة
    python main.py approve <id> [ملاحظة]      اعتماد → تنفيذ الرفع
    python main.py reject <id> [ملاحظة]       رفض
    python main.py opportunities              الفرص المسجلة
    python main.py run "أي مهمة حرة"          CEO يوجّه تلقائياً للقسم الأنسب
    python main.py domains                    الأقسام والوكلاء في السجل
"""
import sys
import pathlib as pl


def _show(out):
    if isinstance(out, dict) and out.get("ok"):
        print("✔", out.get("summary") or "تم", f"(تشغيلة رقم {out.get('run_id', '—')})")
        for key in ("report_path", "story_path", "pdf_path", "marketing_pack", "listing_id"):
            if out.get(key):
                print(f"   {key}: {out[key]}")
        return True
    print("✖", out.get("error") if isinstance(out, dict) else out)
    return False


def cmd_trends():
    from kidbook import engine
    out = engine.analyze_market()
    if not out["ok"]:
        print("فشل تقرير السوق:", out["error"]); sys.exit(1)
    print(pl.Path(out["report_path"]).read_text(encoding="utf-8"))


def cmd_intelligence():
    from kidbook import engine
    brief = " ".join(sys.argv[2:]) or ""
    _show(engine.run_intelligence(brief))


def cmd_affiliate():
    from kidbook import engine
    niche = " ".join(sys.argv[2:]) or ""
    _show(engine.run_affiliate(niche))


def cmd_marketing():
    from kidbook import engine
    if len(sys.argv) < 3:
        print("اكتب وصف المنتج: python main.py marketing \"كتاب قصص عربية\""); sys.exit(1)
    _show(engine.run_marketing(" ".join(sys.argv[2:])))


def cmd_finance():
    from kidbook import engine
    _show(engine.run_finance(" ".join(sys.argv[2:]) or ""))


def cmd_make(idea):
    from kidbook import engine
    out = engine.create_story(idea)
    if not out["ok"]:
        print("فشل كتابة القصة:", out["error"]); sys.exit(1)
    print("القصة:", out["story"]["title"])
    print("ملف المراجعة:", out["story_path"])
    print("\nراجع/عدّل story.json ثم اضغط Enter للمتابعة لتوليد الصور والـ PDF…")
    input()
    cmd_build(out["slug"])


def cmd_build(slug):
    from kidbook import engine
    slug = pl.Path(slug).name
    if not _show(engine.build_book(slug)):
        sys.exit(1)
    print("افتح الـ PDF وراجع كل صفحة بنفسك قبل النشر.")


def cmd_qa(slug):
    from kidbook import engine
    _show(engine.run_qa(pl.Path(slug).name))


def cmd_publish(slug):
    from kidbook import engine
    slug = pl.Path(slug).name
    print("هذا الأمر ينشئ طلب موافقة فقط — الرفع لا يحدث قبل قرارك.")
    _show(engine.request_publish(slug, "طلب نشر من CLI"))


def cmd_approvals():
    from kidbook.db import get_store
    rows = get_store().list_approvals("pending")
    if not rows:
        print("لا موافقات معلّقة.")
        return
    print(f"{len(rows)} طلباً معلقاً:")
    for a in rows:
        print(f"  #{a['id']} [{a['kind']}] {a['ref']} — {a.get('note') or ''}")


def _decide(cmd):
    from kidbook import engine
    if len(sys.argv) < 3:
        print(f"الاستخدام: python main.py {cmd} <رقم الطلب> [ملاحظة]"); sys.exit(1)
    aid = int(sys.argv[2])
    note = " ".join(sys.argv[3:])
    out = engine.decide_publish(aid, "approve" if cmd == "approve" else "reject", note)
    if cmd == "approve" and out["ok"]:
        print(f"✔ اعتُمد — مسودة رقم {out.get('listing_id')} "
              f"({'MOCK' if out.get('mock') else 'حقيقية'})")
    else:
        _show(out)


def cmd_opportunities():
    from kidbook.db import get_store
    rows = get_store().list_opportunities(limit=40)
    if not rows:
        print("لا فرص مسجلة.")
        return
    for o in rows:
        print(f"  #{o['id']} [{o['sector']}] {o['title']} — {o['score']}/10 ({o['status']})")


def cmd_run():
    from kidbook import engine
    text = " ".join(sys.argv[2:])
    if not text.strip():
        print("اكتب المهمة: python main.py run \"ابحث عن فرص عمولة\""); sys.exit(1)
    out = engine.run_task(text)
    print(f"🧭 CEO وجه المهمة إلى: {out.get('domain')}")
    _show(out)


def cmd_domains():
    from kidbook.domains import list_domains
    print("الأقسام المسجلة في السجل (كل قسم قسم مستقلاً قابل للتوسع):\n")
    for d in list_domains():
        print(f"■ {d.key} — {d.title}")
        print(f"   {d.description}")
        for a in d.agents:
            print(f"     • {a}")
        print(f"   القدرات: {', '.join(d.capabilities)} | الموافقات: {d.approval_policy}\n")


if __name__ == "__main__":
    c = sys.argv[1] if len(sys.argv) > 1 else ""
    table = {
        "trends": cmd_trends,
        "intelligence": cmd_intelligence,
        "affiliate": cmd_affiliate,
        "marketing": cmd_marketing,
        "finance": cmd_finance,
        "make": lambda: cmd_make(sys.argv[2]),
        "build": lambda: cmd_build(sys.argv[2]),
        "qa": lambda: cmd_qa(sys.argv[2]),
        "publish": lambda: cmd_publish(sys.argv[2]),
        "approvals": cmd_approvals,
        "approve": lambda: _decide("approve"),
        "reject": lambda: _decide("reject"),
        "opportunities": cmd_opportunities,
        "run": cmd_run,
        "domains": cmd_domains,
    }
    handler = table.get(c)
    if not handler:
        print(__doc__); sys.exit(0)
    handler()

"""قسم المالية — حسابات الوحدة الاقتصادية من معادلات صريحة (ليست نموذج لغوي).

رسوم Etsy وKDP في جداول ثابتة قابلة للتدقيق. أي تعديل مستقبلي = تغيير
constants في decimal فقط، دون لمس الوكيل.
"""
from __future__ import annotations
from datetime import date

from langgraph.graph import StateGraph, START, END

from kidbook import config
from kidbook.db import get_store
from kidbook.domains import DomainSpec, register_domain
from kidbook.domains.common import KidState, invoke_domain, ask_supervisor, log

# رسوم فعلية منشورة (2026 تقريبياً — تُراجع من الروابط الرسمية):
ETSY = {"listing_fee_usd": 0.20, "transaction_pct": 6.5 / 100, "payment_pct": 3.0 / 100}
KDP = {"paperback_royalty": 0.60, "kdp_ebook_royalty_35": 0.35, "kdp_ebook_royalty_70": 0.70,
       "delivery_per_mb": 0.15}


def unit_economics(price: float, pages: int, item: str = "book") -> dict:
    price = float(price)
    etsy_var = price * (ETSY["transaction_pct"] + ETSY["payment_pct"])
    etsy_per_sale = ETSY["listing_fee_usd"] + etsy_var
    kdp_paperback_royalty = price * KDP["paperback_royalty"]  # print cost خارج هذا التقرير
    kdp70 = price * KDP["kdp_ebook_royalty_70"]
    kdp35 = price * KDP["kdp_ebook_royalty_35"]
    return {
        "price": price, "pages": pages, "item": item,
        "etsy": {"per_sale_costs": round(etsy_per_sale, 2),
                 "net_before_ads": round(price - etsy_per_sale, 2)},
        "kdp_paperback": {"royalty_60_pct": round(kdp_paperback_royalty, 2),
                          "note": "اخصم Print cost من KDP Calculator للحصول على صافي الربحي"},
        "kdp_ebook": {"royalty_70_pct": round(kdp70, 2), "royalty_35_pct": round(kdp35, 2),
                      "delivery_per_mb_usd": KDP["delivery_per_mb"]},
        "assumptions": ["USD", "رقمي = لا كلفة طباعة", "الطباعة تطبق فقط على paperback",
                        "الرسوم تُراجَع من صفحات Etsy/KDP الرسمية — قد تتغير"],
    }


def _calculator(state: KidState) -> KidState:
    store = get_store()
    task = (state.get("task") or "").lower()
    try:
        import re
        m_price = re.search(r"(\d+(?:\.\d+)?)\s*(?:\$|دولار|usd|price)?", task)
        m_pages = re.search(r"(\d{1,4})\s*(?:page|صفحة|صفحات|pages)", task)
        price = float(m_price.group(1)) if m_price else 4.99
        pages = int(m_pages.group(1)) if m_pages else config.PAGES
        result = unit_economics(price, pages)

        config.REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        out = config.REPORTS_DIR / f"finance_{date.today()}.md"
        md = [f"### تحليل الوحدة الاقتصادية — {date.today()}", "",
              f"- السعر: **{price} USD** · الصفحات: **{pages}**",
              "",
              "#### Etsy (رقمي — تحميل مباشر)",
              f"- رسوم لكل وحدة: {result['etsy']['per_sale_costs']} USD",
              f"- الصافي قبل الإعلانات: {result['etsy']['net_before_ads']} USD",
              "",
              "#### KDP (كتاب ورقي)",
              f"- العائد 60%: {result['kdp_paperback']['royalty_60_pct']} USD (قبل Print cost)",
              "",
              "#### KDP (eBook)",
              f"- عائد 70%: {result['kdp_ebook']['royalty_70_pct']} USD",
              f"- عائد 35%: {result['kdp_ebook']['royalty_35_pct']} USD",
              "", "#### الافتراضات", *[f"- {a}" for a in result["assumptions"]]]
        out.write_text("\n".join(md), encoding="utf-8")
        try:
            store.add_report(str(out), out.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass
        return {"summary": f"تحليل مالي جاهز — السعر {price} USD — راجع {out.name}",
                "artifacts": {**state.get("artifacts", {}), "finance": result,
                              "report_path": str(out)},
                "progress": state.get("progress", []) + ["CALC_DONE"]}
    except Exception as e:  # noqa: BLE001
        return {"error": f"فشل الحساب: {e}", "progress": state.get("progress", []) + ["FAILED calculator"]}


def _supervisor(state: KidState) -> KidState:
    nxt = ask_supervisor("finance.supervisor", state.get("progress", []),
                         [("calculator", "CALC_DONE"), ("done", None)])
    return {"summary": nxt}


def _route(state: KidState) -> str:
    if state.get("error"):
        return END
    return "calculator" if (state.get("summary") or "").strip().lower() == "calculator" else END


def build_graph():
    g = StateGraph(KidState)
    g.add_node("supervisor", _supervisor)
    g.add_node("calculator", _calculator)
    g.add_edge(START, "supervisor")
    g.add_conditional_edges("supervisor", _route, {"calculator": "calculator", END: END})
    g.add_edge("calculator", "supervisor")
    return g.compile()


def run(task, store, run_id=None):
    return invoke_domain(build_graph(),
                         {"task": task, "run_id": run_id, "progress": []},
                         store, run_id, "تحليل الوحدة الاقتصادية جاهز")


register_domain(DomainSpec(
    key="finance",
    title="المالية والهوامش",
    description="رسوم Etsy/KDP وعائد الوحدة لكل سعر بالمعادلات — لا نموذج لغوي في الأرقام",
    run=run,
    agents=["calculator (Python حتمي: رسوم Etsy/KDP + صافي الوحدة)",
            "supervisor (calculator → done)"],
    capabilities=["unit_economics", "fee_modeling", "break_even_hints"],
    keywords=["finance", "رسوم", "هامش", "عائد", "تكلفة", "عوائد", "أرباح", "ربح"],
    approval_policy="none",
))

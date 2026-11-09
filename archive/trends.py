"""وكيل الاتجاهات: Google Trends + Etsy API + تحليل Claude. تقرير أسبوعي."""
import os, requests, datetime, pathlib
from pytrends.request import TrendReq
from config import SEED_KEYWORDS
from llm import ask

def google_interest(keywords):
    out = {}
    py = TrendReq(hl="en-US", tz=0)
    for kw in keywords:
        try:
            py.build_payload([kw], timeframe="today 3-m")
            df = py.interest_over_time()
            if not df.empty:
                s = df[kw]
                out[kw] = {"avg": round(float(s.mean()), 1),
                           "last_vs_first": round(float(s.iloc[-4:].mean() - s.iloc[:4].mean()), 1)}
        except Exception as e:
            out[kw] = {"error": str(e)}
    return out

def etsy_competition(keywords):
    """عدد المنافسين + مؤشر الطلب (favorers) من Etsy Open API v3."""
    key = os.getenv("ETSY_API_KEY")
    if not key:
        return {}
    out = {}
    for kw in keywords:
        r = requests.get("https://openapi.etsy.com/v3/application/listings/active",
                         headers={"x-api-key": key},
                         params={"keywords": kw, "limit": 25, "sort_on": "score"}, timeout=30)
        if r.ok:
            j = r.json()
            res = j.get("results", [])
            out[kw] = {"total_listings": j.get("count"),
                       "avg_favorers_top25": round(sum(x.get("num_favorers", 0) for x in res) / max(len(res), 1), 1),
                       "avg_price": round(sum(float(x["price"]["amount"]) / x["price"]["divisor"] for x in res) / max(len(res), 1), 2) if res else None}
    return out

def weekly_report():
    g, e = google_interest(SEED_KEYWORDS), etsy_competition(SEED_KEYWORDS)
    prompt = f"""You are a children's-book market analyst. Data:
Google Trends (3 months): {g}
Etsy competition: {e}
Write the report IN ARABIC: rank the niches by opportunity (rising demand, low competition),
give a score /10 for each, and propose 3 concrete book ideas for the best niche
(title, age, hook). Be honest about data limits."""
    report = ask(prompt)
    pathlib.Path("reports").mkdir(exist_ok=True)
    p = f"reports/trends_{datetime.date.today()}.md"
    pathlib.Path(p).write_text(report, encoding="utf-8")
    return p, report

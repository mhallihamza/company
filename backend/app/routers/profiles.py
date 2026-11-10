"""market_profiles — multi-market seed + listing (Phase 5).

Three starter profiles are seeded on boot if missing. Each entry is a country+language
combination with currency, text direction, font, seed keywords, and a simple seasonal
table. Enable/disable is toggled via the UI — never by code change.
"""
from __future__ import annotations
import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from backend.app.auth import require_founder
from backend.app.db import get_store

router = APIRouter(tags=["profiles"], dependencies=[Depends(require_founder)])


class ProfileCreateIn(BaseModel):
    country: str = Field(..., min_length=2, max_length=2)
    language: str = Field(..., min_length=2, max_length=5)
    currency: str = Field(..., min_length=3, max_length=3)
    dir: str = Field("ltr", pattern="^(ltr|rtl)$")
    font: str = Field("DejaVu Serif", max_length=60)
    seeds: list[str] = Field(default_factory=list)
    seasonal: dict = Field(default_factory=dict)
    enabled: bool = True
    fee_model_ref: str = Field("etsy.global", max_length=40)
    story_prompt_ref: str = Field("story.en", max_length=40)
    font_ref: str = Field("font.dejavu", max_length=40)
    text_direction: str = Field("ltr", pattern="^(ltr|rtl)$")
    seasonal_calendar: list[dict] = Field(default_factory=list)
    qa_ruleset_ref: str = Field("qa.en", max_length=40)


_NEW_COLUMNS = (
    ("fee_model_ref", "TEXT"),
    ("story_prompt_ref", "TEXT"),
    ("font_ref", "TEXT"),
    ("text_direction", "TEXT DEFAULT 'ltr'"),
    ("seasonal_calendar", "TEXT"),
    ("qa_ruleset_ref", "TEXT"),
)

_DDL_PG = """CREATE TABLE IF NOT EXISTS market_profiles (
            profile_id BIGSERIAL PRIMARY KEY,
            country TEXT NOT NULL,
            language TEXT NOT NULL,
            currency TEXT NOT NULL,
            dir TEXT DEFAULT 'ltr',
            font TEXT,
            seeds TEXT,
            seasonal TEXT,
            enabled BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT now(),
            fee_model_ref TEXT,
            story_prompt_ref TEXT,
            font_ref TEXT,
            text_direction TEXT DEFAULT 'ltr',
            seasonal_calendar TEXT,
            qa_ruleset_ref TEXT,
            UNIQUE(country, language))"""
_DDL_SQLITE = """CREATE TABLE IF NOT EXISTS market_profiles (
            profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
            country TEXT NOT NULL,
            language TEXT NOT NULL,
            currency TEXT NOT NULL,
            dir TEXT DEFAULT 'ltr',
            font TEXT,
            seeds TEXT,
            seasonal TEXT,
            enabled BOOLEAN DEFAULT TRUE,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            fee_model_ref TEXT,
            story_prompt_ref TEXT,
            font_ref TEXT,
            text_direction TEXT DEFAULT 'ltr',
            seasonal_calendar TEXT,
            qa_ruleset_ref TEXT,
            UNIQUE(country, language))"""


def _ensure_table():
    s = get_store()
    if s.kind == "pg":
        s._execute(_DDL_PG)
    else:
        s._execute(_DDL_SQLITE)
    # incremental migration for installs created before Item 7
    for name, ddl in _NEW_COLUMNS:
        try:
            if s.kind == "pg":
                s._execute(f"ALTER TABLE market_profiles ADD COLUMN IF NOT EXISTS {name} {ddl}")
            else:
                s._execute(f"ALTER TABLE market_profiles ADD COLUMN {name} {ddl}")
        except Exception:  # noqa: BLE001 — column may already exist on sqlite
            pass
    # backfill text_direction from legacy `dir`
    try:
        s._execute("UPDATE market_profiles SET text_direction = dir WHERE text_direction IS NULL")
    except Exception:  # noqa: BLE001
        pass
    # migrate legacy free-text `seasonal` dict → structured calendar list
    try:
        rows = s.q("SELECT profile_id, seasonal FROM market_profiles "
                   "WHERE seasonal_calendar IS NULL AND seasonal IS NOT NULL")
        for row in rows:
            try:
                legacy = json.loads(row["seasonal"]) or {}
                calendar = [{"name": str(name), "start": str(span).split("–")[0].strip() or None,
                             "end": str(span).split("–")[-1].strip() or None,
                             "lead_weeks": 8}
                            for name, span in list(legacy.items())[:8]]
                s._execute("UPDATE market_profiles SET seasonal_calendar=? WHERE profile_id=?",
                           (json.dumps(calendar, ensure_ascii=False), row["profile_id"]))
            except Exception:  # noqa: BLE001 — keep legacy row intact, never lose data
                continue
    except Exception:  # noqa: BLE001
        pass


_STARTER_SEEDS = [
    dict(country="US", language="en", currency="USD", dir="ltr", font="DejaVu Serif",
         seeds=["back to school", "summer reading", "coloring animals", "activity book"],
         seasonal={"back_to_school": "August–October",
                   "christmas": "November–December",
                   "easter": "March–April"},
         fee_model_ref="etsy.us", story_prompt_ref="story.en",
         font_ref="font.dejavu", text_direction="ltr",
         seasonal_calendar=[
             {"name": "back_to_school", "start": "August", "end": "September–October", "lead_weeks": 8},
             {"name": "christmas", "start": "November", "end": "December", "lead_weeks": 6},
             {"name": "easter", "start": "March", "end": "April", "lead_weeks": 6},
         ],
         qa_ruleset_ref="qa.en"),
    dict(country="FR", language="fr", currency="EUR", dir="ltr", font="DejaVu Serif",
         seeds=["rentrée scolaire", "cahier activités", "coloriage animaux", "livre enfants"],
         seasonal={"rentrée": "Septembre",
                   "noël": "Novembre–Décembre",
                   "pâques": "Mars–Avril"},
         fee_model_ref="etsy.eu", story_prompt_ref="story.fr",
         font_ref="font.dejavu", text_direction="ltr",
         seasonal_calendar=[
             {"name": "rentree_scolaire", "start": "Septembre", "end": "Octobre", "lead_weeks": 8},
             {"name": "noel", "start": "Novembre", "end": "Décembre", "lead_weeks": 6},
             {"name": "paques", "start": "Mars", "end": "Avril", "lead_weeks": 6},
         ],
         qa_ruleset_ref="qa.fr"),
    dict(country="SA", language="ar", currency="SAR", dir="rtl", font="Amiri",
         seeds=["قصص قبل النوم", "عيد الفطر", "عيد الأضحى", "أبجدية عربية", "رمضان"],
         seasonal={"ramadan": "February–April",
                   "eid_fitr": "March–April",
                   "eid_adha": "May–June",
                   "back_to_school": "August–September"},
         fee_model_ref="etsy.global", story_prompt_ref="story.ar",
         font_ref="font.amiri", text_direction="rtl",
         seasonal_calendar=[
             {"name": "ramadan", "start": "February", "end": "April", "lead_weeks": 8},
             {"name": "eid_fitr", "start": "March", "end": "April", "lead_weeks": 8},
             {"name": "eid_adha", "start": "May", "end": "June", "lead_weeks": 8},
             {"name": "back_to_school", "start": "August", "end": "September", "lead_weeks": 8},
         ],
         qa_ruleset_ref="qa.ar"),
]


def seed():
    """Insert/backfill the three starter profiles — idempotent, safe at every boot.

    Existing rows are only filled for refs that are still NULL — founder edits are preserved.
    """
    _ensure_table()
    s = get_store()
    ph = "%s" if s.kind == "pg" else "?"
    ins = f"""INSERT INTO market_profiles
               (country, language, currency, dir, font, seeds, seasonal,
                fee_model_ref, story_prompt_ref, font_ref, text_direction,
                seasonal_calendar, qa_ruleset_ref)
               VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})
               ON CONFLICT (country, language) DO NOTHING"""
    upsert = f"""UPDATE market_profiles SET
                   fee_model_ref = COALESCE(fee_model_ref, {ph}),
                   story_prompt_ref = COALESCE(story_prompt_ref, {ph}),
                   font_ref = COALESCE(font_ref, {ph}),
                   text_direction = COALESCE(text_direction, {ph}),
                   seasonal_calendar = COALESCE(seasonal_calendar, {ph}),
                   qa_ruleset_ref = COALESCE(qa_ruleset_ref, {ph})
                WHERE country = {ph} AND language = {ph}"""
    for seed_row in _STARTER_SEEDS:
        with s._cur() as cur:  # noqa: SLF001
            cur.execute(ins, (seed_row["country"], seed_row["language"], seed_row["currency"],
                              seed_row["dir"], seed_row["font"],
                              json.dumps(seed_row["seeds"], ensure_ascii=False),
                              json.dumps(seed_row["seasonal"], ensure_ascii=False),
                              seed_row["fee_model_ref"], seed_row["story_prompt_ref"],
                              seed_row["font_ref"], seed_row["text_direction"],
                              json.dumps(seed_row["seasonal_calendar"], ensure_ascii=False),
                              seed_row["qa_ruleset_ref"]))
            cur.execute(upsert, (seed_row["fee_model_ref"], seed_row["story_prompt_ref"],
                                 seed_row["font_ref"], seed_row["text_direction"],
                                 json.dumps(seed_row["seasonal_calendar"], ensure_ascii=False),
                                 seed_row["qa_ruleset_ref"],
                                 seed_row["country"], seed_row["language"]))


def _with_fee_badge(row: dict) -> dict:
    """Annotate each profile with fee_model verification status (never invented)."""
    try:
        from agents.fees.registry import FEE_MODELS
        ref = (row.get("fee_model_ref") or "").strip().lower()
        model = FEE_MODELS.get(ref)
        row["fee_verified"] = bool(model and model.verified)
        row["fee_currency"] = model.currency if model else None
    except Exception:  # noqa: BLE001
        row["fee_verified"] = False
        row["fee_currency"] = None
    return row


@router.get("/profiles")
def list_profiles():
    seed()
    s = get_store()
    rows = s.q("SELECT * FROM market_profiles ORDER BY enabled DESC, country")
    return [_with_fee_badge(dict(r)) for r in rows]


@router.post("/profiles")
def create_profile(body: ProfileCreateIn):
    seed()
    s = get_store()
    ph = "%s" if s.kind == "pg" else "?"
    ins = f"""INSERT INTO market_profiles
              (country, language, currency, dir, font, seeds, seasonal,
               fee_model_ref, story_prompt_ref, font_ref, text_direction,
               seasonal_calendar, qa_ruleset_ref)
              VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph},{ph})
              RETURNING profile_id"""
    with s._cur() as cur:                 # noqa: SLF001
        cur.execute(ins, (body.country.upper(), body.language.lower(),
                          body.currency.upper(), body.dir, body.font,
                          json.dumps(body.seeds, ensure_ascii=False),
                          json.dumps(body.seasonal, ensure_ascii=False),
                          body.fee_model_ref.strip().lower(),
                          body.story_prompt_ref.strip().lower(),
                          body.font_ref.strip().lower(),
                          body.text_direction,
                          json.dumps(body.seasonal_calendar, ensure_ascii=False),
                          body.qa_ruleset_ref.strip().lower()))
        row = cur.fetchone()
        pid = int(row["profile_id"] if isinstance(row, dict) else row[0])
    return {"ok": True, "profile_id": pid}


@router.patch("/profiles/{profile_id}/toggle")
def toggle_profile(profile_id: int):
    s = get_store()
    s._execute("UPDATE market_profiles SET enabled = NOT enabled WHERE profile_id=?",
               (profile_id,))
    return {"ok": True}

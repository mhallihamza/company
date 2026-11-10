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
            UNIQUE(country, language))"""


def _ensure_table():
    s = get_store()
    if s.kind == "pg":
        s._execute(_DDL_PG)
    else:
        s._execute(_DDL_SQLITE)


def seed():
    """Insert the three starter profiles — idempotent, safe to call at every boot."""
    _ensure_table()
    s = get_store()
    seeds = [
        ("US", "en", "USD", "ltr", "DejaVu Serif",
         ["back to school", "summer reading", "coloring animals", "activity book"],
         {"back_to_school": "August–September",
          "christmas": "December",
          "easter": "March–April"}),
        ("FR", "fr", "EUR", "ltr", "DejaVu Serif",
         ["rentrée scolaire", "cahier activités", "coloriage animaux", "livre enfants"],
         {"rentrée": "September",
          "noël": "December",
          "pâques": "March–April"}),
        ("SA", "ar", "SAR", "rtl", "Amiri",
         ["قصص قبل النوم", "عيد الفطر", "عيد الأضحى", "أبجدية عربية", "رمضان"],
         {"ramadan": "March–April",
          "eid_fitr": "March–April",
          "eid_adha": "May–June",
          "back_to_school": "September"}),
    ]
    ph = "%s" if s.kind == "pg" else "?"
    sql = f"""INSERT INTO market_profiles
               (country, language, currency, dir, font, seeds, seasonal)
               VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph})
               ON CONFLICT (country, language) DO NOTHING"""
    for country, lang, currency, direction, font, seeds_list, seasonal in seeds:
        with s._cur() as cur:  # noqa: SLF001
            cur.execute(sql, (country, lang, currency, direction, font,
                              json.dumps(seeds_list, ensure_ascii=False),
                              json.dumps(seasonal, ensure_ascii=False)))


@router.get("/profiles")
def list_profiles():
    seed()
    s = get_store()
    rows = s.q("SELECT * FROM market_profiles ORDER BY enabled DESC, country")
    return rows


@router.post("/profiles")
def create_profile(body: ProfileCreateIn):
    seed()
    s = get_store()
    ph = "%s" if s.kind == "pg" else "?"
    ins = f"""INSERT INTO market_profiles
              (country, language, currency, dir, font, seeds, seasonal)
              VALUES ({ph},{ph},{ph},{ph},{ph},{ph},{ph}) RETURNING profile_id"""
    with s._cur() as cur:                 # noqa: SLF001
        cur.execute(ins, (body.country.upper(), body.language.lower(),
                          body.currency.upper(), body.dir, body.font,
                          json.dumps(body.seeds, ensure_ascii=False),
                          json.dumps(body.seasonal, ensure_ascii=False)))
        row = cur.fetchone()
        pid = int(row["profile_id"] if isinstance(row, dict) else row[0])
    return {"ok": True, "profile_id": pid}


@router.patch("/profiles/{profile_id}/toggle")
def toggle_profile(profile_id: int):
    s = get_store()
    s._execute("UPDATE market_profiles SET enabled = NOT enabled WHERE profile_id=?",
               (profile_id,))
    return {"ok": True}

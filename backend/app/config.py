"""Settings and path roots — from .env and friends."""
from __future__ import annotations
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]           # project root

# load .env before any key reads — env vars take precedence over the file
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=False)
except ImportError:
    # non-fatal; fall back to raw environment variables
    pass

STORAGE = ROOT / "storage"
BOOKS_DIR = STORAGE / "books"
REPORTS_DIR = STORAGE / "reports"
DATA_DIR = ROOT / "data"
ARABIC_FONT = ROOT / "fonts" / "Amiri-Regular.ttf"

DB_BACKEND = os.getenv("DB_BACKEND", "auto")          # auto | supabase | sqlite
DATABASE_URL = os.getenv("DATABASE_URL", "")
SQLITE_PATH = DATA_DIR / "hq.db"
# Sane fallback only — overridden per book via `products.price_usd`
DEFAULT_BOOK_PRICE_USD = float(os.getenv("DEFAULT_BOOK_PRICE_USD", "4.99") or 4.99)

FEATURE_SCHEDULER = os.getenv("ENABLE_SCHEDULER", "").lower() in ("1", "true", "yes")


def ensure_dirs() -> None:
    for d in (BOOKS_DIR, REPORTS_DIR, DATA_DIR):
        d.mkdir(parents=True, exist_ok=True)


ensure_dirs()

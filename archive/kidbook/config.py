"""إعدادات المشروع — تُقرأ من .env مع قيم افتراضية معقولة."""
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

# ---- إعدادات الكتاب ----
LANGUAGE = os.getenv("KIDBOOK_LANGUAGE", "ar")          # "ar" أو "en"
AGE_RANGE = os.getenv("KIDBOOK_AGE_RANGE", "3-6")
PAGES = int(os.getenv("KIDBOOK_PAGES", "12"))
PAGE_SIZE_IN = float(os.getenv("KIDBOOK_PAGE_SIZE", "8.5"))
ARABIC_FONT = ROOT / "fonts" / "Amiri-Regular.ttf"
SEED_KEYWORDS = [
    "bedtime story kids", "coloring book animals",
    "قصص قبل النوم", "learning alphabet kids",
]

# ---- وضع العمل ----
FAKE_LLM = os.getenv("KIDBOOK_FAKE_LLM", "").lower() in ("1", "true", "yes")

# ---- قاعدة البيانات ----
DB_BACKEND = os.getenv("DB_BACKEND", "auto").lower()      # auto | supabase | sqlite
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
SQLITE_PATH = ROOT / "data" / "kidbook.db"

# ---- المسارات ----
BOOKS_DIR = ROOT / "books"
REPORTS_DIR = ROOT / "reports"
DATA_DIR = ROOT / "data"

def ensure_dirs():
    for d in (BOOKS_DIR, REPORTS_DIR, DATA_DIR):
        d.mkdir(parents=True, exist_ok=True)

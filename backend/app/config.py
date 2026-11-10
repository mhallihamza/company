"""جذر الإعدادات والمسارات — من .env وغيرها."""
from __future__ import annotations
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]           # جذر المشروع

# تحميل .env قبل أي قراءة للمفاتيح — مع التجاوز: بيئة الأدوات تتغلب على الملف
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env", override=False)
except ImportError:
    # لا يعيق التشغيل؛ يبقى الاعتماد على متغيرات البيئة الصرفة
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

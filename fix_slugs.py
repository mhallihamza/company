"""واحدية: إصلاح slug المنتجات والأقسام الحالية + الحذف النظيف لسجلات الاختبار المعطلة."""
import os
import re
import sys
import shutil
from pathlib import Path

os.environ["KIDBOOK_FAKE_LLM"] = "1"
os.environ["DB_BACKEND"] = "auto"

from backend.app import config
from backend.app.db import get_store


def fix_slug(text: str) -> str:
    keep = "".join(ch for ch in str(text) if ch.isascii() and (ch.isalnum() or ch in "_-"))
    keep = re.sub(r"[^a-z0-9_-]+", "_", keep.lower()).strip("_-")
    return keep or "book"


store = get_store()
rows = store.q("SELECT product_id, slug, title, status FROM products")
page = 0
for r in rows:
    page += 1
    old = r["slug"]
    new = fix_slug(old)
    if new != old:
        print(f"[{page}] fixing {old!r} -> {new!r}")
        store._execute("UPDATE products SET slug=? WHERE product_id=?",
                       (new, r["product_id"]))
    else:
        print(f"[{page}] ok {new!r}")

# Archive fresh books
for r in store.q("SELECT product_id, slug, status FROM products ORDER BY product_id"):
    d = config.BOOKS_DIR / r["slug"]
    if d.exists():
        print(f"kept {r['slug']}")
    else:
        print(f"MISSING DIR {r['slug']}")

# Go through manual cleanup for any stray mangled directories
for p in Path(config.BOOKS_DIR).iterdir():
    if p.is_dir() and any(ord(c) > 127 for c in p.name):
        # try a copy with fixed name, then just leave dirs (don't delete user data)
        newdir = p.with_name(fix_slug(p.name))
        if not newdir.exists():
            p.rename(newdir)
            print(f"renamed dir {p.name!r} -> {newdir.name!r}")

print("done")

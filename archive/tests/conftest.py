"""إعداد الاختبارات: وضع محاكاة حتمي + قاعدة SQLite مؤقتة معزولة."""
import os
import sys
from pathlib import Path

os.environ["KIDBOOK_FAKE_LLM"] = "1"
os.environ["DB_BACKEND"] = "sqlite"
os.environ["DATABASE_URL"] = ""
os.environ["LLM_PROVIDER"] = "fake"

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

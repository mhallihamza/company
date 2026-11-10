"""Backend test setup — deterministic mocks + isolated temporary SQLite."""
import os
import sys
from pathlib import Path

os.environ["AIHQ_FAKE_LLM"] = "1"
os.environ["DB_BACKEND"] = "sqlite"
os.environ["DATABASE_URL"] = ""
os.environ["LLM_PROVIDER"] = "fake"
os.environ["FOUNDER_TOKEN"] = "test-founder-token-000000000000"

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

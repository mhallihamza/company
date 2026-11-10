"""Evidence validation — validates LLM briefs against stored evidence.

Any number appearing in the brief must match the captured evidence (numeric tolerance 1e-6).
No "sales"/"revenue" claims when the only demand proxy is favorers. Validation failures
are never silently accepted — the brief is stored as `rejected_by_validator`.
"""
from agents.validation.evidence import ValidationResult, validate_brief

__all__ = ["validate_brief", "ValidationResult"]

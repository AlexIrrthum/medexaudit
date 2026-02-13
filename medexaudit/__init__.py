"""medexaudit - Benchmark LLMs on clinical fact extraction from medical conversations."""

__version__ = "0.1.0"

from .audit import audit
from .extract import get_candidate_extract, get_reference_extract
from .llm import DEFAULT_MAX_RETRIES, DEFAULT_MAX_TOKENS, DEFAULT_MODEL, DEFAULT_TEMPERATURE
from .models import AuditReport, ClinicalFact, Extraction, Scenario
from .report import report
from .simulate import simulate

__all__ = [
    "audit",
    "get_candidate_extract",
    "get_reference_extract",
    "report",
    "simulate",
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_MAX_TOKENS",
    "DEFAULT_MODEL",
    "DEFAULT_TEMPERATURE",
    "AuditReport",
    "ClinicalFact",
    "Extraction",
    "Scenario",
]

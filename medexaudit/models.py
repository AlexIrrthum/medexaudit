"""Pydantic data models for medexaudit."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

ComplexityLevel = Literal["Minimal", "Medium", "High"]


class ComplexityParams(BaseModel):
    """Complexity parameters for conversation simulation."""

    small_talk: ComplexityLevel = "Minimal"
    patient_confusion: ComplexityLevel = "Minimal"
    temporal_complexity: ComplexityLevel = "Minimal"
    clinical_complexity: ComplexityLevel = "Minimal"
    lay_terms: ComplexityLevel = "Minimal"
    third_party_interference: ComplexityLevel = "Minimal"
    resistance: ComplexityLevel = "Minimal"
    semantic_ambiguity: ComplexityLevel = "Minimal"
    initial_incoherence: ComplexityLevel = "Minimal"
    named_entities: ComplexityLevel = "Minimal"
    clinical_nonsense: ComplexityLevel = "Minimal"
    total_nonsense: ComplexityLevel = "Minimal"


class Scenario(BaseModel):
    """Structured scenario with context and complexity parameters."""

    context: str
    complexity: ComplexityParams = ComplexityParams()


class ClinicalFact(BaseModel):
    """Single atomic clinical fact extracted from a transcript."""

    fact_id: str
    category: Literal["Finding", "Measurement", "Procedure", "Substance", "Context", "Other"]
    raw_verbatim: str
    normalized_term: str
    value: str | None = None
    status: Literal["Active", "Resolved", "Conditional", "Pending"]
    condition: str | None = None
    subject: Literal["Patient", "Family", "Professional", "Third-Party"]
    subject_relationship: str | None = None
    subject_name: str | None = None
    source: Literal["Doctor", "Patient", "Other"]
    negation: bool = False
    certainty: Literal["Certain", "Uncertain", "Suspected"]
    clinical_nonsense: bool = False
    timeline: Literal["Past", "Current", "Future", "Undetermined"]
    beginning: str | None = None
    end: str | None = None
    duration: str | None = None


class Extraction(BaseModel):
    """Wrapper for a list of extracted facts + metadata."""

    model: str
    conversation_file: str
    is_reference: bool
    timestamp: str
    facts: list[ClinicalFact]


class Deduction(BaseModel):
    field: str
    points: int
    reason: str


class FactAuditResult(BaseModel):
    ref_id: str
    candidate_id: str | None = None
    match_quality: Literal["High", "Partial", "None"]
    deductions: list[Deduction]
    fact_score: float


class FinalMetrics(BaseModel):
    reference_fact_count: int
    hallucination_count: int
    global_accuracy_score: float
    verdict: Literal["Pass", "Fail"]


class AuditReport(BaseModel):
    """Full audit result with metadata."""

    reference_file: str
    candidate_file: str
    candidate_model: str
    judge_model: str
    timestamp: str
    audit_results: list[FactAuditResult]
    final_metrics: FinalMetrics

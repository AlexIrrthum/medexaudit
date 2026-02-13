"""Phases 2 & 3: Reference and candidate extraction."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel

from .llm import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL,
    DEFAULT_TEMPERATURE,
    call_llm,
    load_prompt,
)
from .models import ClinicalFact, Extraction
from .paths import DATA_DIR


class _LenientFact(ClinicalFact):
    """ClinicalFact that accepts any string for Literal fields.

    Candidate models may return values outside the expected enums
    (e.g. "Suspected" for status). We capture these as-is so the
    audit phase can score them rather than crashing the pipeline.
    """

    category: str  # type: ignore[assignment]
    status: str  # type: ignore[assignment]
    subject: str  # type: ignore[assignment]
    source: str  # type: ignore[assignment]
    certainty: str  # type: ignore[assignment]
    timeline: str  # type: ignore[assignment]


class _FactList(BaseModel):
    """Internal wrapper for LLM JSON response."""
    facts: list[_LenientFact]


def _model_slug(model: str) -> str:
    """Convert 'gemini/gemini-3-pro' -> 'gemini-3-pro'."""
    return re.sub(r"[^a-zA-Z0-9._-]", "-", model.split("/")[-1])


def extract_facts(
    conversation_path: str,
    model: str = DEFAULT_MODEL,
    is_reference: bool = False,
    output_path: str | None = None,
    temperature: float = DEFAULT_TEMPERATURE,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> Extraction:
    """Extract clinical facts from a conversation transcript.

    1. Read conversation text
    2. Read prompts/extractor.md as system prompt
    3. Call LLM with conversation as user message, response_model=_FactList
    4. Wrap in Extraction with metadata
    5. Save JSON to output_path (auto-generated if None)
    6. Return Extraction
    """
    conversation_text = Path(conversation_path).read_text(encoding="utf-8")
    system_prompt = load_prompt("extractor")

    result = call_llm(
        model=model,
        system_prompt=system_prompt,
        user_prompt=conversation_text,
        response_model=_FactList,
        temperature=temperature,
        max_tokens=max_tokens,
        max_retries=max_retries,
    )

    ts = datetime.now(timezone.utc)
    extraction = Extraction(
        model=model,
        conversation_file=str(conversation_path),
        is_reference=is_reference,
        timestamp=ts.isoformat(),
        facts=result.facts,
    )

    if output_path is None:
        stem = Path(conversation_path).stem
        slug = _model_slug(model)
        label = "ref" if is_reference else "cand"
        ts_str = ts.strftime("%Y%m%d_%H%M%S")
        out = DATA_DIR / "extracts" / f"{stem}_{slug}_{label}_{ts_str}.json"
    else:
        out = Path(output_path)

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(extraction.model_dump_json(indent=2), encoding="utf-8")
    return extraction


def get_reference_extract(
    conversation_path: str,
    model: str = DEFAULT_MODEL,
    output_path: str | None = None,
    temperature: float = DEFAULT_TEMPERATURE,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> Extraction:
    """Extract reference (ground truth) clinical facts from a conversation.

    Uses the frontier model to produce the gold-standard extraction that
    candidate models will be scored against.

    Args:
        conversation_path: Path to a conversation transcript text file.
        model: LiteLLM model string for the frontier (judge) model.
        output_path: Where to write the extraction JSON. When *None* a
            timestamped path under ``data/extracts/`` is generated.
        temperature: LLM sampling temperature.
        max_tokens: Maximum tokens for the LLM response.
        max_retries: Maximum retries on transient LLM errors.

    Returns:
        An :class:`Extraction` containing the list of clinical facts and metadata.

    Raises:
        FileNotFoundError: If *conversation_path* does not exist.
    """
    return extract_facts(
        conversation_path=conversation_path,
        model=model,
        is_reference=True,
        output_path=output_path,
        temperature=temperature,
        max_tokens=max_tokens,
        max_retries=max_retries,
    )


def get_candidate_extract(
    conversation_path: str,
    model: str = DEFAULT_MODEL,
    output_path: str | None = None,
    temperature: float = DEFAULT_TEMPERATURE,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> Extraction:
    """Extract candidate clinical facts from a conversation.

    Runs the model under test against the same conversation used for the
    reference extraction. Uses lenient parsing so out-of-enum values are
    captured rather than rejected.

    Args:
        conversation_path: Path to a conversation transcript text file.
        model: LiteLLM model string for the candidate model being evaluated.
        output_path: Where to write the extraction JSON. When *None* a
            timestamped path under ``data/extracts/`` is generated.
        temperature: LLM sampling temperature.
        max_tokens: Maximum tokens for the LLM response.
        max_retries: Maximum retries on transient LLM errors.

    Returns:
        An :class:`Extraction` containing the list of clinical facts and metadata.

    Raises:
        FileNotFoundError: If *conversation_path* does not exist.
    """
    return extract_facts(
        conversation_path=conversation_path,
        model=model,
        is_reference=False,
        output_path=output_path,
        temperature=temperature,
        max_tokens=max_tokens,
        max_retries=max_retries,
    )

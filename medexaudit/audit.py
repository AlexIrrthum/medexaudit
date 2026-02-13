"""Phase 4: Audit/scoring of candidate extractions against reference."""

from __future__ import annotations

import json
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
from .models import AuditReport, FactAuditResult, FinalMetrics
from .paths import DATA_DIR


class _AuditLLMResponse(BaseModel):
    """Shape expected from the auditor LLM."""
    audit_results: list[FactAuditResult]
    final_metrics: FinalMetrics


def _load_extraction(path: str) -> tuple[dict, str]:
    """Load an extraction JSON file.

    Handles both the Extraction wrapper format and bare fact arrays.
    Returns (dict suitable for prompt injection, model name).
    """
    raw = json.loads(Path(path).read_text(encoding="utf-8"))

    if isinstance(raw, list):
        return {"facts": raw}, "unknown"

    return {"facts": raw.get("facts", [])}, raw.get("model", "unknown")


def audit(
    reference_path: str,
    candidate_path: str,
    model: str = DEFAULT_MODEL,
    output_path: str | None = None,
    temperature: float = DEFAULT_TEMPERATURE,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> AuditReport:
    """Compare candidate extraction against reference using the auditor prompt.

    Loads both extraction JSONs, injects them into the auditor system prompt,
    and asks the judge LLM to produce a per-fact audit with deductions and a
    global accuracy score.

    Args:
        reference_path: Path to the reference (ground truth) extraction JSON.
        candidate_path: Path to the candidate extraction JSON.
        model: LiteLLM model string for the judge model.
        output_path: Where to write the audit JSON. When *None* a timestamped
            path under ``data/audits/`` is generated.
        temperature: LLM sampling temperature.
        max_tokens: Maximum tokens for the LLM response.
        max_retries: Maximum retries on transient LLM errors.

    Returns:
        An :class:`AuditReport` with per-fact results and final metrics.

    Raises:
        FileNotFoundError: If *reference_path* or *candidate_path* does not exist.
        json.JSONDecodeError: If either file is not valid JSON.
    """
    ref_data, _ = _load_extraction(reference_path)
    cand_data, cand_model = _load_extraction(candidate_path)

    prompt_template = load_prompt("auditor")
    system_prompt = prompt_template.replace(
        "{{INSERT_REFERENCE_JSON}}", json.dumps(ref_data, indent=2, ensure_ascii=False)
    ).replace(
        "{{INSERT_CANDIDATE_JSON}}", json.dumps(cand_data, indent=2, ensure_ascii=False)
    )

    result = call_llm(
        model=model,
        system_prompt=system_prompt,
        user_prompt="Perform the audit following the instructions above. Return the structured JSON report.",
        response_model=_AuditLLMResponse,
        temperature=temperature,
        max_tokens=max_tokens,
        max_retries=max_retries,
    )

    ts = datetime.now(timezone.utc)
    report = AuditReport(
        reference_file=str(reference_path),
        candidate_file=str(candidate_path),
        candidate_model=cand_model,
        judge_model=model,
        timestamp=ts.isoformat(),
        audit_results=result.audit_results,
        final_metrics=result.final_metrics,
    )

    if output_path is None:
        ref_stem = Path(reference_path).stem
        cand_stem = Path(candidate_path).stem
        ts_str = ts.strftime("%Y%m%d_%H%M%S")
        out = DATA_DIR / "audits" / f"{ref_stem}_vs_{cand_stem}_{ts_str}.json"
    else:
        out = Path(output_path)

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return report

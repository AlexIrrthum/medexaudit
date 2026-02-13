"""Phase 1: Conversation generation from scenario files."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import yaml

from .llm import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL,
    DEFAULT_TEMPERATURE,
    call_llm,
    load_prompt,
)
from .models import Scenario
from .paths import DATA_DIR

COMPLEXITY_LABELS: dict[str, str] = {
    "small_talk": "Small Talk (Bruit)",
    "patient_confusion": "Confusion du Patient",
    "temporal_complexity": "Complexité Temporelle",
    "clinical_complexity": "Complexité Clinique",
    "lay_terms": "Termes Profanes (Normalisation)",
    "third_party_interference": "Interférence d'un Tiers (Attribution)",
    "resistance": "Résistance / Stigmate (Nuance)",
    "semantic_ambiguity": "Polysémie & Ambiguïté Sémantique",
    "initial_incoherence": "Incohérence Initiale (Auto-Correction)",
    "named_entities": "Noms Propres (Entités Nommées)",
    "clinical_nonsense": "Nonsense Clinique (Cohérence Médicale)",
    "total_nonsense": "Nonsense Total (Filtrage de Bruit Absurde)",
}


def _format_user_prompt(scenario: Scenario) -> str:
    """Build the user prompt from a validated Scenario."""
    lines = [scenario.context.strip(), "", "## Paramètres de complexité"]
    for field, label in COMPLEXITY_LABELS.items():
        value = getattr(scenario.complexity, field)
        lines.append(f"- **{label}** : {value}")
    return "\n".join(lines)


def simulate(
    scenario_path: str,
    model: str = DEFAULT_MODEL,
    output_path: str | None = None,
    temperature: float = DEFAULT_TEMPERATURE,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    max_retries: int = DEFAULT_MAX_RETRIES,
) -> str:
    """Generate a clinical conversation transcript from a scenario YAML file.

    Parses the scenario YAML, formats complexity parameters into a user prompt,
    and calls the LLM with the simulator system prompt to produce a realistic
    French clinical conversation transcript.

    Args:
        scenario_path: Path to a YAML file containing a ``context`` string and
            optional ``complexity`` parameters (see :class:`Scenario`).
        model: LiteLLM model string (``provider/model-name``).
        output_path: Where to write the transcript. When *None* a timestamped
            path under ``data/conversations/`` is generated automatically.
        temperature: LLM sampling temperature.
        max_tokens: Maximum tokens for the LLM response.
        max_retries: Maximum retries on transient LLM errors.

    Returns:
        The generated conversation transcript as a string.

    Raises:
        FileNotFoundError: If *scenario_path* does not exist.
        yaml.YAMLError: If the file is not valid YAML.
        pydantic.ValidationError: If the YAML doesn't match the Scenario schema.
    """
    raw = yaml.safe_load(Path(scenario_path).read_text(encoding="utf-8"))
    scenario = Scenario.model_validate(raw)
    user_prompt = _format_user_prompt(scenario)
    system_prompt = load_prompt("simulator")

    transcript = call_llm(
        model=model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        temperature=temperature,
        max_tokens=max_tokens,
        max_retries=max_retries,
    )

    if output_path is None:
        stem = Path(scenario_path).stem
        ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        out = DATA_DIR / "conversations" / f"{stem}_{ts}.txt"
    else:
        out = Path(output_path)

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(transcript, encoding="utf-8")
    return transcript

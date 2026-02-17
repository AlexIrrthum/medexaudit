# medexaudit

Benchmark LLMs on clinical fact extraction from French medical conversation transcripts.

A frontier LLM serves triple duty: generating realistic conversations, producing ground-truth extractions, and auditing candidate model outputs. Uses [LiteLLM](https://docs.litellm.ai/) so you can swap in any provider (OpenAI, Google, Together, local models).

## Setup

Requires Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

Set API keys for the models you plan to use:

```bash
export GEMINI_API_KEY=...       # default frontier model
export OPENAI_API_KEY=...       # if testing OpenAI candidates
export TOGETHER_API_KEY=...     # if testing Together candidates
```

## Usage

The tool runs in 5 phases. Each command is also importable as a library function.

### 1. Simulate a conversation

Generate a clinical transcript from a scenario YAML file:

```bash
uv run medexaudit simulate --scenario data/scenarios/my_scenario.yaml
```

Scenarios use a structured YAML format with a clinical context and complexity parameters:

```yaml
context:
  Une adolescente de 14 ans, sportive, visite un médecin du sport
  pour une douleur au tibia et à la hanche gauches.

complexity:
  small_talk: Medium
  lay_terms: Medium
  resistance: Medium
  # all other parameters default to Minimal
```

See [`data/scenarios/scenario_template.yaml`](data/scenarios/scenario_template.yaml) for the full template.

#### Complexity parameters

Each parameter controls a specific dimension of conversational difficulty on a 3-level scale: **Minimal**, **Medium**, **High**. They inject realistic noise that challenges the extraction phase.

| Parameter | YAML key | What it controls |
|---|---|---|
| Small Talk (Bruit) | `small_talk` | Digressions on family, weather, unrelated anecdotes |
| Confusion du Patient | `patient_confusion` | Vagueness, contradictions, forgotten medication names |
| Complexité Temporelle | `temporal_complexity` | Multiple symptoms over months/years with fuzzy dates |
| Complexité Clinique | `clinical_complexity` | Multimorbidity and polypharmacy (5+ medications) |
| Termes Profanes (Normalisation) | `lay_terms` | Metaphors and vague descriptions instead of medical terms |
| Interférence d'un Tiers (Attribution) | `third_party_interference` | A relative interrupts, corrects, or shares their own history |
| Résistance / Stigmate (Nuance) | `resistance` | Patient hides information (smoking, missed pills), reveals later |
| Polysémie & Ambiguïté Sémantique | `semantic_ambiguity` | Context-dependent double-meaning words |
| Incohérence Initiale (Auto-Correction) | `initial_incoherence` | Patient states something wrong early, corrects it later |
| Noms Propres (Entités Nommées) | `named_entities` | Many proper nouns (doctors, pharmacies, cities, relatives) |
| Nonsense Clinique (Cohérence Médicale) | `clinical_nonsense` | A clinically absurd statement the doctor does not challenge |
| Nonsense Total (Filtrage de Bruit Absurde) | `total_nonsense` | A completely unrelated sentence inserted mid-conversation |

All parameters default to **Minimal**. Only specify the ones you want to raise.

### 2. Reference extraction (ground truth)

Extract clinical facts using the frontier model:

```bash
uv run medexaudit get-reference-extract --conversation data/conversations/transcript.txt
```

### 3. Candidate extraction

Extract facts using the model under test:

```bash
uv run medexaudit get-candidate-extract \
  --conversation data/conversations/transcript.txt \
  --model openai/gpt-4o
```

### 4. Audit

Score the candidate against the reference:

```bash
uv run medexaudit audit \
  --reference data/extracts/ref.json \
  --candidate data/extracts/cand.json
```

### 5. Report

Generate a self-contained HTML report with graphics from one or more audits:

```bash
uv run medexaudit report \
  --evals data/audits/audit_a.json \
  --evals data/audits/audit_b.json
```

## Prompts

The three system prompts live in `prompts/` and are fully editable:

| File | Phase | Role |
|---|---|---|
| `prompts/simulator.md` | Simulate | Generates realistic French clinical conversations from a scenario context and 12 complexity parameters (small talk, patient confusion, temporal complexity, etc.). |
| `prompts/extractor.md` | Extract | Extracts atomic clinical facts from a transcript into structured JSON (findings, measurements, substances, etc.) with fields for negation, certainty, timeline, and more. |
| `prompts/auditor.md` | Audit | Scores a candidate extraction against a reference using a penalty-weighted system (critical/major/minor errors) and produces a per-fact audit report with a global accuracy verdict. |

## Project structure

```
prompts/              # Editable prompt templates (simulator, extractor, auditor)
medexaudit/           # Python package
├── __init__.py       # Public API & exports
├── cli.py            # Typer CLI (5 subcommands)
├── llm.py            # LiteLLM wrapper
├── models.py         # Pydantic data models
├── paths.py          # Path constants
├── simulate.py       # Phase 1
├── extract.py        # Phases 2-3
├── audit.py          # Phase 4
├── report.py         # Phase 5
└── templates/        # Jinja2 HTML template
data/                 # Working data
├── scenarios/        # Input scenario files
├── conversations/    # Generated transcripts
├── extracts/         # Extraction JSONs
└── audits/           # Audit JSONs
output/               # Generated HTML reports
```

## Library usage

All five phase functions and key data models are importable directly from `medexaudit`:

```python
from medexaudit import (
    simulate,
    get_reference_extract,
    get_candidate_extract,
    audit,
    report,
    Extraction,
    AuditReport,
)

transcript = simulate("data/scenarios/my_scenario.yaml")
ref = get_reference_extract("data/conversations/transcript.txt")
cand = get_candidate_extract("data/conversations/transcript.txt", model="openai/gpt-4o")
result = audit("data/extracts/ref.json", "data/extracts/cand.json")
report_path = report(["data/audits/audit.json"])
```

Data models (`Extraction`, `AuditReport`, `ClinicalFact`, `Scenario`) and default constants (`DEFAULT_MODEL`, `DEFAULT_TEMPERATURE`, `DEFAULT_MAX_TOKENS`, `DEFAULT_MAX_RETRIES`) are also available at the top level.

## Options

All commands accept `--output` to set a custom output path. Commands in phases 1–4 also accept `--model` to override the LLM.

### LLM parameters

These flags apply to phases 1–4 (commands that call an LLM). The `report` command does not use them.

| Flag | Default | Description |
|---|---|---|
| `--temperature` | `0.7` | LLM sampling temperature |
| `--max-tokens` | `16384` | Maximum tokens for the LLM response |
| `--max-retries` | `3` | Maximum retries on transient LLM errors |

### Model strings

Model strings must use the [LiteLLM format](https://docs.litellm.ai/docs/providers): `provider/model-name`. Examples:

| Provider | Model string | Env var |
|---|---|---|
| Google Gemini | `gemini/gemini-3-pro-preview` | `GEMINI_API_KEY` |
| OpenAI | `openai/gpt-4o` | `OPENAI_API_KEY` |
| Anthropic | `anthropic/claude-sonnet-4-5-20250929` | `ANTHROPIC_API_KEY` |
| Together AI | `together_ai/meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo` | `TOGETHER_API_KEY` |

The `provider/` prefix is **required** — passing a bare model name like `meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo` without the prefix will fail.

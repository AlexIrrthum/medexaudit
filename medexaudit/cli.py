"""Typer CLI for medexaudit."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

import typer
import yaml
from pydantic import ValidationError

from .llm import DEFAULT_MAX_RETRIES, DEFAULT_MAX_TOKENS, DEFAULT_MODEL, DEFAULT_TEMPERATURE

app = typer.Typer(help="medexaudit - Benchmark LLMs on clinical fact extraction")


@contextmanager
def _handle_errors() -> Iterator[None]:
    """Catch common errors and print a friendly one-line message instead of a traceback."""
    try:
        yield
    except FileNotFoundError as e:
        typer.echo(f"Error: file not found: {e.filename or e}", err=True)
        raise typer.Exit(code=1) from None
    except yaml.YAMLError as e:
        typer.echo(f"Error: invalid YAML: {e}", err=True)
        raise typer.Exit(code=1) from None
    except ValidationError as e:
        typer.echo(f"Error: invalid data: {e}", err=True)
        raise typer.Exit(code=1) from None
    except Exception as e:
        typer.echo(f"Error ({type(e).__name__}): {e}", err=True)
        raise typer.Exit(code=1) from None


@app.command()
def simulate(
    scenario: str = typer.Option(..., help="Path to scenario YAML file"),
    model: str = typer.Option(DEFAULT_MODEL, help="Frontier LLM model"),
    output: str | None = typer.Option(None, help="Output path for conversation"),
    temperature: float = typer.Option(DEFAULT_TEMPERATURE, help="LLM sampling temperature"),
    max_tokens: int = typer.Option(DEFAULT_MAX_TOKENS, help="Max tokens for LLM response"),
    max_retries: int = typer.Option(DEFAULT_MAX_RETRIES, help="Max retries on LLM errors"),
) -> None:
    """Phase 1: Generate a clinical conversation transcript from a scenario."""
    with _handle_errors():
        from .simulate import simulate as _simulate

        _simulate(
            scenario_path=scenario,
            model=model,
            output_path=output,
            temperature=temperature,
            max_tokens=max_tokens,
            max_retries=max_retries,
        )
        typer.echo("Conversation generated.")


@app.command()
def get_reference_extract(
    conversation: str = typer.Option(..., help="Path to conversation transcript"),
    model: str = typer.Option(DEFAULT_MODEL, help="Frontier LLM model"),
    output: str | None = typer.Option(None, help="Output path for extract JSON"),
    temperature: float = typer.Option(DEFAULT_TEMPERATURE, help="LLM sampling temperature"),
    max_tokens: int = typer.Option(DEFAULT_MAX_TOKENS, help="Max tokens for LLM response"),
    max_retries: int = typer.Option(DEFAULT_MAX_RETRIES, help="Max retries on LLM errors"),
) -> None:
    """Phase 2: Extract reference (ground truth) clinical facts."""
    with _handle_errors():
        from .extract import get_reference_extract as _get_reference_extract

        result = _get_reference_extract(
            conversation_path=conversation,
            model=model,
            output_path=output,
            temperature=temperature,
            max_tokens=max_tokens,
            max_retries=max_retries,
        )
        typer.echo(f"Reference extraction done: {len(result.facts)} facts.")


@app.command()
def get_candidate_extract(
    conversation: str = typer.Option(..., help="Path to conversation transcript"),
    model: str = typer.Option(..., help="Candidate LLM model (LiteLLM format)"),
    output: str | None = typer.Option(None, help="Output path for extract JSON"),
    temperature: float = typer.Option(DEFAULT_TEMPERATURE, help="LLM sampling temperature"),
    max_tokens: int = typer.Option(DEFAULT_MAX_TOKENS, help="Max tokens for LLM response"),
    max_retries: int = typer.Option(DEFAULT_MAX_RETRIES, help="Max retries on LLM errors"),
) -> None:
    """Phase 3: Extract candidate clinical facts using a specific model."""
    with _handle_errors():
        from .extract import get_candidate_extract as _get_candidate_extract

        result = _get_candidate_extract(
            conversation_path=conversation,
            model=model,
            output_path=output,
            temperature=temperature,
            max_tokens=max_tokens,
            max_retries=max_retries,
        )
        typer.echo(f"Candidate extraction done: {len(result.facts)} facts.")


@app.command()
def audit(
    reference: str = typer.Option(..., help="Path to reference extract JSON"),
    candidate: str = typer.Option(..., help="Path to candidate extract JSON"),
    model: str = typer.Option(DEFAULT_MODEL, help="Judge LLM model"),
    output: str | None = typer.Option(None, help="Output path for audit JSON"),
    temperature: float = typer.Option(DEFAULT_TEMPERATURE, help="LLM sampling temperature"),
    max_tokens: int = typer.Option(DEFAULT_MAX_TOKENS, help="Max tokens for LLM response"),
    max_retries: int = typer.Option(DEFAULT_MAX_RETRIES, help="Max retries on LLM errors"),
) -> None:
    """Phase 4: Audit candidate extraction against reference."""
    with _handle_errors():
        from .audit import audit as _audit

        result = _audit(
            reference_path=reference,
            candidate_path=candidate,
            model=model,
            output_path=output,
            temperature=temperature,
            max_tokens=max_tokens,
            max_retries=max_retries,
        )
        typer.echo(
            f"Audit done: accuracy={result.final_metrics.global_accuracy_score:.1f}%, "
            f"verdict={result.final_metrics.verdict}"
        )


@app.command()
def report(
    evals: list[str] = typer.Option(..., help="Paths to audit JSON files"),
    output: str | None = typer.Option(None, help="Output path for HTML report"),
) -> None:
    """Phase 5: Generate HTML report from audit files."""
    with _handle_errors():
        from .report import report as _report

        path = _report(audit_paths=evals, output_path=output)
        typer.echo(f"Report generated: {path}")

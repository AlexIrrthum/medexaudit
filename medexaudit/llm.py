"""Thin LiteLLM wrapper for medexaudit."""

from __future__ import annotations

import json
import re
import time
from typing import TypeVar

import litellm
from pydantic import BaseModel, ValidationError

from .paths import PROMPTS_DIR

DEFAULT_MODEL = "gemini/gemini-3-pro-preview"
DEFAULT_TEMPERATURE = 0.7
DEFAULT_MAX_RETRIES = 3
DEFAULT_MAX_TOKENS = 16_384

T = TypeVar("T", bound=BaseModel)


def load_prompt(prompt_name: str) -> str:
    """Load a prompt from prompts/ directory.

    E.g. load_prompt('simulator') reads prompts/simulator.md
    """
    path = PROMPTS_DIR / f"{prompt_name}.md"
    return path.read_text(encoding="utf-8")


def call_llm(
    model: str,
    system_prompt: str,
    user_prompt: str,
    response_model: type[T] | None = None,
    temperature: float = DEFAULT_TEMPERATURE,
    max_retries: int = DEFAULT_MAX_RETRIES,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> str | T:
    """Call an LLM via LiteLLM.

    If response_model is provided, use JSON mode + validate with Pydantic.
    Retries on transient errors with exponential backoff.
    Returns parsed Pydantic model or raw string.
    """
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    kwargs: dict = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    if response_model is not None:
        kwargs["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": response_model.__name__,
                "schema": response_model.model_json_schema(),
            },
        }

    last_error: Exception | None = None
    for attempt in range(max_retries):
        try:
            response = litellm.completion(**kwargs)
            content = response.choices[0].message.content

            if response_model is None:
                return content

            # Strip reasoning/thinking blocks from reasoning models.
            content = re.sub(r"<think>.*?</think>", "", content, flags=re.DOTALL).strip()
            # Strip markdown fences that some models wrap around JSON.
            content = re.sub(r"^```(?:json)?\s*\n", "", content)
            content = re.sub(r"\n```\s*$", "", content)

            result = response_model.model_validate_json(content)

            # Reasoning models (Kimi, DeepSeek-R1, etc.) combined with
            # response_format constraints tend to produce technically-
            # valid but empty results — the model satisfies the schema
            # with minimal output instead of doing the actual task.
            # Detect this and retry without response_format, prompting
            # for JSON instead.
            is_reasoning = getattr(
                response.choices[0].message, "reasoning_content", None
            )
            if is_reasoning and _is_empty_result(result):
                _switch_to_prompt_json(kwargs, response_model)
                continue

            return result

        except litellm.UnsupportedParamsError:
            _switch_to_prompt_json(kwargs, response_model)
            continue

        except (json.JSONDecodeError, ValidationError, litellm.exceptions.APIError) as e:
            last_error = e
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise

    if last_error is not None:
        raise last_error
    raise RuntimeError(
        f"call_llm: {max_retries} attempts exhausted — model returned empty results"
    )


def _switch_to_prompt_json(kwargs: dict, response_model: type[BaseModel]) -> None:
    """Drop response_format and append the JSON schema to the prompt."""
    if "response_format" not in kwargs:
        return
    kwargs.pop("response_format")
    kwargs["messages"][-1]["content"] += (
        "\n\nRespond with ONLY valid JSON matching this schema, "
        "no markdown fences:\n"
        + json.dumps(response_model.model_json_schema(), indent=2)
    )


def _is_empty_result(result: BaseModel) -> bool:
    """Check if a parsed result is structurally valid but has no data."""
    return all(
        not value for value in result.model_dump().values()
        if isinstance(value, (list, dict))
    )

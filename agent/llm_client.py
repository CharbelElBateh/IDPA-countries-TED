"""LLM client — litellm wrapper with .env loading and model config."""

import os
from pathlib import Path

from dotenv import load_dotenv
import litellm

from agent.config import DEFAULT_MODEL

# Load .env from project root
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)

# Suppress litellm's verbose logging
litellm.suppress_debug_info = True
litellm.set_verbose = False


def get_available_models() -> list[str]:
    """Return list of models that have API keys configured."""
    models = []
    if os.environ.get("OPENAI_API_KEY"):
        models.extend(["gpt-4o", "gpt-4o-mini"])
    if os.environ.get("ANTHROPIC_API_KEY"):
        models.extend(["anthropic/claude-sonnet-4-20250514", "anthropic/claude-haiku-4-5-20251001"])
    if os.environ.get("OPENAI_API_BASE"):
        models.append("openai/local")
    if not models:
        # Fallback — let user try anyway
        models.append(DEFAULT_MODEL)
    return models


def completion(model: str, messages: list[dict], tools: list[dict] | None = None, stream: bool = False):
    """Call litellm.completion with standard settings."""
    kwargs = {
        "model": model,
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 4096,
        "stream": stream,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    return litellm.completion(**kwargs)

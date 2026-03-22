"""LLM client — OpenAI + Anthropic SDK support with unified streaming interface.

Detects provider from model name and adapts the Anthropic API to match
OpenAI's streaming chunk format so core.py needs no changes.
"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root
_env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_env_path)

# Lazy-initialized clients
_openai_client = None
_anthropic_client = None


def _get_openai():
    global _openai_client
    if _openai_client is None:
        from openai import OpenAI
        _openai_client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))
    return _openai_client


def _get_anthropic():
    global _anthropic_client
    if _anthropic_client is None:
        from anthropic import Anthropic
        _anthropic_client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
    return _anthropic_client


def _is_anthropic(model: str) -> bool:
    return "claude" in model.lower()


def _strip_provider_prefix(model: str) -> str:
    """Remove 'anthropic/' or 'openai/' prefix if present."""
    for prefix in ("anthropic/", "openai/"):
        if model.startswith(prefix):
            return model[len(prefix):]
    return model


def get_available_models() -> list[str]:
    """Return list of models that have API keys configured."""
    models = []
    if os.environ.get("OPENAI_API_KEY"):
        models.extend(["gpt-4o", "gpt-4o-mini"])
    if os.environ.get("ANTHROPIC_API_KEY"):
        models.extend(["claude-sonnet-4-20250514", "claude-haiku-4-5-20251001"])
    if not models:
        models.append("gpt-4o")
    return models


# ── OpenAI-compatible chunk wrappers (for Anthropic adapter) ─────────────────

class _Function:
    def __init__(self, name=None, arguments=None):
        self.name = name
        self.arguments = arguments


class _ToolCall:
    def __init__(self, index, id=None, function=None):
        self.index = index
        self.id = id
        self.function = function or _Function()


class _Delta:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls


class _Choice:
    def __init__(self, delta=None):
        self.delta = delta or _Delta()


class _Chunk:
    def __init__(self, choices=None):
        self.choices = choices or [_Choice()]


# ── Anthropic → OpenAI format converters ─────────────────────────────────────

def _convert_tools_for_anthropic(tools: list[dict]) -> list[dict]:
    """Convert OpenAI tool schemas to Anthropic format."""
    result = []
    for tool in tools:
        func = tool["function"]
        result.append({
            "name": func["name"],
            "description": func.get("description", ""),
            "input_schema": func.get("parameters", {"type": "object", "properties": {}}),
        })
    return result


def _convert_messages_for_anthropic(messages: list[dict]) -> tuple[str, list[dict]]:
    """Extract system prompt and convert messages to Anthropic format.

    Returns (system_text, converted_messages).
    """
    system_text = ""
    converted = []

    for msg in messages:
        role = msg.get("role")

        if role == "system":
            system_text = msg["content"]
            continue

        if role == "assistant":
            content_blocks = []
            if msg.get("content"):
                content_blocks.append({"type": "text", "text": msg["content"]})
            if msg.get("tool_calls"):
                for tc in msg["tool_calls"]:
                    fn = tc["function"]
                    try:
                        input_data = json.loads(fn["arguments"]) if fn["arguments"] else {}
                    except json.JSONDecodeError:
                        input_data = {}
                    content_blocks.append({
                        "type": "tool_use",
                        "id": tc["id"],
                        "name": fn["name"],
                        "input": input_data,
                    })
            converted.append({"role": "assistant", "content": content_blocks or msg.get("content", "")})
            continue

        if role == "tool":
            # Anthropic: tool results go as user messages with tool_result blocks.
            # Merge consecutive tool messages into one user message.
            tool_block = {
                "type": "tool_result",
                "tool_use_id": msg["tool_call_id"],
                "content": msg["content"],
            }
            # Check if previous converted message is already a user tool_result group
            if converted and converted[-1]["role"] == "user" and isinstance(converted[-1]["content"], list):
                last_types = {b.get("type") for b in converted[-1]["content"]}
                if "tool_result" in last_types:
                    converted[-1]["content"].append(tool_block)
                    continue
            converted.append({"role": "user", "content": [tool_block]})
            continue

        # Regular user message
        converted.append({"role": role, "content": msg.get("content", "")})

    return system_text, converted


def _stream_anthropic(model: str, messages: list[dict], tools: list[dict] | None = None):
    """Stream from Anthropic and yield OpenAI-compatible chunks."""
    client = _get_anthropic()
    system_text, conv_messages = _convert_messages_for_anthropic(messages)

    kwargs = {
        "model": _strip_provider_prefix(model),
        "messages": conv_messages,
        "max_tokens": 4096,
        "system": system_text,
    }
    if tools:
        kwargs["tools"] = _convert_tools_for_anthropic(tools)

    tool_index_map = {}  # block_index -> sequential tool index
    next_tool_idx = 0

    with client.messages.stream(**kwargs) as stream:
        for event in stream:
            if event.type == "content_block_start":
                block = event.content_block
                if block.type == "tool_use":
                    idx = next_tool_idx
                    tool_index_map[event.index] = idx
                    next_tool_idx += 1
                    tc = _ToolCall(index=idx, id=block.id, function=_Function(name=block.name, arguments=""))
                    yield _Chunk([_Choice(_Delta(tool_calls=[tc]))])

            elif event.type == "content_block_delta":
                delta = event.delta
                if delta.type == "text_delta":
                    yield _Chunk([_Choice(_Delta(content=delta.text))])
                elif delta.type == "input_json_delta":
                    idx = tool_index_map.get(event.index, 0)
                    tc = _ToolCall(index=idx, function=_Function(arguments=delta.partial_json))
                    yield _Chunk([_Choice(_Delta(tool_calls=[tc]))])


# ── Unified completion function ──────────────────────────────────────────────

def completion(model: str, messages: list[dict], tools: list[dict] | None = None, stream: bool = False):
    """Route to OpenAI or Anthropic based on model name."""
    if _is_anthropic(model):
        if stream:
            return _stream_anthropic(model, messages, tools)
        # Non-streaming not used by agent loop, but handle it
        return _stream_anthropic(model, messages, tools)

    # OpenAI path
    client = _get_openai()
    kwargs = {
        "model": _strip_provider_prefix(model),
        "messages": messages,
        "temperature": 0.3,
        "max_tokens": 4096,
        "stream": stream,
    }
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"
    return client.chat.completions.create(**kwargs)
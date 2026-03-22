"""Agent core — tool-calling loop with streaming support."""

import json
from typing import Generator

from agent.config import MAX_TOOL_ITERATIONS
from agent.llm_client import completion
from agent.tools import TOOL_SCHEMAS, dispatch
from agent.system_prompt import build_system_prompt


def run_agent_stream(
    model: str,
    messages: list[dict],
) -> Generator[dict, None, list[dict]]:
    """Run the agent loop, yielding SSE-compatible events.

    Yields dicts with keys:
        - {"type": "token", "content": "..."}
        - {"type": "tool_start", "name": "...", "arguments": {...}}
        - {"type": "tool_end", "name": "...", "result": "..."}
        - {"type": "done", "messages": [...]}
        - {"type": "error", "message": "..."}

    Returns the final messages list.
    """
    # Ensure system prompt is present
    if not messages or messages[0].get("role") != "system":
        messages.insert(0, {"role": "system", "content": build_system_prompt()})

    for iteration in range(MAX_TOOL_ITERATIONS):
        try:
            response = completion(
                model=model,
                messages=messages,
                tools=TOOL_SCHEMAS,
                stream=True,
            )
        except Exception as e:
            yield {"type": "error", "message": f"LLM call failed: {e}"}
            return messages

        # Accumulate streamed response
        content_chunks = []
        tool_calls_acc = {}  # index -> {id, name, arguments_str}

        for chunk in response:
            delta = chunk.choices[0].delta if chunk.choices else None
            if not delta:
                continue

            # Text content
            if delta.content:
                content_chunks.append(delta.content)
                yield {"type": "token", "content": delta.content}

            # Tool calls (streamed in pieces)
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tool_calls_acc:
                        tool_calls_acc[idx] = {
                            "id": tc.id or "",
                            "name": "",
                            "arguments": "",
                        }
                    if tc.id:
                        tool_calls_acc[idx]["id"] = tc.id
                    if tc.function:
                        if tc.function.name:
                            tool_calls_acc[idx]["name"] = tc.function.name
                        if tc.function.arguments:
                            tool_calls_acc[idx]["arguments"] += tc.function.arguments

        full_content = "".join(content_chunks)
        tool_calls = list(tool_calls_acc.values()) if tool_calls_acc else []

        if not tool_calls:
            # No tool calls — final text response
            if full_content:
                messages.append({"role": "assistant", "content": full_content})
            yield {"type": "done"}
            return messages

        # Build assistant message with tool_calls
        assistant_msg = {
            "role": "assistant",
            "content": full_content or None,
            "tool_calls": [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": tc["arguments"],
                    },
                }
                for tc in tool_calls
            ],
        }
        messages.append(assistant_msg)

        # Execute each tool call
        for tc in tool_calls:
            name = tc["name"]
            try:
                args = json.loads(tc["arguments"]) if tc["arguments"] else {}
            except json.JSONDecodeError:
                args = {}

            yield {"type": "tool_start", "name": name, "arguments": args}

            result = dispatch(name, args)

            yield {"type": "tool_end", "name": name, "result": result}

            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "name": name,
                "content": result,
            })

        # Continue loop — LLM will see tool results and respond

    # Hit max iterations
    yield {"type": "error", "message": f"Agent reached maximum iterations ({MAX_TOOL_ITERATIONS})."}
    return messages


def run_agent_sync(model: str, messages: list[dict]) -> tuple[str, list[dict]]:
    """Run the agent loop synchronously. Returns (final_text, messages)."""
    final_text = ""
    for event in run_agent_stream(model, messages):
        if event["type"] == "token":
            final_text += event["content"]
        elif event["type"] == "done":
            break
        elif event["type"] == "error":
            final_text += f"\n\n**Error**: {event['message']}"
            break
    return final_text, messages

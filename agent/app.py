"""Flask server — API routes + SSE streaming + serves static chat UI."""

import json
import sys
import argparse
from pathlib import Path

from flask import Flask, request, jsonify, Response, stream_with_context, send_from_directory

import agent.config as cfg
from agent.core import run_agent_stream
from agent.persistence import (
    generate_id, generate_title, save_chat, load_chat, list_chats, delete_chat,
)
from agent.llm_client import get_available_models
from agent.system_prompt import build_system_prompt

# Ensure project root is on sys.path for src/ imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

app = Flask(__name__, static_folder="static")


# ── Static UI ─────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


# ── Chat API ──────────────────────────────────────────────────────────────────

@app.route("/api/chat", methods=["POST"])
def chat():
    """Start or continue a chat. Returns SSE stream."""
    data = request.get_json()
    if not data or "message" not in data:
        return jsonify({"error": "Missing 'message' field"}), 400

    user_message = data["message"]
    chat_id = data.get("chat_id")
    model = data.get("model", cfg.DEFAULT_MODEL)

    # Load or create chat
    if chat_id:
        chat_data = load_chat(chat_id)
        if chat_data:
            messages = chat_data["messages"]
            title = chat_data["title"]
        else:
            messages = [{"role": "system", "content": build_system_prompt()}]
            title = generate_title(user_message)
    else:
        chat_id = generate_id()
        messages = [{"role": "system", "content": build_system_prompt()}]
        title = generate_title(user_message)

    # Add user message
    messages.append({"role": "user", "content": user_message})

    def generate():
        """SSE event generator."""
        # Send chat_id first so client can track it
        yield f"event: chat_id\ndata: {json.dumps({'chat_id': chat_id, 'title': title})}\n\n"

        assistant_text = ""

        for event in run_agent_stream(model, messages):
            if event["type"] == "token":
                assistant_text += event["content"]
                yield f"event: token\ndata: {json.dumps({'content': event['content']})}\n\n"

            elif event["type"] == "tool_start":
                yield f"event: tool_start\ndata: {json.dumps({'name': event['name'], 'arguments': event['arguments']})}\n\n"

            elif event["type"] == "tool_end":
                # Truncate large results for SSE
                result = event["result"]
                if len(result) > 5000:
                    result = result[:5000] + "... (truncated)"
                yield f"event: tool_end\ndata: {json.dumps({'name': event['name'], 'result': result})}\n\n"

            elif event["type"] == "error":
                yield f"event: error\ndata: {json.dumps({'message': event['message']})}\n\n"

            elif event["type"] == "done":
                # Save chat
                save_chat(chat_id, title, model, messages)
                yield f"event: done\ndata: {json.dumps({'chat_id': chat_id})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── Chat management ───────────────────────────────────────────────────────────

@app.route("/api/chats", methods=["GET"])
def get_chats():
    return jsonify(list_chats())


@app.route("/api/chats/<chat_id>", methods=["GET"])
def get_chat(chat_id):
    data = load_chat(chat_id)
    if data is None:
        return jsonify({"error": "Chat not found"}), 404
    return jsonify(data)


@app.route("/api/chats/<chat_id>", methods=["DELETE"])
def remove_chat(chat_id):
    if delete_chat(chat_id):
        return jsonify({"ok": True})
    return jsonify({"error": "Chat not found"}), 404


# ── Models ────────────────────────────────────────────────────────────────────

@app.route("/api/models", methods=["GET"])
def get_models():
    available = get_available_models()
    return jsonify({
        "default": cfg.DEFAULT_MODEL,
        "presets": cfg.MODEL_PRESETS,
        "available": available,
    })


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="IDPA Agent Chat Server")
    parser.add_argument("--model", default=cfg.DEFAULT_MODEL, help=f"Default LLM model (default: {cfg.DEFAULT_MODEL})")
    parser.add_argument("--port", type=int, default=5000, help="Port to listen on (default: 5000)")
    parser.add_argument("--host", default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)")
    parser.add_argument("--debug", action="store_true", help="Enable Flask debug mode")
    args = parser.parse_args()

    # Override default model
    cfg.DEFAULT_MODEL = args.model

    print(f"Starting IDPA Agent Chat Server")
    print(f"  Model: {args.model}")
    print(f"  URL:   http://{args.host}:{args.port}")
    print()

    app.run(host=args.host, port=args.port, debug=args.debug, threaded=True)


if __name__ == "__main__":
    main()

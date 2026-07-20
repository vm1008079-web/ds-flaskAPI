from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any


def export_chat_to_markdown(chat: dict[str, Any], destination: Path) -> Path:
    prompt = chat.get("prompt", "")
    think = chat.get("think", "")
    response = chat.get("response", "")
    ref_file_ids = chat.get("ref_file_ids", [])
    created = chat.get("created_at", "")
    session_id = chat.get("session_id", "")

    body = [
        f"# Conversación DeepSeek\n",
        f"**Session ID:** `{session_id}`\n",
        f"**Creado:** {created}\n",
        f"**Archivos referenciados:** {', '.join(ref_file_ids) if ref_file_ids else 'ninguno'}\n",
        "---\n",
        "## Prompt\n",
        prompt,
        "\n---\n",
        "## Pensamiento\n",
        think,
        "\n---\n",
        "## Respuesta\n",
        response,
        "\n",
    ]
    destination.write_text("\n".join(body), encoding="utf-8")
    return destination


def export_chat_to_html(chat: dict[str, Any], destination: Path) -> Path:
    prompt = escape(chat.get("prompt", ""))
    think = escape(chat.get("think", ""))
    response = escape(chat.get("response", ""))
    ref_file_ids = chat.get("ref_file_ids", [])
    created = chat.get("created_at", "")
    session_id = chat.get("session_id", "")

    html = f"""
<!DOCTYPE html>
<html lang=\"es\">
<head>
  <meta charset=\"UTF-8\">
  <title>Conversación DeepSeek</title>
  <style>
    body {{ font-family: sans-serif; margin: 24px; line-height: 1.5; }}
    pre {{ background: #f5f5f5; padding: 16px; border-radius: 8px; white-space: pre-wrap; word-break: break-word; }}
    h1,h2 {{ color: #2b2b2b; }}
  </style>
</head>
<body>
  <h1>Conversación DeepSeek</h1>
  <p><strong>Session ID:</strong> <code>{session_id}</code></p>
  <p><strong>Creado:</strong> {created}</p>
  <p><strong>Archivos referenciados:</strong> {', '.join(ref_file_ids) if ref_file_ids else 'ninguno'}</p>
  <hr>
  <h2>Prompt</h2>
  <pre>{prompt}</pre>
  <h2>Pensamiento</h2>
  <pre>{think}</pre>
  <h2>Respuesta</h2>
  <pre>{response}</pre>
</body>
</html>
"""
    destination.write_text(html, encoding="utf-8")
    return destination

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from json.decoder import JSONDecodeError

from .errors import StorageError

class ChatStorage:
    def __init__(self, login_dir: Path = Path(".login")):
        self.chat_dir = login_dir / "chats"
        self.chat_dir.mkdir(parents=True, exist_ok=True)

    def _get_chat_file_for_session(self, session_id: str) -> Optional[Path]:
        """
        Busca un archivo existente para esta sesión.
        Primero intenta por nombre corto (primeros 6 caracteres), luego por contenido.
        """
        # 1. Intentar por nombre corto (chat-XXXXXX.md)
        short_id = session_id[:6]
        short_path = self.chat_dir / f"chat-{short_id}.md"
        if short_path.exists():
            # Verificar que el contenido corresponda a esta sesión
            try:
                data = self._parse_chat_file(short_path)
                if data.get("session_id") == session_id:
                    return short_path
            except:
                pass

        # 2. Buscar por contenido (para archivos con nombres personalizados o antiguos)
        for path in sorted(self.chat_dir.glob("chat-*.md")) + sorted(self.chat_dir.glob("chat-*.json")):
            try:
                data = self._parse_chat_file(path)
                if data.get("session_id") == session_id:
                    return path
            except:
                continue

        return None

    def _generate_unique_filename(self, base_name: str) -> str:
        """Genera un nombre de archivo único en el directorio."""
        path = self.chat_dir / f"{base_name}.md"
        if not path.exists():
            return f"{base_name}.md"

        # Si ya existe, añadir sufijo numérico
        counter = 1
        while True:
            new_name = f"{base_name}_{counter}.md"
            if not (self.chat_dir / new_name).exists():
                return new_name
            counter += 1

    def save_or_update_chat(
        self,
        session_id: str,
        prompt: str,
        think: str,
        response: str,
        ref_file_ids: list[str],
        parent_message_id: Optional[str] = None,
    ) -> str:
        """
        Guarda o actualiza el archivo de la sesión.
        Usa un nombre corto (primeros 6 caracteres del session_id) para el archivo.
        """
        now = datetime.now(timezone.utc)
        timestamp = now.isoformat()
        new_entry = {
            "timestamp": timestamp,
            "prompt": prompt,
            "think": think,
            "response": response,
            "ref_file_ids": ref_file_ids,
            "parent_message_id": parent_message_id,
        }

        # Buscar archivo existente para esta sesión
        existing_path = self._get_chat_file_for_session(session_id)

        if existing_path is None:
            # Crear nuevo archivo con nombre corto
            short_id = session_id[:6]
            file_name = self._generate_unique_filename(f"chat-{short_id}")
            path = self.chat_dir / file_name
            data = {
                "session_id": session_id,
                "created_at": timestamp,
                "history": [new_entry],
            }
        else:
            # Actualizar archivo existente
            if existing_path.suffix == ".json":
                path = existing_path.with_suffix(".md")
            else:
                path = existing_path
            try:
                data = self._parse_chat_file(path)
                # Migrar formato antiguo si es necesario
                if "prompt" in data and "response" in data:
                    old_entry = {
                        "timestamp": data.get("created_at", timestamp),
                        "prompt": data.get("prompt", ""),
                        "think": data.get("think", ""),
                        "response": data.get("response", ""),
                        "ref_file_ids": data.get("ref_file_ids", []),
                        "parent_message_id": data.get("parent_message_id"),
                    }
                    data = {
                        "session_id": session_id,
                        "created_at": data.get("created_at", timestamp),
                        "history": [old_entry],
                    }
                data["history"].append(new_entry)
            except (JSONDecodeError, KeyError) as e:
                logging.exception("Corrupt chat file, overwriting: %s", path)
                data = {
                    "session_id": session_id,
                    "created_at": timestamp,
                    "history": [new_entry],
                }

        try:
            markdown = self._render_chat_markdown(data)
            path.write_text(markdown, encoding="utf-8")
        except OSError as e:
            logging.exception("Failed to write chat file %s: %s", path, e)
            raise StorageError(f"Failed to save chat to {path}") from e

        return path.name

    def list_chats(self) -> list[dict[str, Any]]:
        """Lista todos los chats guardados (formato nuevo y antiguo)."""
        results: list[dict[str, Any]] = []
        for path in sorted(self.chat_dir.glob("chat-*.md")) + sorted(self.chat_dir.glob("chat-*.json")):
            try:
                data = self._parse_chat_file(path)
                session_id = data.get("session_id", "")
                created_at = data.get("created_at", "")
                if "history" in data and data["history"]:
                    first = data["history"][0]
                    prompt = first.get("prompt", "")[:120]
                else:
                    prompt = data.get("prompt", "")[:120]
                results.append({
                    "file_name": path.name,
                    "session_id": session_id,
                    "created_at": created_at,
                    "prompt": prompt,
                    "ref_file_ids": [],
                })
            except (JSONDecodeError, OSError) as e:
                logging.warning("Skipping corrupt chat file %s: %s", path, e)
                corrupt_dir = self.chat_dir / "corrupt"
                corrupt_dir.mkdir(parents=True, exist_ok=True)
                try:
                    path.replace(corrupt_dir / path.name)
                except Exception:
                    logging.exception("Failed to move corrupt file %s", path)
                continue
        return results

    def load_chat(self, file_name: str) -> dict[str, Any]:
        """Carga un chat completo (formato nuevo o antiguo) y lo normaliza."""
        path = self.chat_dir / file_name
        if not path.exists():
            raise FileNotFoundError(f"Chat file not found: {path}")
        try:
            data = self._parse_chat_file(path)
        except JSONDecodeError as e:
            logging.exception("Chat file is corrupt: %s", path)
            raise StorageError(f"Chat file is corrupt: {path}") from e
        except OSError as e:
            logging.exception("Failed to read chat file: %s", path)
            raise StorageError(f"Failed to read chat file: {path}") from e

        # Normalizar a formato nuevo si es antiguo
        if "prompt" in data and "response" in data:
            old_entry = {
                "timestamp": data.get("created_at", ""),
                "prompt": data.get("prompt", ""),
                "think": data.get("think", ""),
                "response": data.get("response", ""),
                "ref_file_ids": data.get("ref_file_ids", []),
                "parent_message_id": data.get("parent_message_id"),
            }
            data = {
                "session_id": data.get("session_id", ""),
                "created_at": data.get("created_at", ""),
                "history": [old_entry],
            }
        return data

    def _parse_chat_file(self, path: Path) -> dict[str, Any]:
        text = path.read_text(encoding="utf-8")
        if path.suffix == ".md":
            return self._parse_chat_markdown(text)
        return json.loads(text)

    def _parse_chat_markdown(self, text: str) -> dict[str, Any]:
        header = {}
        body = text
        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                raw_header = parts[1].strip()
                body = parts[2]
                for line in raw_header.splitlines():
                    if ":" in line:
                        key, value = line.split(":", 1)
                        header[key.strip()] = value.strip()

        history: list[dict[str, Any]] = []
        import re

        pattern = re.compile(r"^## Turno \d+\s*$", flags=re.MULTILINE)
        matches = list(pattern.finditer(body))
        sections = []
        for idx, match in enumerate(matches):
            start = match.end()
            end = matches[idx + 1].start() if idx + 1 < len(matches) else len(body)
            sections.append(body[start:end].strip())

        for section in sections:
            prompt = ""
            think = ""
            response = ""
            lines = section.splitlines()
            current = None
            buffer: list[str] = []

            def flush_current() -> None:
                nonlocal prompt, think, response, current, buffer
                text_block = "\n".join(line.rstrip() for line in buffer).strip()
                if current == "Tú":
                    prompt = text_block
                elif current == "Pensamiento":
                    think = text_block
                elif current == "DeepSeek":
                    response = text_block
                buffer = []

            for line in lines:
                stripped = line.strip()
                if stripped.startswith("**Tú:**"):
                    if current:
                        flush_current()
                    current = "Tú"
                    buffer = []
                    continue
                if stripped.startswith("**Pensamiento:**"):
                    if current:
                        flush_current()
                    current = "Pensamiento"
                    buffer = []
                    continue
                if stripped.startswith("**DeepSeek:**"):
                    if current:
                        flush_current()
                    current = "DeepSeek"
                    buffer = []
                    continue
                if current is not None:
                    buffer.append(line)
            if current:
                flush_current()
            history.append({
                "timestamp": "",
                "prompt": prompt,
                "think": think,
                "response": response,
                "ref_file_ids": [],
                "parent_message_id": None,
            })

        return {
            "session_id": header.get("session_id", ""),
            "created_at": header.get("created_at", ""),
            "history": history,
        }

    def _render_chat_markdown(self, data: dict[str, Any]) -> str:
        lines = [
            "---",
            f"session_id: {data.get('session_id', '')}",
            f"created_at: {data.get('created_at', '')}",
            "---",
            "",
            "# Conversación DeepSeek",
            "",
        ]
        for idx, entry in enumerate(data.get("history", []), start=1):
            lines.extend([
                f"## Turno {idx}",
                "",
                "**Tú:**",
                entry.get("prompt", ""),
                "",
            ])
            if entry.get("think"):
                lines.extend([
                    "**Pensamiento:**",
                    entry.get("think", ""),
                    "",
                ])
            lines.extend([
                "**DeepSeek:**",
                entry.get("response", ""),
                "",
            ])
        return "\n".join(lines)

from __future__ import annotations

import base64
import json
import struct
import time
import threading
import logging
from pathlib import Path
from typing import Optional

import wasmtime
import requests

from .errors import PoWLoadError, PoWChallengeError, PoWSolverError

WASM_URL = "https://fe-static.deepseek.com/chat/static/sha3_wasm_bg.7b9ca65ddd.wasm"
WASM_PATH = Path(__file__).resolve().parent / "sha3_wasm_bg.wasm"
DEFAULT_TIMEOUT = 8  # segundos

logger = logging.getLogger(__name__)


class DeepSeekPow:
    _wasm_module = None  # clase para compartir entre instancias
    _lock = threading.Lock()

    def __init__(self, wasm_path: Path = WASM_PATH, timeout: int = DEFAULT_TIMEOUT):
        self.wasm_path = wasm_path
        self.timeout = timeout
        self._ensure_wasm()
        self._store = None
        self._inst = None
        self._memory = None
        self._solve = None
        self._malloc = None
        self._add_to_stack = None
        self._pow_cache: dict[str, tuple[int, float]] = {}  # cache de respuestas
        self._load_wasm()

    def _ensure_wasm(self) -> None:
        """Descarga el WASM si no existe localmente."""
        if self.wasm_path.exists():
            return
        logger.info("Descargando WASM desde %s", WASM_URL)
        try:
            resp = requests.get(WASM_URL, timeout=30)
            resp.raise_for_status()
            self.wasm_path.write_bytes(resp.content)
            logger.info("WASM descargado correctamente (%d bytes)", len(resp.content))
        except Exception as e:
            raise PoWLoadError(f"No se pudo descargar el WASM: {e}") from e

    def _load_wasm(self) -> None:
        """Carga el módulo WASM y extrae las exportaciones necesarias."""
        try:
            self._store = wasmtime.Store()
            module = wasmtime.Module.from_file(self._store.engine, str(self.wasm_path))
            self._inst = wasmtime.Instance(self._store, module, [])
            exports = self._inst.exports(self._store)
            # Obtener funciones necesarias
            self._memory = exports["memory"]
            self._solve = exports["wasm_solve"]
            # Las siguientes pueden tener nombres alternativos; intentamos varios
            for name in ["__wbindgen_export_0", "malloc", "_malloc"]:
                if name in exports:
                    self._malloc = exports[name]
                    break
            for name in ["__wbindgen_add_to_stack_pointer", "add_to_stack_pointer"]:
                if name in exports:
                    self._add_to_stack = exports[name]
                    break
            if None in (self._malloc, self._add_to_stack):
                raise PoWLoadError("No se encontraron las exportaciones necesarias en el WASM")
        except Exception as e:
            logger.exception("Error al cargar el WASM")
            raise PoWLoadError(f"No se pudo cargar el WASM: {e}") from e

    def _write_str(self, text: str) -> tuple[int, int]:
        data = text.encode("utf-8")
        ptr = self._malloc(self._store, len(data), 1)
        base = self._memory.data_ptr(self._store)
        for i, b in enumerate(data):
            base[ptr + i] = b
        return ptr, len(data)

    def solve(self, challenge: str, prefix: str, difficulty: float, timeout: Optional[int] = None) -> Optional[int]:
        """Resuelve el PoW con timeout."""
        if timeout is None:
            timeout = self.timeout

        # Verificar caché
        cache_key = f"{prefix}_{challenge}"
        if cache_key in self._pow_cache:
            answer, expire_at = self._pow_cache[cache_key]
            if time.time() < expire_at:
                return answer

        # Preparar el solver en un hilo
        result = [None]
        error = [None]

        def target():
            try:
                retptr = self._add_to_stack(self._store, -16)
                try:
                    c_ptr, c_len = self._write_str(challenge)
                    p_ptr, p_len = self._write_str(prefix)
                    self._solve(
                        self._store,
                        retptr,
                        c_ptr,
                        c_len,
                        p_ptr,
                        p_len,
                        float(difficulty),
                    )
                    mem = self._memory.data_ptr(self._store)
                    status = struct.unpack("<i", bytes(mem[retptr:retptr + 4]))[0]
                    value = struct.unpack("<d", bytes(mem[retptr + 8:retptr + 16]))[0]
                finally:
                    self._add_to_stack(self._store, 16)

                if status == 0:
                    result[0] = None
                else:
                    result[0] = int(value)
            except Exception as e:
                error[0] = e

        thread = threading.Thread(target=target, daemon=True)
        thread.start()
        thread.join(timeout)
        if thread.is_alive():
            raise PoWSolverError(f"El solver excedió el tiempo límite de {timeout}s")
        if error[0]:
            raise error[0]
        return result[0]

    def make_header(self, challenge: dict, timeout: Optional[int] = None) -> str:
        required = ("salt", "expire_at", "challenge", "difficulty", "signature", "algorithm", "target_path")
        for key in required:
            if key not in challenge:
                raise PoWChallengeError(f"Falta campo en challenge: {key}")

        expire_at = challenge["expire_at"] / 1000.0
        if time.time() + 2 > expire_at:
            raise PoWChallengeError("El challenge expira pronto, abortando resolución")

        prefix = f"{challenge['salt']}_{challenge['expire_at']}_"
        answer = self.solve(challenge["challenge"], prefix, challenge["difficulty"], timeout)
        if answer is None:
            raise PoWChallengeError("No se obtuvo respuesta del solver (¿challenge expirado?)")

        # Cachear la respuesta hasta el expire_at
        cache_key = f"{prefix}_{challenge['challenge']}"
        self._pow_cache[cache_key] = (answer, expire_at)

        payload = {
            "algorithm": challenge["algorithm"],
            "challenge": challenge["challenge"],
            "salt": challenge["salt"],
            "answer": answer,
            "signature": challenge["signature"],
            "target_path": challenge["target_path"],
        }
        raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        return base64.b64encode(raw).decode("utf-8")
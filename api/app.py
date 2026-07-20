"""
Wrapper del cliente DeepSeek con gestión de sesiones y archivos.
Importa el motor desde la carpeta deepseekcli.
"""

import sys
import os
from pathlib import Path
from typing import Optional, Generator
from queue import Queue
import threading
import logging

# ============================================================
#  IMPORTACIÓN ROBUSTA DE DEEPSEEKCLI
# ============================================================
# Intentar diferentes formas de encontrar deepseekcli

# Opción 1: Buscar en la raíz del proyecto (subiendo 2 niveles desde api/services)
ROOT_DIR = Path(__file__).parent.parent.parent  # api/services -> api -> raíz
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Opción 2: Buscar en el directorio actual (por si se ejecuta desde la raíz)
CURRENT_DIR = Path.cwd()
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

# Opción 3: Buscar en el directorio padre (por si se ejecuta desde api/)
PARENT_DIR = Path(__file__).parent.parent  # api/services -> api
if str(PARENT_DIR) not in sys.path:
    sys.path.insert(0, str(PARENT_DIR))

# Verificar si deepseekcli existe antes de importar
deepseekcli_path = ROOT_DIR / "deepseekcli"
if not deepseekcli_path.exists():
    deepseekcli_path = CURRENT_DIR / "deepseekcli"
if not deepseekcli_path.exists():
    deepseekcli_path = PARENT_DIR / "deepseekcli"

if not deepseekcli_path.exists():
    raise ImportError(
        f"No se encontró la carpeta 'deepseekcli' en ninguna de estas ubicaciones:\n"
        f"  - {ROOT_DIR / 'deepseekcli'}\n"
        f"  - {CURRENT_DIR / 'deepseekcli'}\n"
        f"  - {PARENT_DIR / 'deepseekcli'}\n"
        f"  - {Path(__file__).parent / 'deepseekcli'}"
    )

print(f"✅ deepseekcli encontrado en: {deepseekcli_path}")

# Ahora importar
from deepseekcli import DeepSeekClient
from utils.env_loader import get_credentials

logger = logging.getLogger(__name__)

class DeepSeekService:
    """Servicio singleton para mantener el cliente y sesiones."""
    
    _instance = None
    _client = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._client is None:
            token, cookies = get_credentials()
            login_dir = Path(os.getenv('DEEPSEEK_LOGIN_DIR', '.login_api'))
            self._client = DeepSeekClient(
                token=token,
                cookies=cookies,
                login_dir=login_dir
            )
            logger.info("Cliente DeepSeek inicializado correctamente.")
    
    @property
    def client(self) -> DeepSeekClient:
        return self._client
    
    def create_session(self) -> str:
        """Crea una nueva sesión de chat."""
        return self.client.create_chat_session()
    
    def upload_file(self, file_path: str, thinking: bool = True) -> str:
        """Sube un archivo y devuelve su file_id."""
        return self.client.upload_file(file_path, thinking_enabled=thinking)
    
    def send_message(
        self,
        session_id: str,
        prompt: str,
        parent_message_id: Optional[int] = None,
        ref_file_ids: Optional[list[str]] = None,
        thinking_enabled: bool = True,
        search_enabled: bool = True,
        model_type: Optional[str] = None,
    ) -> Generator[dict, None, None]:
        """
        Envía un mensaje y devuelve un generador de eventos (streaming).
        """
        queue = Queue()
        
        def on_think(chunk: str):
            queue.put(("think", chunk))
        
        def on_response(chunk: str):
            queue.put(("response", chunk))
        
        def chat_thread():
            try:
                think, response, msg_id = self.client.chat(
                    prompt=prompt,
                    session_id=session_id,
                    parent_message_id=parent_message_id,
                    ref_file_ids=ref_file_ids,
                    stream=True,
                    thinking_enabled=thinking_enabled,
                    search_enabled=search_enabled,
                    model_type=model_type,
                    print_output=False,
                    on_think_chunk=on_think,
                    on_response_chunk=on_response,
                    save_history=True
                )
                queue.put(("done", msg_id))
            except Exception as e:
                logger.exception("Error en el hilo de chat")
                queue.put(("error", str(e)))
        
        thread = threading.Thread(target=chat_thread)
        thread.daemon = True
        thread.start()
        
        while True:
            event_type, data = queue.get()
            if event_type == "done":
                yield {"type": "done", "data": data}
                break
            elif event_type == "error":
                yield {"type": "error", "data": data}
                break
            else:
                yield {"type": event_type, "data": data}
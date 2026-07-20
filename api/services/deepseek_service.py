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
#  AGREGAR LA RUTA DE DEEPSEEKCLI AL SYS.PATH
# ============================================================
# Obtener la ruta raíz del proyecto (donde está deepseekcli)
current_file = Path(__file__).resolve()  # api/services/deepseek_service.py
project_root = current_file.parent.parent.parent  # sube 3 niveles hasta la raíz

# Agregar la raíz al sys.path para que Python pueda encontrar deepseekcli
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))
    print(f"✅ Ruta añadida a sys.path: {project_root}")

# Verificar que deepseekcli existe
deepseekcli_path = project_root / "deepseekcli"
if not deepseekcli_path.exists():
    raise ImportError(
        f"No se encontró la carpeta 'deepseekcli' en: {deepseekcli_path}\n"
        f"Estructura esperada:\n"
        f"  {project_root}/\n"
        f"    ├── deepseekcli/\n"
        f"    │   ├── __init__.py\n"
        f"    │   ├── client.py\n"
        f"    │   └── ...\n"
        f"    └── api/\n"
        f"        └── services/\n"
        f"            └── deepseek_service.py"
    )

print(f"✅ deepseekcli encontrado en: {deepseekcli_path}")

# Ahora importar
try:
    from deepseekcli import DeepSeekClient
    print("✅ DeepSeekClient importado correctamente")
except ImportError as e:
    print(f"❌ Error al importar DeepSeekClient: {e}")
    print(f"   sys.path actual: {sys.path}")
    raise

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
            try:
                token, cookies = get_credentials()
                login_dir = Path(os.getenv('DEEPSEEK_LOGIN_DIR', '.login_api'))
                self._client = DeepSeekClient(
                    token=token,
                    cookies=cookies,
                    login_dir=login_dir
                )
                logger.info("Cliente DeepSeek inicializado correctamente.")
            except Exception as e:
                logger.exception("Error al inicializar el cliente DeepSeek")
                raise
    
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

#!/usr/bin/env python3
"""
API REST para DeepSeek con streaming en tiempo real.
Desplegable en Render.
"""

import os
import sys
import logging
from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# Configurar logging detallado
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Cargar variables de entorno
load_dotenv()

# Verificar credenciales al inicio
logger.info("=== INICIANDO API DEEPSEEK ===")
logger.info(f"Directorio actual: {os.getcwd()}")
logger.info(f"Archivos en directorio: {os.listdir('.')}")

token = os.getenv('DEEPSEEK_TOKEN')
cookies = os.getenv('DEEPSEEK_COOKIES')

if not token or not cookies:
    logger.error("❌ Faltan credenciales: DEEPSEEK_TOKEN y DEEPSEEK_COOKIES deben estar definidas")
    logger.error("   Revisa las variables de entorno en Render")
    sys.exit(1)

logger.info("✅ Credenciales encontradas (token y cookies)")

# Inicializar app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50 MB

# CORS
CORS(app, resources={r"/*": {"origins": "*"}})

# Importar rutas (después de configurar app)
try:
    logger.info("Importando rutas...")
    from routes.session import session_bp
    from routes.chat import chat_bp
    from routes.upload import upload_bp
    
    app.register_blueprint(session_bp, url_prefix='/api/session')
    app.register_blueprint(chat_bp, url_prefix='/api/chat')
    app.register_blueprint(upload_bp, url_prefix='/api/upload')
    logger.info("✅ Rutas registradas correctamente")
except Exception as e:
    logger.exception("❌ Error al importar rutas")
    sys.exit(1)

# Health check
@app.route('/api/health')
def health():
    return jsonify({"status": "ok", "service": "deepseek-api"})

# Manejador de errores global
@app.errorhandler(Exception)
def handle_error(e):
    logger.exception("Error no capturado")
    return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Obtener puerto desde variable de entorno (Render asigna PORT)
    port = int(os.getenv('PORT', 5000))
    logger.info(f"🚀 Iniciando servidor en puerto {port}")
    logger.info(f"   Health check: http://0.0.0.0:{port}/api/health")
    
    # Ejecutar con host 0.0.0.0 para que Render pueda acceder
    app.run(host='0.0.0.0', port=port, debug=False)

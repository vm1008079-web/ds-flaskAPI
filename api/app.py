#!/usr/bin/env python3
"""
API REST para DeepSeek con streaming en tiempo real.
Desplegable en Render.
"""

from routes.upload import upload_bp
from routes.chat import chat_bp
from routes.session import session_bp
import os
from flask import Flask, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

# Inicializar app
app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'dev-secret-key')
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50 MB para archivos

# CORS (permitir cualquier origen para desarrollo)
CORS(app, resources={r"/*": {"origins": "*"}})

# Importar rutas

app.register_blueprint(session_bp, url_prefix='/api/session')
app.register_blueprint(chat_bp, url_prefix='/api/chat')
app.register_blueprint(upload_bp, url_prefix='/api/upload')

# Health check


@app.route('/api/health')
def health():
    return jsonify({"status": "ok", "service": "deepseek-api"})

# Manejador de errores global


@app.errorhandler(Exception)
def handle_error(e):
    return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    # Para desarrollo local
    app.run(host='0.0.0.0', port=5000, debug=True)

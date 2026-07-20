from flask import Blueprint, request, jsonify
import tempfile
import os
from services.deepseek_service import DeepSeekService

upload_bp = Blueprint('upload', __name__)
service = DeepSeekService()


@upload_bp.route('', methods=['POST'])
def upload_file():
    """Sube un archivo y devuelve file_id."""
    if 'file' not in request.files:
        return jsonify({"error": "No se encontró el archivo"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "Nombre de archivo vacío"}), 400

    thinking = request.form.get('thinking_enabled', 'true').lower() == 'true'

    # Guardar temporalmente
    with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp:
        file.save(tmp.name)
        tmp_path = tmp.name

    try:
        file_id = service.upload_file(tmp_path, thinking)
        return jsonify({"file_id": file_id, "filename": file.filename}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        # Limpiar archivo temporal
        try:
            os.unlink(tmp_path)
        except:
            pass

from flask import Blueprint, jsonify
from services.deepseek_service import DeepSeekService

session_bp = Blueprint('session', __name__)
service = DeepSeekService()


@session_bp.route('', methods=['POST'])
def create_session():
    """Crea una nueva sesión de chat."""
    try:
        session_id = service.create_session()
        return jsonify({"session_id": session_id}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

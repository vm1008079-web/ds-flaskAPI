from flask import Blueprint, request, Response, jsonify
import json
from services.deepseek_service import DeepSeekService

chat_bp = Blueprint('chat', __name__)
service = DeepSeekService()

@chat_bp.route('', methods=['POST'])
def send_message():
    """Envía un mensaje y devuelve stream SSE."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Datos JSON requeridos"}), 400
    
    session_id = data.get('session_id')
    prompt = data.get('prompt')
    if not session_id or not prompt:
        return jsonify({"error": "session_id y prompt son obligatorios"}), 400
    
    parent_message_id = data.get('parent_message_id')
    ref_file_ids = data.get('ref_file_ids', [])
    thinking_enabled = data.get('thinking_enabled', True)
    search_enabled = data.get('search_enabled', True)
    model_type = data.get('model_type')
    
    def generate():
        """Generador de eventos SSE."""
        yield "event: start\ndata: {}\n\n"
        try:
            for event in service.send_message(
                session_id=session_id,
                prompt=prompt,
                parent_message_id=parent_message_id,
                ref_file_ids=ref_file_ids,
                thinking_enabled=thinking_enabled,
                search_enabled=search_enabled,
                model_type=model_type
            ):
                yield f"event: {event['type']}\ndata: {json.dumps(event['data'], ensure_ascii=False)}\n\n"
        except Exception as e:
            yield f"event: error\ndata: {json.dumps({'error': str(e)}, ensure_ascii=False)}\n\n"
    
    return Response(generate(), mimetype="text/event-stream")
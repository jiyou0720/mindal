import os
from flask import Blueprint, request, jsonify, g, current_app
import openai
from backend.routes.auth_routes import token_required
from backend.mongo_models import ChatHistory, ChatSession, ChatbotFeedback
from datetime import datetime
from bson.objectid import ObjectId

chat_bp = Blueprint('chat', __name__)

# --- OpenAI 헬퍼 함수 ---
def call_openai_api(messages, model="gpt-4o", temperature=0.7, max_tokens=500):
    """OpenAI Chat Completion API를 호출하고 응답 텍스트를 반환합니다."""
    try:
        openai.api_key = os.environ.get('OPENAI_API_KEY')
        if not openai.api_key:
            current_app.logger.error("OpenAI API key is not configured!")
            return "서버 설정 오류: OpenAI API 키가 없습니다."

        response = openai.ChatCompletion.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if response.choices and response.choices[0].message:
            return response.choices[0].message['content'].strip()
        else:
            current_app.logger.warning(f"OpenAI API 응답에 유효한 선택지가 없습니다: {response}")
            return "응답이 명확하지 않습니다. 다시 시도해 주세요."
    except openai.error.OpenAIError as e:
        current_app.logger.error(f"OpenAI API 오류: {e}")
        return f"API 오류가 발생했습니다: {e}"
    except Exception as e:
        current_app.logger.error(f"OpenAI API 호출 중 예기치 않은 오류 발생: {e}", exc_info=True)
        return "알 수 없는 오류가 발생했습니다. 다시 시도해 주세요."

# --- API 엔드포인트 ---

@chat_bp.route('/openai', methods=['POST'])
@token_required
def chat_with_openai():
    user_id = g.user_id
    data = request.get_json()
    user_message = data.get('message')
    chat_session_id = data.get('chat_session_id')
    
    if not user_message:
        return jsonify({'error': '메시지를 입력해주세요.'}), 400

    # 새 세션 생성 또는 기존 세션 사용
    if not chat_session_id:
        chat_session_id = ChatHistory.generate_session_id(user_id)
        ChatSession.create_session(user_id, chat_session_id, "default")
        current_app.logger.info(f"새로운 채팅 세션 생성: {chat_session_id}")

    # 사용자 메시지 저장
    ChatHistory.add_message(user_id, "user", user_message, chat_session_id)

    # 대화 기록 구성
    system_prompt = (
        "당신은 사용자에게 심리적 안정과 통찰을 제공하는 AI 심리 상담사입니다. "
        "사용자의 이야기를 경청하고 공감하며, 따뜻하고 비판단적인 태도로 대화해주세요. "
        "사용자가 스스로 해결책을 찾을 수 있도록 돕고, 필요한 경우 전문가 상담을 제안할 수도 있습니다."
    )
    messages = [{"role": "system", "content": system_prompt}]
    
    # 이전 대화 기록 추가 (최대 10개)
    for msg in ChatHistory.get_history(user_id, chat_session_id, limit=10):
        role = "user" if msg["sender"] == "user" else "assistant"
        messages.append({"role": role, "content": msg["message"]})
    
    messages.append({"role": "user", "content": user_message})

    # OpenAI API 호출
    ai_response_text = call_openai_api(messages)

    # AI 응답 저장
    ChatHistory.add_message(user_id, "ai", ai_response_text, chat_session_id)
    
    return jsonify({'response': ai_response_text, 'chat_session_id': chat_session_id})

@chat_bp.route('/end_session', methods=['POST'])
@token_required
def end_chat_session():
    user_id = g.user_id
    data = request.get_json()
    chat_session_id = data.get('chat_session_id')

    if not chat_session_id:
        return jsonify({'error': '세션을 종료하려면 chat_session_id가 필요합니다.'}), 400

    full_history = ChatHistory.get_history(user_id, chat_session_id)
    if not full_history:
        return jsonify({'message': '해당 세션의 대화 기록이 없습니다.'}), 404

    conversation_text = "\n".join([f"{msg['sender']}: {msg['message']}" for msg in full_history])
    
    summary_prompt = (
        "다음 심리 상담 대화 내용을 3~5줄로 간결하게 요약해 주세요. "
        "주요 논점, 사용자의 감정 변화, 상담사의 개입 방식 등을 포함하여 "
        "핵심 내용을 파악할 수 있도록 작성해 주세요:\n\n"
        f"{conversation_text}"
    )
    
    summary_messages = [{"role": "user", "content": summary_prompt}]
    summary_text = call_openai_api(summary_messages, model="gpt-4o", temperature=0.5, max_tokens=200)

    ChatSession.update_session_summary(user_id, chat_session_id, summary_text)
    
    return jsonify({'message': '대화가 종료되고 요약되었습니다.', 'summary': summary_text}), 200

# [기존 기능 유지] 대화 기록, 세션, 피드백 관련 API들...
# (내부 로직은 mongo_models.py 파일 수정 후 정상 작동)

@chat_bp.route('/history', methods=['GET'])
@token_required
def get_chat_history():
    user_id = g.user_id
    chat_session_id = request.args.get('session_id')
    if not chat_session_id:
        return jsonify({'error': 'session_id가 필요합니다.'}), 400
    history = ChatHistory.get_history(user_id, chat_session_id)
    for item in history:
        item['_id'] = str(item['_id'])
        item['timestamp'] = item['timestamp'].isoformat()
    return jsonify({'history': history}), 200

@chat_bp.route('/sessions', methods=['GET'])
@token_required
def get_chat_sessions_metadata():
    user_id = g.user_id
    sessions_metadata = ChatSession.get_all_sessions_metadata(user_id)
    return jsonify({'sessions': [s.to_dict() for s in sessions_metadata]}), 200

@chat_bp.route('/session/<string:session_id>', methods=['DELETE'])
@token_required
def delete_chat_session(session_id):
    user_id = g.user_id
    ChatHistory.delete_session(user_id, session_id)
    ChatSession.delete_session_metadata(user_id, session_id)
    ChatbotFeedback.delete_by_chat_session_id(session_id)
    return jsonify({'message': f'세션 {session_id}이(가) 삭제되었습니다.'}), 200

@chat_bp.route('/feedback', methods=['POST'])
@token_required
def submit_chat_feedback():
    user_id = g.user_id
    data = request.get_json()
    feedback_id = ChatbotFeedback.create(
        user_id=user_id,
        chat_session_id=data.get('chat_session_id'),
        rating=data.get('rating'),
        comment=data.get('comment'),
        timestamp=datetime.now()
    )
    return jsonify({'message': '피드백이 성공적으로 제출되었습니다.', 'feedback_id': feedback_id}), 200


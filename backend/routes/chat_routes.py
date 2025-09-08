import os
from flask import Blueprint, request, jsonify, g, current_app
from openai import OpenAI
from backend.routes.auth_routes import token_required, roles_required
from backend.mongo_models import ChatHistory, ChatSession, ChatbotFeedback
from datetime import datetime

chat_bp = Blueprint('chat', __name__)

# --- OpenAI Helper Function ---
def call_openai_api(messages, model="gpt-4o", temperature=0.7, max_tokens=500):
    """Calls the OpenAI Chat Completion API and returns the response text."""
    try:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            current_app.logger.error("OpenAI API key is not configured!")
            return "서버 설정 오류: OpenAI API 키가 없습니다."

        client = OpenAI(api_key=api_key.strip())

        response = client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        if response.choices and response.choices[0].message:
            return response.choices[0].message.content.strip()
        else:
            current_app.logger.warning(f"OpenAI API response did not contain valid choices: {response}")
            return "응답이 명확하지 않습니다. 다시 시도해 주세요."

    except Exception as e:
        current_app.logger.error(f"OpenAI API Error: {e}", exc_info=True)
        return f"OpenAI 호출 중 오류 발생: {e}"

# --- API Endpoints ---

@chat_bp.route('/openai', methods=['POST'])
@token_required
def chat_with_openai():
    user_id = g.user_id
    data = request.get_json()
    user_message = data.get('message')
    chat_session_id = data.get('chat_session_id')
    
    if not user_message:
        return jsonify({'error': 'Please enter a message.'}), 400

    if not chat_session_id:
        chat_session_id = ChatHistory._generate_session_id(user_id) 
        ChatSession.create_session(user_id, chat_session_id, "default")
        current_app.logger.info(f"New chat session created: {chat_session_id}")

    ChatHistory.add_message(user_id, "user", user_message, chat_session_id)

    system_prompt = (
        "You are an AI psychological counselor providing psychological stability and insight to the user. "
        "Listen to the user's story, empathize, and converse with a warm, non-judgmental attitude. "
        "Help the user find their own solutions, and suggest professional counseling if necessary."
    )
    messages = [{"role": "system", "content": system_prompt}]
    
    # ✅ 세션이 존재하고, 숨김 처리되지 않았을 때만 이전 대화 기록을 가져옵니다.
    session_info = ChatSession.get_session_by_id(user_id, chat_session_id)
    if session_info:
        for msg in ChatHistory.get_history(user_id, chat_session_id, limit=10):
            role = "user" if msg["sender"] == "user" else "assistant"
            messages.append({"role": role, "content": msg["message"]})
    
    messages.append({"role": "user", "content": user_message})

    ai_response_text = call_openai_api(messages)

    ChatHistory.add_message(user_id, "ai", ai_response_text, chat_session_id)
    
    return jsonify({'response': ai_response_text, 'chat_session_id': chat_session_id})

@chat_bp.route('/end_session', methods=['POST'])
@token_required
def end_chat_session():
    user_id = g.user_id
    data = request.get_json()
    chat_session_id = data.get('chat_session_id')

    if not chat_session_id:
        return jsonify({'error': 'chat_session_id is required to end the session.'}), 400

    full_history = ChatHistory.get_history(user_id, chat_session_id)
    if not full_history:
        return jsonify({'message': 'No chat history found for this session.'}), 404

    conversation_text = "\n".join([f"{msg['sender']}: {msg['message']}" for msg in full_history])
    
    summary_prompt = (
        "Please summarize the following psychological counseling conversation in 3-5 lines. "
        "Include the main points, the user's emotional changes, and the counselor's intervention methods "
        "to capture the core content:\n\n"
        f"{conversation_text}"
    )
    
    summary_messages = [{"role": "user", "content": summary_prompt}]
    summary_text = call_openai_api(summary_messages, model="gpt-4o", temperature=0.5, max_tokens=200)

    ChatSession.update_session_summary(user_id, chat_session_id, summary_text)
    
    return jsonify({'message': 'The conversation has ended and been summarized.', 'summary': summary_text}), 200

@chat_bp.route('/sessions', methods=['GET'])
@token_required
def get_chat_sessions_metadata():
    user_id = g.user_id
    try:
        # 이 함수는 이제 mongo_models에서 알아서 숨김 처리된 세션을 제외하고 가져옵니다.
        sessions_metadata = ChatSession.get_all_sessions_metadata(user_id)
        sessions_list = []
        for s in sessions_metadata:
            session_dict = s.to_dict()
            if '_id' in session_dict:
                session_dict['_id'] = str(session_dict['_id'])
            if 'created_at' in session_dict and isinstance(session_dict['created_at'], datetime):
                 session_dict['created_at'] = session_dict['created_at'].isoformat()
            sessions_list.append(session_dict)
        return jsonify({'sessions': sessions_list}), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching chat sessions metadata for user {user_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to load chat session list.'}), 500

@chat_bp.route('/history', methods=['GET'])
@token_required
def get_chat_history():
    user_id = g.user_id
    chat_session_id = request.args.get('session_id')
    if not chat_session_id:
        return jsonify({'error': 'session_id is required.'}), 400
    
    # ✅ 숨겨진 세션인지 확인하는 로직
    session_info = ChatSession.get_session_by_id(user_id, chat_session_id)
    if not session_info:
        return jsonify({'error': 'Session not found or you do not have permission to view it.'}), 404

    history = ChatHistory.get_history(user_id, chat_session_id)
    for item in history:
        item['_id'] = str(item['_id'])
        if isinstance(item.get('timestamp'), datetime):
            item['timestamp'] = item['timestamp'].isoformat()
    return jsonify({'history': history}), 200

@chat_bp.route('/session/<string:session_id>', methods=['DELETE'])
@token_required
def delete_chat_session(session_id):
    # ✅ 소프트 삭제를 위한 함수 호출로 변경
    user_id = g.user_id
    success = ChatSession.hide_session_for_user(user_id, session_id)
    
    if success:
        return jsonify({'message': f'Session {session_id} has been hidden.'}), 200
    else:
        return jsonify({'error': 'Session not found or could not be hidden.'}), 404


@chat_bp.route('/feedback', methods=['POST'])
@token_required
def submit_chat_feedback():
    user_id = g.user_id
    data = request.get_json()
    chat_session_id = data.get('chat_session_id')
    rating = data.get('rating')

    # ✅ 피드백 저장을 위한 필수 필드 검증 로직 추가
    if not all([chat_session_id, rating is not None]):
        current_app.logger.warning(
            f"Feedback submission failed for user {user_id} due to missing data. "
            f"Session ID: {chat_session_id}, Rating: {rating}"
        )
        return jsonify({'error': 'Chat session ID and rating are required to submit feedback.'}), 400

    feedback_id = ChatbotFeedback.create(
        user_id=user_id,
        chat_session_id=chat_session_id,
        rating=rating,
        comment=data.get('comment')
    )
    return jsonify({'message': 'Feedback submitted successfully.', 'feedback_id': str(feedback_id)}), 200

# --- Admin Feedback Routes ---

@chat_bp.route('/all_feedback', methods=['GET'])
@token_required
@roles_required(['관리자', '개발자'])
def get_all_chatbot_feedback():
    try:
        feedback_list = ChatbotFeedback.get_all()
        formatted_feedback = []
        for fb in feedback_list:
            fb['_id'] = str(fb['_id'])
            if isinstance(fb.get('timestamp'), datetime):
                fb['timestamp'] = fb['timestamp'].isoformat()
            formatted_feedback.append(fb)
        return jsonify({"feedback": formatted_feedback}), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching all chatbot feedback: {e}", exc_info=True)
        return jsonify({"message": "An error occurred while fetching all chatbot feedback."}), 500

@chat_bp.route('/feedback/<string:feedback_id>', methods=['GET'])
@token_required
@roles_required(['관리자', '개발자'])
def get_feedback_detail_for_admin(feedback_id):
    try:
        feedback_doc = ChatbotFeedback.get_by_id(feedback_id)
        if not feedback_doc:
            return jsonify({'message': 'Feedback not found.'}), 404
        
        feedback_doc['_id'] = str(feedback_doc['_id'])
        if isinstance(feedback_doc.get('timestamp'), datetime):
            feedback_doc['timestamp'] = feedback_doc['timestamp'].isoformat()

        return jsonify(feedback_doc), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching feedback detail {feedback_id}: {e}", exc_info=True)
        return jsonify({'error': 'An error occurred while fetching feedback details.'}), 500

@chat_bp.route('/feedback_item/<string:feedback_id>', methods=['DELETE'])
@token_required
@roles_required(['관리자', '개발자'])
def delete_feedback_item(feedback_id):
    try:
        if ChatbotFeedback.delete(feedback_id):
            return jsonify({'message': 'Feedback deleted successfully.'}), 200
        return jsonify({'message': 'Feedback not found.'}), 404
    except Exception as e:
        current_app.logger.error(f"Error deleting feedback item {feedback_id}: {e}", exc_info=True)
        return jsonify({'error': 'An error occurred while deleting feedback.'}), 500

# [Restored] Endpoint to get all feedback for the current user
@chat_bp.route('/my_feedback', methods=['GET'])
@token_required
def get_my_feedback():
    user_id = g.user_id
    try:
        feedback_list = ChatbotFeedback.get_feedback_by_user(user_id)
        
        formatted_feedback = []
        for fb in feedback_list:
            fb_dict = {
                'id': str(fb['_id']),
                'user_id': fb['user_id'],
                'chat_session_id': fb['chat_session_id'],
                'rating': fb['rating'],
                'comment': fb['comment'],
                'timestamp': fb['timestamp'].isoformat() if isinstance(fb['timestamp'], datetime) else fb['timestamp'],
            }
            formatted_feedback.append(fb_dict)
            
        return jsonify({"feedback": formatted_feedback}), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching user feedback for user {user_id}: {e}", exc_info=True)
        return jsonify({"message": "내 피드백을 불러오는 중 오류가 발생했습니다."}), 500



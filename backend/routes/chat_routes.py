import os
from flask import Blueprint, request, jsonify, g, current_app
import requests
import json
from backend.routes.auth_routes import token_required, role_required # role_required 임포트
from backend.mongo_models import ChatHistory, ChatSession, ChatbotFeedback # ChatSession, ChatbotFeedback 임포트
from datetime import datetime
import time
import openai
from bson.objectid import ObjectId # ObjectId 임포트

chat_bp = Blueprint('chat', __name__)

# Exponential backoff function for API retries
def exponential_backoff(retries, base_delay=1):
    delay = base_delay * (2 ** retries)
    time.sleep(delay)

@chat_bp.route('/openai', methods=['POST'])
@token_required
def chat_with_openai():
    user_id = g.user_id
    data = request.get_json()
    user_message = data.get('message')
    chat_session_id = data.get('chat_session_id')
    
    if not user_message:
        return jsonify({'error': 'Message is required'}), 400

    api_key = current_app.config.get('OPENAI_API_KEY')
    if not api_key:
        current_app.logger.error("OpenAI API key is not configured!")
        return jsonify({'error': 'Server configuration error: OpenAI API key missing.'}), 500

    chat_history_docs = ChatHistory.get_history(user_id, chat_session_id, limit=10)

    openai_chat_history = []
    
    system_prompt = (
        f"당신은 사용자에게 심리적 안정과 통찰을 제공하는 AI 심리 상담사입니다. "
        f"사용자의 이야기를 경청하고 공감하며, 따뜻하고 비판단적인 태도로 대화해주세요. "
        f"사용자가 스스로 해결책을 찾을 수 있도록 돕고, 필요한 경우 전문가 상담을 제안할 수도 있습니다. "
        f"사용자의 질문에 직접적인 조언보다는 질문과 공감을 통해 스스로 생각할 기회를 제공하세요. "
        f"간결하고 명확하게 답변하며, 때로는 은유나 비유를 사용하여 깊이 있는 사고를 유도하세요."
    )
    openai_chat_history.append({"role": "system", "content": system_prompt})


    if chat_history_docs:
        for msg_doc in chat_history_docs:
            role = "user" if msg_doc["sender"] == "user" else "assistant"
            openai_chat_history.append({"role": role, "content": msg_doc["message"]})
    
    openai_chat_history.append({"role": "user", "content": user_message})

    payload = {
        "model": "gpt-4o",
        "messages": openai_chat_history,
        "temperature": 0.7,
        "max_tokens": 500,
        "top_p": 1,
        "frequency_penalty": 0,
        "presence_penalty": 0
    }
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}'
    }
    api_url = "https://api.openai.com/v1/chat/completions"

    ai_response_text = "죄송합니다. 현재 챗봇이 응답할 수 없습니다."
    
    try:
        if chat_session_id is None:
            new_session_id = ChatHistory._generate_session_id(user_id)
            ChatSession.create_session(user_id, new_session_id, chat_style="default")
            chat_session_id = new_session_id
            current_app.logger.info(f"New ChatSession created: {chat_session_id}")
            
        ChatHistory.add_message(user_id, "user", user_message, chat_session_id)
        current_app.logger.info(f"User message saved: User ID {user_id}, Session ID {chat_session_id}")
    except Exception as e:
        current_app.logger.error(f"Failed to save user message to MongoDB: {e}")

    retries = 0
    max_retries = 3
    while retries < max_retries:
        try:
            response = requests.post(api_url, headers=headers, data=json.dumps(payload))
            response.raise_for_status()
            result = response.json()

            if result.get("choices") and result["choices"][0].get("message") and result["choices"][0]["message"].get("content"):
                ai_response_text = result["choices"][0]["message"]["content"]
                break
            else:
                current_app.logger.warning(f"OpenAI API response missing choices or content: {result}")
                ai_response_text = "응답이 명확하지 않습니다. 다시 시도해 주세요."
                break

        except requests.exceptions.HTTPError as http_err:
            current_app.logger.error(f"HTTP error occurred during OpenAI API call: {http_err} - Response: {response.text}")
            if response.status_code == 429 and retries < max_retries -1:
                retries += 1
                exponential_backoff(retries)
                current_app.logger.info(f"Retrying OpenAI API call ({retries}/{max_retries})...")
            else:
                ai_response_text = f"API 오류: {response.status_code} - {response.text}"
                break
        except requests.exceptions.ConnectionError as conn_err:
            current_app.logger.error(f"Connection error during OpenAI API call: {conn_err}")
            ai_response_text = "네트워크 연결에 문제가 있습니다. 다시 시도해 주세요."
            break
        except requests.exceptions.Timeout as timeout_err:
            current_app.logger.error(f"Timeout error during OpenAI API call: {timeout_err}")
            ai_response_text = "API 응답 시간이 초과되었습니다. 다시 시도해 주세요."
            break
        except json.JSONDecodeError as json_err:
            current_app.logger.error(f"JSON decode error from OpenAI API response: {json_err} - Response text: {response.text}")
            ai_response_text = "API 응답 형식이 잘못되었습니다."
            break
        except Exception as e:
            current_app.logger.error(f"An unexpected error occurred during OpenAI API call: {e}", exc_info=True)
            ai_response_text = "알 수 없는 오류가 발생했습니다. 다시 시도해 주세요."
            break

    try:
        if chat_session_id:
            ChatHistory.add_message(user_id, "ai", ai_response_text, chat_session_id)
            current_app.logger.info(f"AI response saved: User ID {user_id}, Session ID {chat_session_id}")
        else:
            current_app.logger.error("Chat session ID is missing, cannot save AI response to MongoDB.")
    except Exception as e:
        current_app.logger.error(f"Failed to save AI response to MongoDB: {e}")

    return jsonify({'response': ai_response_text, 'chat_session_id': chat_session_id})

@chat_bp.route('/end_session', methods=['POST'])
@token_required
def end_chat_session():
    user_id = g.user_id
    data = request.get_json()
    chat_session_id = data.get('chat_session_id')

    if not chat_session_id:
        return jsonify({'error': 'chat_session_id is required to end session'}), 400

    try:
        full_history = ChatHistory.get_history(user_id, chat_session_id)
        if not full_history:
            return jsonify({'message': 'No chat history found for this session.'}), 404

        conversation_text = "\n".join([f"{msg['sender']}: {msg['message']}" for msg in full_history])

        api_key = current_app.config.get('OPENAI_API_KEY')
        if not api_key:
            current_app.logger.error("OpenAI API key is not configured for summarization!")
            return jsonify({'error': 'Server configuration error: OpenAI API key missing.'}), 500

        summary_prompt = (
            "다음 심리 상담 대화 내용을 3~5줄로 간결하게 요약해 주세요. "
            "주요 논점, 사용자의 감정 변화, 상담사의 개입 방식 등을 포함하여 "
            "핵심 내용을 파악할 수 있도록 작성해 주세요:\n\n"
            f"{conversation_text}"
        )
        
        summary_payload = {
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": summary_prompt}],
            "temperature": 0.5,
            "max_tokens": 200,
            "top_p": 1
        }
        summary_headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {api_key}'
        }
        summary_api_url = "https://api.openai.com/v1/chat/completions"

        summary_text = "대화 요약을 생성하는 데 실패했습니다."
        retries = 0
        max_retries = 3
        while retries < max_retries:
            try:
                summary_response = requests.post(summary_api_url, headers=summary_headers, data=json.dumps(summary_payload))
                summary_response.raise_for_status()
                summary_result = summary_response.json()
                if summary_result.get("choices") and summary_result["choices"][0].get("message") and summary_result["choices"][0]["message"].get("content"):
                    summary_text = summary_result["choices"][0]["message"]["content"]
                    break
                else:
                    current_app.logger.warning(f"OpenAI API summary response missing content: {summary_result}")
                    break
            except requests.exceptions.HTTPError as http_err:
                current_app.logger.error(f"HTTP error during summary API call: {http_err} - Response: {summary_response.text}")
                if summary_response.status_code == 429 and retries < max_retries -1:
                    retries += 1
                    exponential_backoff(retries)
                    current_app.logger.info(f"Retrying summary API call ({retries}/{max_retries})...")
                else:
                    summary_text = f"요약 API 오류: {summary_response.status_code}"
                    break
            except Exception as e:
                current_app.logger.error(f"Error during summary API call: {e}", exc_info=True)
                break

        ChatSession.update_session_summary(user_id, chat_session_id, summary_text)
        current_app.logger.info(f"ChatSession {chat_session_id} summary updated.")

        return jsonify({'message': '대화가 종료되고 요약되었습니다.', 'summary': summary_text}), 200

    except Exception as e:
        current_app.logger.error(f"Error ending chat session {chat_session_id}: {e}", exc_info=True)
        return jsonify({'error': '대화 종료 및 요약 중 오류가 발생했습니다.'}), 500


@chat_bp.route('/history', methods=['GET'])
@token_required
def get_chat_history():
    user_id = g.user_id
    chat_session_id = request.args.get('session_id')

    if not chat_session_id:
        return jsonify({'error': 'session_id is required'}), 400

    try:
        history = ChatHistory.get_history(user_id, chat_session_id)
        for item in history:
            item['_id'] = str(item['_id'])
            item['timestamp'] = item['timestamp'].isoformat()
        return jsonify({'history': history}), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching chat history for user {user_id}, session {chat_session_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to retrieve chat history.'}), 500


@chat_bp.route('/sessions', methods=['GET'])
@token_required
def get_chat_sessions_metadata():
    user_id = g.user_id
    try:
        sessions_metadata = ChatSession.get_all_sessions_metadata(user_id)
        return jsonify({'sessions': [s.to_dict() for s in sessions_metadata]}), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching chat sessions metadata for user {user_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to retrieve chat sessions metadata.'}), 500

@chat_bp.route('/session/<string:session_id>', methods=['DELETE'])
@token_required
def delete_chat_session(session_id):
    user_id = g.user_id
    try:
        deleted_messages_count = ChatHistory.delete_session(user_id, session_id)
        deleted_session_metadata = ChatSession.delete_session_metadata(user_id, session_id)
        deleted_feedback_count = ChatbotFeedback.delete_by_chat_session_id(session_id)


        if deleted_messages_count > 0 or deleted_session_metadata or deleted_feedback_count > 0:
            return jsonify({'message': f'Session {session_id} and its {deleted_messages_count} messages and {deleted_feedback_count} feedbacks deleted successfully.'}), 200
        else:
            return jsonify({'message': f'Session {session_id} not found or no messages/feedbacks deleted.'}), 404
    except Exception as e:
        current_app.logger.error(f"Error deleting chat session {session_id} for user {user_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to delete chat session.'}), 500

@chat_bp.route('/feedback', methods=['POST'])
@token_required
def submit_chat_feedback():
    user_id = g.user_id
    data = request.get_json()
    chat_session_id = data.get('chat_session_id')
    rating = data.get('rating')
    comment = data.get('comment')

    if not all([chat_session_id, rating]):
        return jsonify({'error': 'chat_session_id and rating are required for feedback.'}), 400
    
    try:
        feedback_id = ChatbotFeedback.create(
            user_id=user_id,
            chat_session_id=chat_session_id,
            rating=rating,
            comment=comment,
            timestamp=datetime.now()
        )
        current_app.logger.info(f"Feedback submitted for session {chat_session_id} by user {user_id}. Feedback ID: {feedback_id}")
        return jsonify({'message': '피드백이 성공적으로 제출되었습니다.', 'feedback_id': feedback_id}), 200
    except Exception as e:
        current_app.logger.error(f"Error submitting feedback for session {chat_session_id}: {e}", exc_info=True)
        return jsonify({'error': '피드백 제출 중 오류가 발생했습니다.'}), 500

# NEW: 특정 피드백 상세 조회 (관리자용)
@chat_bp.route('/feedback/<string:feedback_id>', methods=['GET'])
@token_required
@role_required('관리자', '개발자') # 관리자 또는 개발자만 접근 가능
def get_feedback_detail_for_admin(feedback_id):
    try:
        feedback_doc = ChatbotFeedback.get_by_id(feedback_id)
        if not feedback_doc:
            return jsonify({'message': '피드백을 찾을 수 없습니다.'}), 404
        
        # ObjectId를 문자열로 변환
        feedback_doc['_id'] = str(feedback_doc['_id'])
        # feedback_doc['id'] 필드가 없을 수 있으므로 제거
        if 'timestamp' in feedback_doc and isinstance(feedback_doc['timestamp'], datetime):
            feedback_doc['timestamp'] = feedback_doc['timestamp'].isoformat()

        return jsonify(feedback_doc), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching feedback detail {feedback_id}: {e}", exc_info=True)
        return jsonify({'error': '피드백 상세 조회 중 오류가 발생했습니다.'}), 500

# NEW: 특정 피드백 삭제 (관리자용)
@chat_bp.route('/feedback_item/<string:feedback_id>', methods=['DELETE'])
@token_required
@role_required('관리자', '개발자') # 관리자 또는 개발자만 접근 가능
def delete_feedback_item(feedback_id):
    try:
        if ChatbotFeedback.delete(feedback_id):
            return jsonify({'message': '피드백이 성공적으로 삭제되었습니다.'}), 200
        return jsonify({'message': '피드백을 찾을 수 없습니다.'}), 404
    except Exception as e:
        current_app.logger.error(f"Error deleting feedback item {feedback_id}: {e}", exc_info=True)
        return jsonify({'error': '피드백 삭제 중 오류가 발생했습니다.'}), 500

# NEW: 모든 챗봇 피드백 조회 (관리자용)
@chat_bp.route('/all_feedback', methods=['GET'])
@token_required
@role_required('관리자', '개발자') # 관리자 또는 개발자만 접근 가능
def get_all_chatbot_feedback():
    try:
        feedback_list = ChatbotFeedback.get_all()
        
        formatted_feedback = []
        for fb in feedback_list:
            fb_dict = {
                'id': str(fb['_id']), # ObjectId를 문자열로 변환
                'user_id': fb['user_id'],
                'chat_session_id': fb['chat_session_id'],
                'rating': fb['rating'],
                'comment': fb['comment'],
                'timestamp': fb['timestamp'].isoformat() if isinstance(fb['timestamp'], datetime) else fb['timestamp'],
            }
            formatted_feedback.append(fb_dict)
            
        return jsonify({"feedback": formatted_feedback}), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching all chatbot feedback: {e}", exc_info=True)
        return jsonify({"message": "모든 챗봇 피드백을 불러오는 중 오류가 발생했습니다."}), 500

# NEW: 사용자의 모든 피드백을 조회하는 엔드포인트 (기존 유지)
@chat_bp.route('/my_feedback', methods=['GET'])
@token_required
def get_my_feedback():
    user_id = g.user_id
    try:
        feedback_list = ChatbotFeedback.get_feedback_by_user(user_id)
        
        formatted_feedback = []
        for fb in feedback_list:
            fb_dict = {
                'id': str(fb['_id']), # ObjectId를 문자열로 변환
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


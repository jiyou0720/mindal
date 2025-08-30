import os
from flask import Blueprint, request, jsonify, g, current_app
import requests
import json
from backend.routes.auth_routes import token_required, roles_required
from backend.mongo_models import ChatHistory, ChatSession
from datetime import datetime
import time

chat_bp = Blueprint('chat_api', __name__)

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
    
    # chat_style은 이제 프론트엔드에서 제거되었으므로, 기본값으로 설정하거나
    # 첫 메시지 전송 시에만 사용하도록 로직을 변경합니다.
    # 여기서는 시스템 프rompt에 직접 포함하는 방식으로 변경합니다.
    # chat_style = data.get('chat_style', 'default') 

    if not user_message:
        return jsonify({'error': 'Message is required'}), 400

    api_key = current_app.config.get('OPENAI_API_KEY')
    if not api_key:
        current_app.logger.error("OpenAI API key is not configured!")
        return jsonify({'error': 'Server configuration error: OpenAI API key missing.'}), 500

    # Retrieve recent chat history for context
    chat_history_docs = ChatHistory.get_history(user_id, chat_session_id, limit=10)

    # Construct chat history for OpenAI API, including the new user message
    openai_chat_history = []
    
    # System message for chatbot personality and style
    # 이제 chat_style은 동적으로 받지 않고, 기본 심리 상담사 페르소나를 유지합니다.
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

    # Prepare payload for OpenAI Chat Completions API
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
    
    # Store user message in MongoDB *before* calling OpenAI API
    try:
        if chat_session_id is None:
            # New session: create ChatSession metadata first
            new_session_id = ChatHistory._generate_session_id(user_id)
            ChatSession.create_session(user_id, new_session_id, chat_style="default") # 기본 스타일로 세션 생성
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

            if result.get("choices") and result["choices"][0].get("message") and result["choices"][0]["message"].get("content"): # Corrected line 104
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

    # Store AI response in MongoDB
    try:
        if chat_session_id:
            ChatHistory.add_message(user_id, "ai", ai_response_text, chat_session_id)
            current_app.logger.info(f"AI response saved: User ID {user_id}, Session ID {chat_session_id}")
        else:
            current_app.logger.error("Chat session ID is missing, cannot save AI response to MongoDB.")
    except Exception as e:
        current_app.logger.error(f"Failed to save AI response to MongoDB: {e}")

    return jsonify({'response': ai_response_text, 'chat_session_id': chat_session_id})

# NEW: 대화 종료 및 요약 API
@chat_bp.route('/end_session', methods=['POST'])
@token_required
def end_chat_session():
    user_id = g.user_id
    data = request.get_json()
    chat_session_id = data.get('chat_session_id')

    if not chat_session_id:
        return jsonify({'error': 'chat_session_id is required to end session'}), 400

    try:
        # 1. 해당 세션의 전체 대화 기록을 가져옵니다.
        full_history = ChatHistory.get_history(user_id, chat_session_id)
        if not full_history:
            return jsonify({'message': 'No chat history found for this session.'}), 404

        # 2. 대화 기록을 텍스트로 변환하여 요약 프롬프트에 사용합니다.
        conversation_text = "\n".join([f"{msg['sender']}: {msg['message']}" for msg in full_history])

        # 3. OpenAI API를 사용하여 대화 요약을 생성합니다.
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

        # 4. ChatSession에 요약 내용을 업데이트합니다.
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
        # ChatHistory에서 개별 메시지 기록을 가져옵니다.
        # 사용자가 삭제한 세션의 기록도 관리자 페이지에서는 볼 수 있어야 하므로,
        # ChatHistory에서 직접 가져오는 이 부분은 변경하지 않습니다.
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
        # 사용자가 삭제하지 않은 세션만 조회 (is_deleted_by_user=False)
        sessions_metadata = ChatSession.get_all_sessions_metadata(user_id, include_deleted=False)
        return jsonify({'sessions': [s.to_dict() for s in sessions_metadata]}), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching chat sessions metadata for user {user_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to retrieve chat sessions metadata.'}), 500

@chat_bp.route('/session/<string:session_id>', methods=['DELETE'])
@token_required
def delete_chat_session(session_id):
    user_id = g.user_id
    try:
        # ChatHistory 메시지 자체는 삭제하지 않고, ChatSession 메타데이터만 소프트 삭제
        # ChatHistory.delete_session(user_id, session_id) # 이 줄은 이제 필요 없습니다.
        deleted_session_metadata = ChatSession.delete_session_metadata(user_id, session_id)

        if deleted_session_metadata:
            return jsonify({'message': f'Session {session_id} has been soft-deleted for the user.'}), 200
        else:
            return jsonify({'message': f'Session {session_id} not found or already soft-deleted.'}), 404
    except Exception as e:
        current_app.logger.error(f"Error soft-deleting chat session {session_id} for user {user_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to soft-delete chat session.'}), 500

# 피드백 제출 API (기존 유지)
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
        success = ChatSession.update_session_feedback(user_id, chat_session_id, rating, comment)
        if success:
            current_app.logger.info(f"Feedback submitted for session {chat_session_id} by user {user_id}.")
            return jsonify({'message': '피드백이 성공적으로 제출되었습니다.'}), 200
        else:
            return jsonify({'message': '피드백 제출에 실패했습니다. 세션을 찾을 수 없습니다.'}), 404
    except Exception as e:
        current_app.logger.error(f"Error submitting feedback for session {chat_session_id}: {e}", exc_info=True)
        return jsonify({'error': '피드백 제출 중 오류가 발생했습니다.'}), 500

# 기존: 특정 채팅 세션의 피드백 확인 API
@chat_bp.route('/feedback/<string:chat_session_id>', methods=['GET'])
@token_required
def get_chat_feedback(chat_session_id):
    user_id = g.user_id
    try:
        session = ChatSession.get_session_metadata(user_id, chat_session_id)
        if session:
            if session.feedback:
                feedback_data = session.feedback # feedback_data는 이미 딕셔너리 또는 적절한 객체
                if isinstance(feedback_data, dict):
                    pass # 이미 딕셔너리이므로 그대로 사용
                elif hasattr(feedback_data, 'to_dict'):
                    feedback_data = feedback_data.to_dict()
                else:
                    current_app.logger.error(f"Unhandled feedback format in get_chat_feedback for session {chat_session_id}: {type(feedback_data)}")
                    return jsonify({'message': '피드백 형식이 잘못되었습니다.'}), 500
                
                return jsonify({'feedback': feedback_data}), 200
            else:
                return jsonify({'message': '해당 세션에 대한 피드백이 없습니다.'}), 404
        else:
            return jsonify({'message': '채팅 세션을 찾을 수 없습니다.'}), 404
    except Exception as e:
        current_app.logger.error(f"Error fetching feedback for session {chat_session_id} by user {user_id}: {e}", exc_info=True)
        return jsonify({'error': '피드백 조회 중 오류가 발생했습니다.'}), 500


# NEW: 현재 로그인한 사용자의 모든 피드백 목록 조회 API (관리자용)
@chat_bp.route('/my_feedback', methods=['GET'])
@token_required
@roles_required(['관리자']) # 관리자 역할만 접근 가능하도록 추가
def get_all_my_feedback():
    user_id = g.user_id # 관리자 본인의 user_id
    try:
        # 모든 사용자의 모든 채팅 세션 메타데이터를 가져옵니다. (소프트 삭제된 것도 포함)
        # 관리자는 모든 피드백을 볼 수 있어야 하므로 user_id 필터링 제거
        # ChatSession.get_all_sessions_metadata(user_id, include_deleted=True) 대신
        # 모든 세션을 조회하는 새로운 메서드가 필요합니다.
        # 일단은 ChatSession.get_all_sessions_metadata를 수정하여 include_deleted=True로 호출
        
        # 모든 세션을 가져오되, 피드백이 있는 세션만 필터링합니다.
        # user_id 필터링 제거 (관리자는 모든 사용자의 피드백을 봐야 함)
        from backend.extensions import mongo
        all_sessions_docs = mongo.db[ChatSession.COLLECTION_NAME].find({}) # 모든 사용자 세션 조회
        
        my_feedback_list = []
        for doc in all_sessions_docs:
            session = ChatSession.from_mongo(doc) # MongoDB 문서로부터 ChatSession 객체 생성
            
            # ChatSession 객체의 feedback 속성이 존재하고 None이 아닌 경우에만 처리
            if hasattr(session, 'feedback') and session.feedback is not None:
                feedback_item = session.feedback
                
                # feedback_item이 딕셔너리인지 확인하여 안전하게 데이터에 접근
                if isinstance(feedback_item, dict):
                    my_feedback_list.append({
                        'chat_session_id': session.chat_session_id,
                        'user_id': session.user_id, # 어떤 사용자의 피드백인지 추가
                        'rating': feedback_item.get('rating'),
                        'comment': feedback_item.get('comment'),
                        'submitted_at': feedback_item.get('submitted_at')
                    })
                elif hasattr(feedback_item, 'to_dict'): # to_dict 메서드가 있다면 호출
                    converted_feedback = feedback_item.to_dict()
                    my_feedback_list.append({
                        'chat_session_id': session.chat_session_id,
                        'user_id': session.user_id, # 어떤 사용자의 피드백인지 추가
                        'rating': converted_feedback.get('rating'),
                        'comment': converted_feedback.get('comment'),
                        'submitted_at': converted_feedback.get('submitted_at')
                    })
                else:
                    current_app.logger.error(
                        f"Chat session {session.chat_session_id} for user {session.user_id} has unhandleable feedback format: {type(feedback_item)}."
                    )
                    # 처리할 수 없는 형식인 경우에도 목록에 추가하여 관리자에게 표시될 수 있도록 함
                    my_feedback_list.append({
                        'chat_session_id': session.chat_session_id,
                        'user_id': session.user_id,
                        'rating': None,
                        'comment': f"Unhandled feedback format: {str(feedback_item)}",
                        'submitted_at': None
                    })

        if my_feedback_list:
            for item in my_feedback_list:
                if isinstance(item.get('submitted_at'), datetime):
                    item['submitted_at'] = item['submitted_at'].isoformat()
            
            my_feedback_list.sort(key=lambda x: x.get('submitted_at', ''), reverse=True)
            return jsonify({'my_feedback': my_feedback_list}), 200
        else:
            return jsonify({'message': '제출된 피드백이 없습니다.'}), 404

    except Exception as e:
        current_app.logger.error(f"Error fetching all feedback for user {user_id}: {e}", exc_info=True)
        return jsonify({'error': '내 피드백 목록을 불러오는 데 실패했습니다.'}), 500

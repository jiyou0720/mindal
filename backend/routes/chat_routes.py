import os
from flask import Blueprint, request, jsonify, g, current_app
import requests
import json
from backend.routes.auth_routes import token_required
from backend.mongo_models import ChatHistory
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
    user_id = g.user_id # Get user_id from token_required decorator
    data = request.get_json()
    user_message = data.get('message')
    chat_session_id = data.get('chat_session_id') # Get session ID from request
    chat_style = data.get('chat_style', 'default') # Get chat style for initial prompt

    if not user_message:
        return jsonify({'error': 'Message is required'}), 400

    api_key = current_app.config.get('OPENAI_API_KEY') # Use OPENAI_API_KEY
    if not api_key:
        current_app.logger.error("OpenAI API key is not configured!")
        return jsonify({'error': 'Server configuration error: OpenAI API key missing.'}), 500

    # Retrieve recent chat history for context
    chat_history_docs = ChatHistory.get_history(user_id, chat_session_id, limit=10) # Limit context to 10 messages

    # Construct chat history for OpenAI API, including the new user message
    openai_chat_history = []
    
    # System message for chatbot personality and style
    # You can customize this prompt heavily for the desired psychological support style
    system_prompt = (
        f"당신은 사용자에게 심리적 안정과 통찰을 제공하는 AI 심리 상담사입니다. "
        f"사용자의 이야기를 경청하고 공감하며, 따뜻하고 비판단적인 태도로 대화해주세요. "
        f"사용자가 스스로 해결책을 찾을 수 있도록 돕고, 필요한 경우 전문가 상담을 제안할 수도 있습니다. "
        f"현재 대화 스타일은 '{chat_style}'입니다. "
        f"사용자의 질문에 직접적인 조언보다는 질문과 공감을 통해 스스로 생각할 기회를 제공하세요. "
        f"간결하고 명확하게 답변하며, 때로는 은유나 비유를 사용하여 깊이 있는 사고를 유도하세요."
    )
    openai_chat_history.append({"role": "system", "content": system_prompt})


    if chat_history_docs:
        for msg_doc in chat_history_docs:
            role = "user" if msg_doc["sender"] == "user" else "assistant" # OpenAI uses 'assistant' for AI
            openai_chat_history.append({"role": role, "content": msg_doc["message"]})
    
    openai_chat_history.append({"role": "user", "content": user_message})

    # Prepare payload for OpenAI Chat Completions API
    payload = {
        "model": "gpt-4o", # Recommended model for psychological counseling
        "messages": openai_chat_history,
        "temperature": 0.7, # Adjust creativity (0.0 - 1.0)
        "max_tokens": 500, # Limit response length
        "top_p": 1,
        "frequency_penalty": 0,
        "presence_penalty": 0
    }
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {api_key}' # Authorization header for OpenAI
    }
    api_url = "https://api.openai.com/v1/chat/completions" # OpenAI Chat Completions API endpoint

    ai_response_text = "죄송합니다. 현재 챗봇이 응답할 수 없습니다."
    
    # Store user message in MongoDB *before* calling OpenAI API
    try:
        if chat_session_id is None:
            inserted_user_message = ChatHistory.add_message(user_id, "user", user_message)
            chat_session_id = inserted_user_message.get("chat_session_id")
        else:
            ChatHistory.add_message(user_id, "user", user_message, chat_session_id)
        current_app.logger.info(f"User message saved: User ID {user_id}, Session ID {chat_session_id}")
    except Exception as e:
        current_app.logger.error(f"Failed to save user message to MongoDB: {e}")

    retries = 0
    max_retries = 3
    while retries < max_retries:
        try:
            response = requests.post(api_url, headers=headers, data=json.dumps(payload))
            response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
            result = response.json()

            if result.get("choices") and result["choices"][0].get("message") and result["choices"][0]["message"].get("content"):
                ai_response_text = result["choices"][0]["message"]["content"]
                break # Exit loop on successful response
            else:
                current_app.logger.warning(f"OpenAI API response missing choices or content: {result}")
                ai_response_text = "응답이 명확하지 않습니다. 다시 시도해 주세요."
                break

        except requests.exceptions.HTTPError as http_err:
            current_app.logger.error(f"HTTP error occurred during OpenAI API call: {http_err} - Response: {response.text}")
            if response.status_code == 429 and retries < max_retries -1: # Too many requests, retry
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


@chat_bp.route('/history', methods=['GET'])
@token_required
def get_chat_history():
    user_id = g.user_id
    chat_session_id = request.args.get('session_id')

    if not chat_session_id:
        return jsonify({'error': 'session_id is required'}), 400

    try:
        history = ChatHistory.get_history(user_id, chat_session_id)
        # Convert ObjectId to string for JSON serialization
        for item in history:
            item['_id'] = str(item['_id'])
            item['timestamp'] = item['timestamp'].isoformat() # Convert datetime to string
        return jsonify({'history': history}), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching chat history for user {user_id}, session {chat_session_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to retrieve chat history.'}), 500


@chat_bp.route('/sessions', methods=['GET'])
@token_required
def get_chat_sessions():
    user_id = g.user_id
    try:
        sessions = ChatHistory.get_all_sessions(user_id)
        return jsonify({'sessions': sessions}), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching chat sessions for user {user_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to retrieve chat sessions.'}), 500

@chat_bp.route('/session/<string:session_id>', methods=['DELETE'])
@token_required
def delete_chat_session(session_id):
    user_id = g.user_id
    try:
        deleted_count = ChatHistory.delete_session(user_id, session_id)
        if deleted_count > 0:
            return jsonify({'message': f'Session {session_id} and {deleted_count} messages deleted successfully.'}), 200
        else:
            return jsonify({'message': f'Session {session_id} not found or no messages deleted.'}), 404
    except Exception as e:
        current_app.logger.error(f"Error deleting chat session {session_id} for user {user_id}: {e}", exc_info=True)
        return jsonify({'error': 'Failed to delete chat session.'}), 500

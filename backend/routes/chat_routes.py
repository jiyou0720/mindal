# backend/routes/chat_routes.py
from flask import Blueprint, request, jsonify, g, current_app
from backend.extensions import mongo
from backend.routes.auth_routes import token_required
from backend.mongo_models import ChatHistory  # 수정됨
from bson.objectid import ObjectId
import datetime
import requests
import os

chat_bp = Blueprint('chat_api', __name__)

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

@chat_bp.route('/send_message', methods=['POST'])
@token_required
def send_message():
    user_id = g.user_id
    data = request.get_json()
    user_message = data.get('message')
    chat_style = data.get('chat_style', 'empathy')
    conversation_history = data.get('history', [])

    if not user_message:
        return jsonify({'message': '메시지를 입력해주세요.'}), 400

    if not GEMINI_API_KEY:
        current_app.logger.error("GEMINI_API_KEY is not set in environment variables.")
        return jsonify({'message': '서버 설정 오류: 챗봇 서비스를 이용할 수 없습니다.'}), 500

    try:
        chat_history_for_gemini = []
        for msg in conversation_history:
            chat_history_for_gemini.append({"role": msg["role"], "parts": [{"text": msg["text"]}]})
        chat_history_for_gemini.append({"role": "user", "parts": [{"text": user_message}]})

        # 상담 스타일 무관하게 empathy 프롬프트만 사용
        system_prompt = "당신은 사용자의 감정에 깊이 공감하고 위로를 제공하는 심리 상담 챗봇입니다. 따뜻하고 지지적인 언어를 사용해주세요."
        if not any(part.get("role") == "system" for part in chat_history_for_gemini):
            chat_history_for_gemini.insert(0, {"role": "system", "parts": [{"text": system_prompt}]})

        payload = {
            "contents": chat_history_for_gemini,
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 500
            }
        }

        headers = {"Content-Type": "application/json"}
        params = {"key": GEMINI_API_KEY}

        response = requests.post(GEMINI_API_URL, headers=headers, params=params, json=payload)
        response.raise_for_status()

        gemini_response_data = response.json()
        ai_text = ""
        if gemini_response_data and gemini_response_data.get('candidates'):
            ai_text = gemini_response_data['candidates'][0]['content']['parts'][0]['text']
        else:
            ai_text = "죄송합니다. AI 응답을 생성하는 데 문제가 발생했습니다."
            current_app.logger.error(f"Gemini API returned no candidates or unexpected structure: {gemini_response_data}")

        updated_conversation_history = conversation_history + [
            {"role": "user", "text": user_message},
            {"role": "model", "text": ai_text}
        ]

        chat_session_id = data.get('chat_session_id')

        if chat_session_id:
            mongo.db.chat_logs.update_one(
                {'_id': ObjectId(chat_session_id), 'user_id': user_id},
                {
                    '$push': {
                        'conversation_history': {"role": "user", "text": user_message}
                    }
                }
            )
            mongo.db.chat_logs.update_one(
                {'_id': ObjectId(chat_session_id), 'user_id': user_id},
                {
                    '$push': {
                        'conversation_history': {"role": "model", "text": ai_text}
                    },
                    '$set': {'updated_at': datetime.datetime.utcnow()}
                }
            )
            current_chat_log = mongo.db.chat_logs.find_one({'_id': ObjectId(chat_session_id)})
            current_chat_log['_id'] = str(current_chat_log['_id'])
        else:
            new_chat_log_entry = {
                'user_id': user_id,
                'conversation_history': [
                    {"role": "user", "text": user_message},
                    {"role": "model", "text": ai_text}
                ],
                'chat_style': chat_style,
                'created_at': datetime.datetime.utcnow(),
                'updated_at': datetime.datetime.utcnow()
            }
            result = mongo.db.chat_logs.insert_one(new_chat_log_entry)
            chat_session_id = str(result.inserted_id)
            current_chat_log = new_chat_log_entry
            current_chat_log['_id'] = chat_session_id

        return jsonify({
            'response': ai_text,
            'chat_session_id': chat_session_id,
            'history': updated_conversation_history
        }), 200

    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"Error communicating with Gemini API: {e}", exc_info=True)
        return jsonify({'message': 'AI 챗봇 서비스와 통신 중 오류가 발생했습니다.'}), 500
    except Exception as e:
        current_app.logger.error(f"Error in send_message: {e}", exc_info=True)
        return jsonify({'message': '메시지 처리 중 오류가 발생했습니다.'}), 500

@chat_bp.route('/history', methods=['GET'])
@token_required
def get_chat_history():
    user_id = g.user_id
    try:
        chat_logs = list(mongo.db.chat_logs.find({'user_id': user_id}).sort('created_at', -1))
        history_data = []
        for log in chat_logs:
            log['_id'] = str(log['_id'])
            summary_text = log.get('summary') or (log['conversation_history'][0]['text'][:100] + '...' if log['conversation_history'] else '대화 없음')
            history_data.append({
                'id': log['_id'],
                'chat_style': log['chat_style'],
                'summary': summary_text,
                'created_at': log['created_at'].isoformat(),
                'conversation_history': log['conversation_history']
            })
        return jsonify({'history': history_data}), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching chat history for user {user_id}: {e}", exc_info=True)
        return jsonify({'message': '대화 기록을 불러오는 데 실패했습니다.'}), 500

@chat_bp.route('/feedback', methods=['POST'])
@token_required
def submit_chatbot_feedback():
    user_id = g.user_id
    data = request.get_json()
    chat_session_id = data.get('chat_session_id')
    rating = data.get('rating')
    comment = data.get('comment')

    if not all([chat_session_id, rating]):
        return jsonify({'message': '세션 ID와 별점은 필수입니다.'}), 400

    if not (1 <= rating <= 5):
        return jsonify({'message': '별점은 1에서 5 사이여야 합니다.'}), 400

    try:
        feedback_collection = mongo.db.chatbot_feedback
        new_feedback = {
            'user_id': user_id,
            'chat_session_id': chat_session_id,
            'rating': rating,
            'comment': comment,
            'timestamp': datetime.datetime.utcnow()
        }
        result = feedback_collection.insert_one(new_feedback)

        mongo.db.chat_logs.update_one(
            {'_id': ObjectId(chat_session_id)},
            {'$set': {'feedback_id': str(result.inserted_id)}}
        )

        return jsonify({'message': '피드백이 성공적으로 제출되었습니다.'}), 201
    except Exception as e:
        current_app.logger.error(f"Error submitting chatbot feedback for user {user_id}: {e}", exc_info=True)
        return jsonify({'message': '피드백 제출에 실패했습니다.'}), 500

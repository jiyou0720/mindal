# backend/routes/chat_routes.py
from flask import Blueprint, request, jsonify, g, current_app
from backend.extensions import mongo
from backend.routes.auth_routes import token_required
from backend.mongo_models import ChatLog # ChatLog 모델 임포트
from bson.objectid import ObjectId
import datetime
import requests # Gemini API 호출을 위한 requests 임포트
import os # 환경 변수 로드를 위해 os 임포트

chat_bp = Blueprint('chat_api', __name__)

# Gemini API 키를 환경 변수에서 로드
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"

# 챗봇 메시지 전송 및 응답 받기
@chat_bp.route('/send_message', methods=['POST'])
@token_required
def send_message():
    user_id = g.user_id
    data = request.get_json()
    user_message = data.get('message')
    chat_style = data.get('chat_style', 'empathy') # 기본 상담 스타일: 공감형
    conversation_history = data.get('history', []) # 클라이언트에서 보낸 이전 대화 기록

    if not user_message:
        return jsonify({'message': '메시지를 입력해주세요.'}), 400
    
    if not GEMINI_API_KEY:
        current_app.logger.error("GEMINI_API_KEY is not set in environment variables.")
        return jsonify({'message': '서버 설정 오류: 챗봇 서비스를 이용할 수 없습니다.'}), 500

    try:
        # Gemini API에 전달할 대화 형식 구성
        # 각 메시지는 {"role": "user", "parts": [{"text": "..."}]} 또는 {"role": "model", "parts": [{"text": "..."}]}
        chat_history_for_gemini = []
        for msg in conversation_history:
            chat_history_for_gemini.append({"role": msg["role"], "parts": [{"text": msg["text"]}]})
        
        # 현재 사용자 메시지 추가
        chat_history_for_gemini.append({"role": "user", "parts": [{"text": user_message}]})

        # 상담 스타일에 따른 시스템 프롬프트 추가 (첫 메시지에만 적용되도록 로직 필요)
        # 여기서는 단순화를 위해 매번 프롬프트에 추가하는 방식으로 예시
        system_prompt = ""
        if chat_style == 'empathy':
            system_prompt = "당신은 사용자의 감정에 깊이 공감하고 위로를 제공하는 심리 상담 챗봇입니다. 따뜻하고 지지적인 언어를 사용해주세요."
        elif chat_style == 'cbt':
            system_prompt = "당신은 인지행동치료(CBT) 기반의 심리 상담 챗봇입니다. 사용자의 비합리적인 생각을 탐색하고 수정하도록 돕는 질문과 제안을 해주세요."
        elif chat_style == 'solution':
            system_prompt = "당신은 문제 해결에 초점을 맞춘 심리 상담 챗봇입니다. 사용자의 구체적인 문제 해결 방안을 함께 모색하고 목표 지향적인 조언을 해주세요."
        
        # 시스템 프롬프트를 대화 기록의 시작 부분에 추가
        if system_prompt and not any(part.get("role") == "system" for part in chat_history_for_gemini):
            chat_history_for_gemini.insert(0, {"role": "system", "parts": [{"text": system_prompt}]})

        payload = {
            "contents": chat_history_for_gemini,
            "generationConfig": {
                "temperature": 0.7, # 창의성 조절
                "maxOutputTokens": 500 # 최대 출력 토큰
            }
        }
        
        headers = {
            "Content-Type": "application/json"
        }
        params = {
            "key": GEMINI_API_KEY
        }

        response = requests.post(GEMINI_API_URL, headers=headers, params=params, json=payload)
        response.raise_for_status() # HTTP 오류 발생 시 예외 발생

        gemini_response_data = response.json()
        ai_text = ""
        if gemini_response_data and gemini_response_data.get('candidates'):
            ai_text = gemini_response_data['candidates'][0]['content']['parts'][0]['text']
        else:
            ai_text = "죄송합니다. AI 응답을 생성하는 데 문제가 발생했습니다."
            current_app.logger.error(f"Gemini API returned no candidates or unexpected structure: {gemini_response_data}")

        # 대화 기록 저장 (MongoDB)
        # 새로운 메시지를 포함한 전체 대화 기록을 저장
        updated_conversation_history = conversation_history + [
            {"role": "user", "text": user_message},
            {"role": "model", "text": ai_text}
        ]

        # 기존 대화가 있다면 업데이트, 없으면 새로 생성
        # 여기서는 매번 새로운 ChatLog 문서를 생성하는 대신,
        # 세션 ID나 특정 방식으로 대화 세션을 관리하여 업데이트하는 것이 더 효율적입니다.
        # 단순화를 위해 user_id와 chat_style 기준으로 최신 대화를 업데이트하거나,
        # 매번 새로운 로그를 저장하는 방식을 선택할 수 있습니다.
        # 여기서는 새로운 ChatLog 문서를 생성하는 방식으로 구현 (각 메시지 교환마다 저장)
        # 실제 앱에서는 하나의 대화 세션(session_id)에 대한 모든 메시지를 하나의 ChatLog 문서에 저장하는 것이 일반적입니다.
        
        # 임시로 user_id와 chat_style로만 찾아서 업데이트 (가장 최근 대화)
        # 또는 클라이언트에서 chat_session_id를 보내주면 해당 세션을 업데이트
        chat_session_id = data.get('chat_session_id') # 클라이언트에서 세션 ID를 보내준다고 가정

        if chat_session_id:
            # 기존 세션 업데이트
            mongo.db.chat_logs.update_one(
                {'_id': ObjectId(chat_session_id), 'user_id': user_id},
                {'$push': {'conversation_history': {"role": "user", "text": user_message},
                                                'conversation_history': {"role": "model", "text": ai_text}},
                 '$set': {'updated_at': datetime.datetime.utcnow()}} # updated_at 필드 추가 필요
            )
            # 업데이트 후 최신 대화 기록 다시 불러오기 (선택 사항)
            current_chat_log = mongo.db.chat_logs.find_one({'_id': ObjectId(chat_session_id)})
            current_chat_log['_id'] = str(current_chat_log['_id'])
        else:
            # 새 대화 세션 시작
            new_chat_log_entry = ChatLog(
                user_id=user_id,
                conversation_history=[
                    {"role": "user", "text": user_message},
                    {"role": "model", "text": ai_text}
                ],
                chat_style=chat_style
            )
            result = mongo.db.chat_logs.insert_one(new_chat_log_entry.to_dict())
            chat_session_id = str(result.inserted_id)
            current_chat_log = new_chat_log_entry.to_dict()
            current_chat_log['_id'] = chat_session_id

        return jsonify({
            'response': ai_text,
            'chat_session_id': chat_session_id,
            'history': updated_conversation_history # 클라이언트에게 업데이트된 전체 기록 반환
        }), 200

    except requests.exceptions.RequestException as e:
        current_app.logger.error(f"Error communicating with Gemini API: {e}", exc_info=True)
        return jsonify({'message': 'AI 챗봇 서비스와 통신 중 오류가 발생했습니다.'}), 500
    except Exception as e:
        current_app.logger.error(f"Error in send_message: {e}", exc_info=True)
        return jsonify({'message': '메시지 처리 중 오류가 발생했습니다.'}), 500

# 챗봇 대화 기록 조회
@chat_bp.route('/history', methods=['GET'])
@token_required
def get_chat_history():
    user_id = g.user_id
    try:
        # 사용자별 모든 챗봇 대화 세션 조회 (최신순)
        # 실제로는 페이지네이션을 적용하거나 특정 기간의 기록만 가져오는 것이 좋습니다.
        chat_logs = list(mongo.db.chat_logs.find({'user_id': user_id}).sort('created_at', -1))
        
        history_data = []
        for log in chat_logs:
            log['_id'] = str(log['_id'])
            # 대화 요약 (첫 100자 또는 특정 필드)
            summary_text = log.get('summary') or (log['conversation_history'][0]['text'][:100] + '...' if log['conversation_history'] else '대화 없음')
            history_data.append({
                'id': log['_id'],
                'chat_style': log['chat_style'],
                'summary': summary_text,
                'created_at': log['created_at'].isoformat(),
                'conversation_history': log['conversation_history'] # 전체 대화 기록도 포함
            })
        return jsonify({'history': history_data}), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching chat history for user {user_id}: {e}", exc_info=True)
        return jsonify({'message': '대화 기록을 불러오는 데 실패했습니다.'}), 500

# 챗봇 피드백 저장 (별점 및 코멘트)
@chat_bp.route('/feedback', methods=['POST'])
@token_required
def submit_chatbot_feedback():
    user_id = g.user_id
    data = request.get_json()
    chat_session_id = data.get('chat_session_id')
    rating = data.get('rating') # 1-5
    comment = data.get('comment')

    if not all([chat_session_id, rating]):
        return jsonify({'message': '세션 ID와 별점은 필수입니다.'}), 400
    
    if not (1 <= rating <= 5):
        return jsonify({'message': '별점은 1에서 5 사이여야 합니다.'}), 400

    try:
        # 피드백을 저장할 MongoDB 컬렉션 (admin_routes에서 사용하는 것과 동일)
        feedback_collection = mongo.db.chatbot_feedback
        
        new_feedback = {
            'user_id': user_id,
            'chat_session_id': chat_session_id,
            'rating': rating,
            'comment': comment,
            'timestamp': datetime.datetime.utcnow()
        }
        result = feedback_collection.insert_one(new_feedback)
        
        # (선택 사항) 해당 챗 세션에 피드백 ID 연결
        mongo.db.chat_logs.update_one(
            {'_id': ObjectId(chat_session_id)},
            {'$set': {'feedback_id': str(result.inserted_id)}}
        )

        return jsonify({'message': '피드백이 성공적으로 제출되었습니다.'}), 201
    except Exception as e:
        current_app.logger.error(f"Error submitting chatbot feedback for user {user_id}: {e}", exc_info=True)
        return jsonify({'message': '피드백 제출에 실패했습니다.'}), 500


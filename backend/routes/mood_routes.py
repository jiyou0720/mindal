from flask import Blueprint, request, jsonify, g, current_app
from backend.extensions import mongo
from backend.routes.auth_routes import token_required
import datetime
# FIX: Correct the import path for mongo_models
from backend.mongo_models import MoodEntry

mood_bp = Blueprint('mood_api', __name__)

# 감정 기록 추가 API
@mood_bp.route('/record', methods=['POST'])
@token_required
def record_mood():
    user_id = g.user_id
    data = request.get_json()
    mood = data.get('mood')

    if not mood:
        return jsonify({'message': '감정을 선택해주세요.'}), 400

    try:
        new_mood_entry = {
            'user_id': user_id,
            'mood': mood,
            'recorded_at': datetime.datetime.utcnow()
        }
        mongo.db.mood_entries.insert_one(new_mood_entry)
        return jsonify({'message': '오늘의 감정이 기록되었습니다.'}), 201
    except Exception as e:
        current_app.logger.error(f"감정 기록 중 오류 발생: {e}", exc_info=True)
        return jsonify({'message': '감정 기록 중 오류가 발생했습니다.'}), 500

# 특정 날짜의 감정 기록 조회 API
@mood_bp.route('/history', methods=['GET'])
@token_required
def get_mood_history():
    user_id = g.user_id
    date_str = request.args.get('date') # 예: 'YYYY-MM-DD'

    if not date_str:
        return jsonify({'message': '날짜를 지정해주세요.'}), 400
        
    try:
        start_date = datetime.datetime.strptime(date_str, '%Y-%m-%d')
        end_date = start_date + datetime.timedelta(days=1)

        mood_entries = mongo.db.mood_entries.find({
            'user_id': user_id,
            'recorded_at': {
                '$gte': start_date,
                '$lt': end_date
            }
        }).sort('recorded_at', -1)

        history = [{
            'mood': entry['mood'], 
            'recorded_at': entry['recorded_at'].isoformat()
        } for entry in mood_entries]
        
        return jsonify({'history': history})

    except ValueError:
        return jsonify({'message': '날짜 형식이 올바르지 않습니다. (YYYY-MM-DD)'}), 400
    except Exception as e:
        current_app.logger.error(f"감정 이력 조회 중 오류 발생: {e}", exc_info=True)
        return jsonify({'message': '데이터를 불러오는 데 실패했습니다.'}), 500


#생각
#고민중인 사안. 감정카드 발급? 우리가 디자인 한 카드중에 맞는 감정의 카드를 랜덤으로 발급 (이러면 한 감정에 대한 감정카드들이 여러개 있어야함.)

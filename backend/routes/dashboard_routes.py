from flask import Blueprint, jsonify, g, current_app
from backend.extensions import db, mongo
from backend.routes.auth_routes import token_required
from backend.maria_models import User
from collections import Counter

dashboard_bp = Blueprint('dashboard_api', __name__)

@dashboard_bp.route('/stats', methods=['GET'])
@token_required
def get_user_dashboard_stats():
    """현재 로그인된 사용자의 대시보드 통계 정보를 반환합니다."""
    user_id = g.user_id
    try:
        # [수정] 안정적인 MongoDB 연결을 위해 db 객체를 직접 가져옵니다.
        db_name = current_app.config.get("MONGO_DBNAME")
        if not db_name or not mongo.cx:
            raise ConnectionError("MongoDB is not configured or connected.")
        db_mongo = mongo.cx[db_name]

        # AI 채팅 기록 (현재 모델이 없으므로 임시로 0을 반환)
        # TODO: AI 채팅 기록을 MongoDB에서 가져오는 로직 구현 필요
        ai_chat_count = 0

        # 작성된 일기 수 (MongoDB)
        diary_entry_count = db_mongo.diary_entries.count_documents({'user_id': user_id})

        # 총 사용자 수 (MariaDB) - 이 값은 모든 사용자에게 동일하게 보임
        total_user_count = User.query.count()

        # 가장 빈번한 감정 (MongoDB에서 최근 30개 기록 기준)
        mood_entries = db_mongo.mood_entries.find({'user_id': user_id}).sort('recorded_at', -1).limit(30)
        moods = [entry['mood'] for entry in mood_entries]
        most_frequent_mood = "분석 중"
        if moods:
            # Counter를 사용하여 가장 빈번한 감정 찾기
            most_frequent_mood = Counter(moods).most_common(1)[0][0]

        stats = {
            'ai_chat_count': ai_chat_count,
            'diary_entry_count': diary_entry_count,
            'community_post_count': total_user_count, # 라벨이 '총 사용자'이므로 전체 사용자 수를 반환
            'most_frequent_mood': most_frequent_mood
        }
        return jsonify(stats), 200
    except Exception as e:
        current_app.logger.error(f"대시보드 통계 조회 중 오류 발생: {e}", exc_info=True)
        return jsonify({'message': '대시보드 통계 정보를 불러오는 데 실패했습니다.'}), 500
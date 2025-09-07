from flask import Blueprint, request, jsonify, g, current_app
from backend.extensions import db, mongo
from backend.maria_models import User
from backend.mongo_models import DiaryEntry, MoodEntry
from backend.routes.auth_routes import token_required
from bson.objectid import ObjectId
import datetime

diary_bp = Blueprint('diary_api', __name__)

# [수정] 안정적인 MongoDB 연결을 위한 헬퍼 함수
def get_mongo_db():
    db_name = current_app.config.get("MONGO_DBNAME")
    if not db_name or not mongo.cx:
        raise ConnectionError("MongoDB is not configured or connected.")
    return mongo.cx[db_name]

@diary_bp.route('/entries', methods=['POST'])
@token_required
def create_diary_entry():
    data = request.get_json()
    user_id = g.user_id
    title = data.get('title')
    content = data.get('content')
    date = data.get('date')
    mood_emoji_key = data.get('mood_emoji_key')

    if not all([title, content, date, mood_emoji_key]):
        return jsonify({'message': '제목, 내용, 날짜, 기분 이모지 키를 모두 입력해주세요.'}), 400

    try:
        datetime.datetime.strptime(date, '%Y-%m-%d')
    except ValueError:
        return jsonify({'message': '날짜 형식이 올바르지 않습니다. YYYY-MM-DD 형식으로 입력해주세요.'}), 400

    new_entry = DiaryEntry(user_id=user_id, title=title, content=content, date=date, mood_emoji_key=mood_emoji_key)

    try:
        db_mongo = get_mongo_db()
        db_mongo.diary_entries.insert_one(new_entry.to_dict())
        return jsonify({'message': '일기 작성이 성공적으로 완료되었습니다!', 'diary_entry': {'_id': str(new_entry._id)}}), 201
    except Exception as e:
        current_app.logger.error(f"일기 저장 중 MongoDB 오류: {e}", exc_info=True)
        return jsonify({'message': '일기 저장 중 오류가 발생했습니다.'}), 500

@diary_bp.route('/entries', methods=['GET'])
@token_required
def get_diary_entries():
    user_id = g.user_id
    date = request.args.get('date')

    query = {'user_id': user_id}
    if date:
        query['date'] = date
        
    try:
        db_mongo = get_mongo_db()
        entries_cursor = db_mongo.diary_entries.find(query).sort('created_at', -1)
        entries_data = []
        for entry in entries_cursor:
            entry['_id'] = str(entry['_id'])
            if 'created_at' in entry and isinstance(entry['created_at'], datetime.datetime):
                entry['created_at'] = entry['created_at'].isoformat()
            if 'updated_at' in entry and isinstance(entry['updated_at'], datetime.datetime):
                entry['updated_at'] = entry['updated_at'].isoformat()
            entries_data.append(entry)
        
        if date and entries_data:
            return jsonify({'diary_entry': entries_data[0]}), 200
        elif date and not entries_data:
            return jsonify({'message': '해당 날짜의 일기를 찾을 수 없습니다.'}), 404
        else:
            return jsonify(entries_data), 200
    except Exception as e:
        current_app.logger.error(f"일기 조회 중 MongoDB 오류: {e}", exc_info=True)
        return jsonify({'message': '일기 조회 중 오류가 발생했습니다.'}), 500

@diary_bp.route('/entries/month_summary', methods=['GET'])
@token_required
def get_month_summary():
    user_id = g.user_id
    year_str = request.args.get('year')
    month_str = request.args.get('month')

    if not year_str or not month_str:
        return jsonify({'message': '년도와 월을 모두 입력해주세요.'}), 400

    try:
        year = int(year_str)
        month = int(month_str)
    except ValueError:
        return jsonify({'message': '년도와 월은 유효한 숫자여야 합니다.'}), 400

    start_date = datetime.datetime(year, month, 1)
    end_date = datetime.datetime(year, month + 1, 1) if month < 12 else datetime.datetime(year + 1, 1, 1)

    query = {
        'user_id': user_id,
        'date': {
            '$gte': start_date.strftime('%Y-%m-%d'),
            '$lt': end_date.strftime('%Y-%m-%d')
        }
    }

    monthly_summary = {}
    try:
        db_mongo = get_mongo_db()
        entries_cursor = db_mongo.diary_entries.find(query, {'date': 1, 'mood_emoji_key': 1})
        for entry in entries_cursor:
            date_key = entry['date']
            monthly_summary[date_key] = {'has_entry': True, 'mood_emoji_key': entry.get('mood_emoji_key')}
        
        return jsonify({'summary': monthly_summary}), 200
    except Exception as e:
        current_app.logger.error(f"월별 요약 조회 중 MongoDB 오류: {e}", exc_info=True)
        return jsonify({'message': '월별 요약 정보를 불러오는 데 실패했습니다.'}), 500

@diary_bp.route('/entries/<string:entry_id>', methods=['GET'])
@token_required
def get_diary_entry_detail(entry_id):
    user_id = g.user_id
    try:
        db_mongo = get_mongo_db()
        entry = db_mongo.diary_entries.find_one({'_id': ObjectId(entry_id), 'user_id': user_id})
        if not entry:
            return jsonify({'message': '일기를 찾을 수 없습니다.'}), 404
        
        entry['_id'] = str(entry['_id'])
        if 'created_at' in entry and isinstance(entry['created_at'], datetime.datetime):
            entry['created_at'] = entry['created_at'].isoformat()
        if 'updated_at' in entry and isinstance(entry['updated_at'], datetime.datetime):
            entry['updated_at'] = entry['updated_at'].isoformat()
            
        return jsonify(entry), 200
    except Exception as e:
        current_app.logger.error(f"특정 일기 조회 중 MongoDB 오류: {e}", exc_info=True)
        return jsonify({'message': '일기 조회 중 오류가 발생했습니다.'}), 500

@diary_bp.route('/entries/<string:entry_id>', methods=['PUT'])
@token_required
def update_diary_entry(entry_id):
    data = request.get_json()
    user_id = g.user_id
    title = data.get('title')
    content = data.get('content')
    date = data.get('date')
    mood_emoji_key = data.get('mood_emoji_key')

    update_fields = {'updated_at': datetime.datetime.utcnow()}
    if title: update_fields['title'] = title
    if content: update_fields['content'] = content
    if date:
        try:
            datetime.datetime.strptime(date, '%Y-%m-%d')
            update_fields['date'] = date
        except ValueError:
            return jsonify({'message': '날짜 형식이 올바르지 않습니다.'}), 400
    if mood_emoji_key: update_fields['mood_emoji_key'] = mood_emoji_key
    
    try:
        db_mongo = get_mongo_db()
        result = db_mongo.diary_entries.update_one(
            {'_id': ObjectId(entry_id), 'user_id': user_id},
            {'$set': update_fields}
        )
        if result.matched_count == 0:
            return jsonify({'message': '일기를 찾을 수 없거나 수정 권한이 없습니다.'}), 404
        return jsonify({'message': '일기가 성공적으로 수정되었습니다!'}), 200
    except Exception as e:
        current_app.logger.error(f"일기 수정 중 MongoDB 오류: {e}", exc_info=True)
        return jsonify({'message': '일기 수정 중 오류가 발생했습니다.'}), 500

@diary_bp.route('/entries/<string:entry_id>', methods=['DELETE'])
@token_required
def delete_diary_entry(entry_id):
    user_id = g.user_id
    try:
        db_mongo = get_mongo_db()
        result = db_mongo.diary_entries.delete_one({'_id': ObjectId(entry_id), 'user_id': user_id})
        if result.deleted_count == 0:
            return jsonify({'message': '일기를 찾을 수 없거나 삭제 권한이 없습니다.'}), 404
        return jsonify({'message': '일기가 성공적으로 삭제되었습니다!'}), 200
    except Exception as e:
        current_app.logger.error(f"일기 삭제 중 MongoDB 오류: {e}", exc_info=True)
        return jsonify({'message': '일기 삭제 중 오류가 발생했습니다.'}), 500

@diary_bp.route('/moods', methods=['POST'])
@token_required
def create_mood_entry():
    data = request.get_json()
    user_id = g.user_id
    date = data.get('date')
    mood_score = data.get('mood_score')

    if not all([date, mood_score is not None]):
        return jsonify({'message': '날짜와 기분 점수를 모두 입력해주세요.'}), 400
    if not isinstance(mood_score, (int, float)) or not (1 <= mood_score <= 5):
        return jsonify({'message': '기분 점수는 1에서 5 사이의 숫자여야 합니다.'}), 400

    try:
        datetime.datetime.strptime(date, '%Y-%m-%d')
    except ValueError:
        return jsonify({'message': '날짜 형식이 올바르지 않습니다.'}), 400

    new_mood_entry = MoodEntry(user_id=user_id, date=date, mood_score=mood_score)

    try:
        db_mongo = get_mongo_db()
        db_mongo.mood_entries.insert_one(new_mood_entry.to_dict())
        return jsonify({'message': '기분 기록이 성공적으로 완료되었습니다!'}), 201
    except Exception as e:
        current_app.logger.error(f"기분 기록 저장 중 MongoDB 오류: {e}", exc_info=True)
        return jsonify({'message': '기분 기록 저장 중 오류가 발생했습니다.'}), 500

@diary_bp.route('/moods', methods=['GET'])
@token_required
def get_mood_entries():
    user_id = g.user_id
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')

    query = {'user_id': user_id}
    if start_date and end_date:
        query['date'] = {'$gte': start_date, '$lte': end_date}
        
    try:
        db_mongo = get_mongo_db()
        mood_entries_cursor = db_mongo.mood_entries.find(query).sort('date', 1)
        mood_entries_data = []
        for entry in mood_entries_cursor:
            entry['_id'] = str(entry['_id'])
            if 'timestamp' in entry and isinstance(entry['timestamp'], datetime.datetime):
                entry['timestamp'] = entry['timestamp'].isoformat()
            mood_entries_data.append(entry)
        
        return jsonify(mood_entries_data), 200
    except Exception as e:
        current_app.logger.error(f"기분 기록 조회 중 MongoDB 오류: {e}", exc_info=True)
        return jsonify({'message': '기분 기록 조회 중 오류가 발생했습니다.'}), 500

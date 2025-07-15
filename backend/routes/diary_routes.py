# backend/routes/diary_routes.py
from flask import Blueprint, request, jsonify, g, current_app
from flask_pymongo import PyMongo
from auth import token_required
from mongo_models import DiaryEntry
from maria_models import User
from extensions import db
from bson.objectid import ObjectId
import datetime

# Blueprint 생성
diary_bp = Blueprint('diary_api', __name__)

@diary_bp.record_once
def record(state):
    state.app.config['MONGO_DB'] = PyMongo(state.app).db

# MongoDB 컬렉션 참조 함수
def get_diary_collection():
    return current_app.config['MONGO_DB'].diaries

# --- 일기 관련 API 엔드포인트 ---

# 1. 새 일기 생성 또는 기존 일기 업데이트
@diary_bp.route('/entries', methods=['POST'])
@token_required # 로그인된 사용자만 일기를 작성할 수 있도록
def create_or_update_diary_entry():
    data = request.get_json()
    # title 필드는 현재 사용되지 않으므로 제거하거나 None으로 처리
    title = data.get('title', None) # 일기 제목 (선택 사항)
    content = data.get('content')
    date = data.get('date') # 일기 날짜 (YYYY-MM-DD)
    mood_emoji_key = data.get('mood_emoji_key') # 선택된 이모티콘 키

    user_id = int(g.user_id) # token_required 데코레이터에서 설정된 사용자 ID

    if not content or not date or not mood_emoji_key: # 내용은 필수, 날짜와 기분도 필수
        return jsonify({'message': 'Content, date, and mood emoji are required'}), 400

    # User 모델에서 사용자 존재 확인 (선택 사항이지만 안전을 위해)
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'message': 'User not found'}), 404

    # 해당 날짜에 이미 일기가 있는지 확인
    existing_entry_data = get_diary_collection().find_one({'user_id': user_id, 'date': date})

    if existing_entry_data:
        # 기존 일기 업데이트
        update_fields = {
            'content': content,
            'mood_emoji_key': mood_emoji_key,
            'updated_at': datetime.datetime.utcnow()
        }
        if title is not None: # 제목이 제공되면 업데이트
            update_fields['title'] = title

        get_diary_collection().update_one(
            {'_id': existing_entry_data['_id']},
            {'$set': update_fields}
        )
        updated_entry = get_diary_collection().find_one({'_id': existing_entry_data['_id']})
        return jsonify({
            'message': 'Diary entry updated successfully!',
            'diary_entry': DiaryEntry.from_mongo(updated_entry).to_dict()
        }), 200
    else:
        # 새 일기 생성
        new_entry = DiaryEntry(
            user_id=user_id,
            title=title,
            content=content,
            date=date,
            mood_emoji_key=mood_emoji_key
        )
        result = get_diary_collection().insert_one(new_entry.to_dict())
        new_entry._id = result.inserted_id

        return jsonify({
            'message': 'Diary entry created successfully!',
            'diary_entry': new_entry.to_dict()
        }), 201


# 2. 특정 날짜의 일기 조회 (GET)
@diary_bp.route('/entries/by_date', methods=['GET'])
@token_required # 로그인된 사용자만 조회할 수 있도록
def get_diary_entry_by_date():
    user_id = int(g.user_id) # 현재 로그인된 사용자 ID
    date_str = request.args.get('date') # 쿼리 파라미터에서 'date' 값 가져오기 (예: ?date=YYYY-MM-DD)

    if not date_str:
        return jsonify({'message': '날짜(date) 파라미터가 누락되었습니다.'}), 400

    # MongoDB에서 해당 user_id와 date에 맞는 일기 엔트리 조회
    diary_entry_data = get_diary_collection().find_one({'user_id': user_id, 'date': date_str})

    if not diary_entry_data:
        # 해당 날짜에 일기가 없으면 404 Not Found 응답
        return jsonify({'message': f'해당 날짜({date_str})에 일기를 찾을 수 없습니다.'}), 404
    
    # MongoDB의 ObjectId와 datetime 객체를 JSON 직렬화 가능하도록 변환
    if '_id' in diary_entry_data:
        diary_entry_data['_id'] = str(diary_entry_data['_id'])
    if 'created_at' in diary_entry_data and isinstance(diary_entry_data['created_at'], datetime.datetime):
        diary_entry_data['created_at'] = diary_entry_data['created_at'].isoformat()
    if 'updated_at' in diary_entry_data and isinstance(diary_entry_data['updated_at'], datetime.datetime):
        diary_entry_data['updated_at'] = diary_entry_data['updated_at'].isoformat()

    # 일기 데이터를 JSON 형태로 반환
    return jsonify({
        'message': '일기를 성공적으로 조회했습니다!',
        'diary_entry': diary_entry_data
    }), 200

# 3. 특정 사용자의 특정 월 일기 요약 조회 (캘린더에 이모티콘 표시용)
@diary_bp.route('/entries/month_summary', methods=['GET'])
@token_required
def get_month_diary_summary():
    user_id = int(g.user_id)
    year = request.args.get('year', type=int)
    month = request.args.get('month', type=int) # 1-12월

    if year is None or month is None:
        return jsonify({'message': 'Year and month parameters are required'}), 400

    # 해당 월의 시작일과 다음 월의 시작일 계산
    start_of_month = datetime.datetime(year, month, 1)
    # 다음 달의 첫 날을 구해서 해당 월의 마지막 날까지의 범위를 만듭니다.
    # MongoDB는 ISO 8601 문자열 비교가 가능하므로, 날짜 문자열로 쿼리합니다.
    if month == 12:
        end_of_month = datetime.datetime(year + 1, 1, 1)
    else:
        end_of_month = datetime.datetime(year, month + 1, 1)

    # MongoDB 쿼리 (날짜 문자열 비교)
    # created_at 필드를 기준으로 날짜 범위를 쿼리하는 대신,
    # DiaryEntry 모델에 추가된 'date' 필드를 기준으로 쿼리합니다.
    # 'date' 필드는 YYYY-MM-DD 문자열 형식이어야 합니다.
    # 따라서 쿼리 범위도 문자열로 변환하여 비교합니다.
    start_date_str = start_of_month.strftime('%Y-%m-%d')
    # end_date_str은 해당 월의 마지막 날짜 문자열
    end_date_str = (end_of_month - datetime.timedelta(days=1)).strftime('%Y-%m-%d')

    diary_entries_data = get_diary_collection().find({
        'user_id': user_id,
        'date': {'$gte': start_date_str, '$lte': end_date_str}
    })

    summary = {}
    for entry in diary_entries_data:
        date_key = entry['date'] # YYYY-MM-DD
        summary[date_key] = {
            'mood_emoji_key': entry.get('mood_emoji_key'),
            'has_entry': True
        }

    return jsonify({
        'message': 'Monthly diary summary retrieved successfully!',
        'summary': summary
    }), 200

# 4. 특정 일기 삭제 (기존 기능 유지)
@diary_bp.route('/entries/<entry_id>', methods=['DELETE'])
@token_required
def delete_diary_entry(entry_id):
    user_id = int(g.user_id)

    try:
        entry_obj_id = ObjectId(entry_id)
    except Exception:
        return jsonify({'message': 'Invalid Diary Entry ID'}), 400

    # 일기 존재 여부 및 소유권 확인 후 삭제
    result = get_diary_collection().delete_one({'_id': entry_obj_id, 'user_id': user_id})

    if result.deleted_count == 0:
        return jsonify({'message': 'Diary entry not found or unauthorized'}), 404

    return jsonify({'message': 'Diary entry deleted successfully!'}), 200

# 5. 기존 '모든 일기 조회'는 사용되지 않으므로 제거하거나 주석 처리합니다.
# @diary_bp.route('/entries', methods=['GET'])
# @token_required
# def get_all_diary_entries():
#     user_id = int(g.user_id)
#     diary_entries_data = get_diary_collection().find({'user_id': user_id}).sort('created_at', -1)
#     diary_entries = [DiaryEntry.from_mongo(entry).to_dict() for entry in diary_entries_data]
#     return jsonify({
#         'message': 'Diary entries retrieved successfully!',
#         'diary_entries': diary_entries
#     }), 200

# 6. 특정 일기 조회 (ID 기준)는 사용되지 않으므로 제거하거나 주석 처리합니다.
# @diary_bp.route('/entries/<entry_id>', methods=['GET'])
# @token_required
# def get_diary_entry_by_id_old(entry_id):
#     user_id = int(g.user_id)
#     try:
#         entry_obj_id = ObjectId(entry_id)
#     except Exception:
#         return jsonify({'message': 'Invalid Diary Entry ID'}), 400
#     diary_entry_data = get_diary_collection().find_one({'_id': entry_obj_id, 'user_id': user_id})
#     if not diary_entry_data:
#         return jsonify({'message': 'Diary entry not found or unauthorized'}), 404
#     return jsonify({
#         'message': 'Diary entry retrieved successfully!',
#         'diary_entry': DiaryEntry.from_mongo(diary_entry_data).to_dict()
#     }), 200

# 7. 일기 수정 (ID 기준)은 POST /entries 에서 통합 처리되므로 제거하거나 주석 처리합니다.
# @diary_bp.route('/entries/<entry_id>', methods=['PUT'])
# @token_required
# def update_diary_entry_old(entry_id):
#     data = request.get_json()
#     title = data.get('title')
#     content = data.get('content')
#     user_id = int(g.user_id)
#     try:
#         entry_obj_id = ObjectId(entry_id)
#         return jsonify({'message': 'Invalid Diary Entry ID'}), 400
#     existing_entry = get_diary_collection().find_one({'_id': entry_obj_id, 'user_id': user_id})
#     if not existing_entry:
#         return jsonify({'message': 'Diary entry not found or unauthorized'}), 404
#     update_fields = {}
#     if title is not None:
#         update_fields['title'] = title
#     if content is not None:
#         update_fields['content'] = content
#     update_fields['updated_at'] = datetime.datetime.utcnow()
#     get_diary_collection().update_one(
#         {'_id': entry_obj_id},
#         {'$set': update_fields}
#     )
#     updated_entry_data = get_diary_collection().find_one({'_id': entry_obj_id})
#     return jsonify({
#         'message': 'Diary entry updated successfully!',
#         'diary_entry': DiaryEntry.from_mongo(updated_entry_data).to_dict()
#     }), 200

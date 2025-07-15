# backend/routes/mood_routes.py
from flask import Blueprint, request, jsonify, g, current_app
from flask_pymongo import PyMongo
from auth import token_required
from mongo_models import MoodEntry
from bson.objectid import ObjectId
import datetime

# Blueprint 생성
mood_bp = Blueprint('mood_api', __name__)

@mood_bp.record_once
def record(state):
    # MongoDB 인스턴스를 애플리케이션 컨텍스트에 등록 (diary_routes.py와 유사)
    state.app.config['MONGO_DB'] = PyMongo(state.app).db

# MongoDB 컬렉션 참조 함수
def get_mood_collection():
    return current_app.config['MONGO_DB'].mood_entries # 'mood_entries' 컬렉션 사용

# --- 감정 카드 관련 API 엔드포인트 ---

# 1. 새 감정 카드 생성
@mood_bp.route('/moods', methods=['POST'])
@token_required # 로그인된 사용자만 감정 카드를 작성할 수 있도록
def create_mood_entry():
    data = request.get_json()
    mood_type = data.get('mood_type')
    description = data.get('description') # 선택적

    if not mood_type:
        return jsonify({'message': 'Mood type is required'}), 400

    user_id = g.user_id # token_required 데코레이터에서 설정된 사용자 ID

    new_entry = MoodEntry(
        user_id=user_id,
        mood_type=mood_type,
        description=description
    )
    inserted_entry = get_mood_collection().insert_one(new_entry.to_dict())
    new_entry._id = inserted_entry.inserted_id # 생성된 _id 설정

    return jsonify({
        'message': 'Mood entry created successfully!',
        'mood_entry': new_entry.to_dict()
    }), 201

# 2. 모든 감정 카드 조회 (최신순 정렬)
@mood_bp.route('/moods', methods=['GET'])
@token_required
def get_all_mood_entries():
    user_id = g.user_id
    mood_entries_data = get_mood_collection().find({'user_id': user_id}).sort('created_at', -1)
    mood_entries = [MoodEntry.from_mongo(entry).to_dict() for entry in mood_entries_data]
    return jsonify({
        'message': 'All mood entries retrieved successfully!',
        'mood_entries': mood_entries
    }), 200

# 3. 특정 감정 카드 조회 (ID 기준)
@mood_bp.route('/moods/<string:mood_id>', methods=['GET'])
@token_required
def get_mood_entry_by_id(mood_id):
    user_id = g.user_id
    try:
        mood_obj_id = ObjectId(mood_id)
    except Exception:
        return jsonify({'message': 'Invalid Mood Entry ID'}), 400

    mood_entry_data = get_mood_collection().find_one({'_id': mood_obj_id, 'user_id': user_id})

    if not mood_entry_data:
        return jsonify({'message': 'Mood entry not found or unauthorized'}), 404

    return jsonify({
        'message': 'Mood entry retrieved successfully!',
        'mood_entry': MoodEntry.from_mongo(mood_entry_data).to_dict()
    }), 200

# 4. 감정 카드 수정
@mood_bp.route('/moods/<string:mood_id>', methods=['PUT'])
@token_required
def update_mood_entry(mood_id):
    data = request.get_json()
    mood_type = data.get('mood_type')
    description = data.get('description')
    user_id = g.user_id

    try:
        mood_obj_id = ObjectId(mood_id)
    except Exception:
        return jsonify({'message': 'Invalid Mood Entry ID'}), 400

    # 기존 감정 카드 존재 여부 및 소유권 확인
    existing_entry = get_mood_collection().find_one({'_id': mood_obj_id, 'user_id': user_id})
    if not existing_entry:
        return jsonify({'message': 'Mood entry not found or unauthorized'}), 404

    update_fields = {}
    if mood_type is not None:
        update_fields['mood_type'] = mood_type
    if description is not None:
        update_fields['description'] = description
    update_fields['updated_at'] = datetime.datetime.utcnow()

    get_mood_collection().update_one(
        {'_id': mood_obj_id},
        {'$set': update_fields}
    )

    updated_entry_data = get_mood_collection().find_one({'_id': mood_obj_id})
    return jsonify({
        'message': 'Mood entry updated successfully!',
        'mood_entry': MoodEntry.from_mongo(updated_entry_data).to_dict()
    }), 200

# 5. 감정 카드 삭제
@mood_bp.route('/moods/<mood_id>', methods=['DELETE'])
@token_required
def delete_mood_entry(mood_id):
    user_id = g.user_id

    try:
        mood_obj_id = ObjectId(mood_id)
    except Exception:
        return jsonify({'message': 'Invalid Mood Entry ID'}), 400

    result = get_mood_collection().delete_one({'_id': mood_obj_id, 'user_id': user_id})

    if result.deleted_count == 0:
        return jsonify({'message': 'Mood entry not found or unauthorized'}), 404

    return jsonify({'message': 'Mood entry deleted successfully!'}), 200
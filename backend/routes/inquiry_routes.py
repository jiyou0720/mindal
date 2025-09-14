from flask import Blueprint, request, jsonify, g, current_app
from backend.extensions import mongo
from backend.routes.auth_routes import token_required
from backend.mongo_models import Inquiry
from bson.objectid import ObjectId
import datetime

inquiry_bp = Blueprint('inquiry_api', __name__)

# [수정] 안정적인 MongoDB 연결을 위한 헬퍼 함수
def get_mongo_db():
    db_name = current_app.config.get("MONGO_DBNAME")
    if not db_name or not mongo.cx:
        raise ConnectionError("MongoDB is not configured or connected.")
    return mongo.cx[db_name]

@inquiry_bp.route('/submit', methods=['POST'])
@token_required
def submit_inquiry():
    user_id = g.user_id
    username = g.username
    email = g.email
    
    data = request.get_json()
    title = data.get('title')
    content = data.get('content')

    if not all([title, content]):
        return jsonify({'message': '제목과 내용을 모두 입력해주세요.'}), 400

    new_inquiry = Inquiry(user_id=user_id, username=username, email=email, title=title, content=content)

    try:
        db_mongo = get_mongo_db()
        db_mongo.inquiries.insert_one(new_inquiry.to_dict())
        return jsonify({'message': '문의사항이 성공적으로 제출되었습니다.'}), 201
    except Exception as e:
        current_app.logger.error(f"문의사항 제출 중 오류 발생: {e}", exc_info=True)
        return jsonify({'message': '문의사항 제출에 실패했습니다.'}), 500

@inquiry_bp.route('/my_inquiries', methods=['GET'])
@token_required
def get_my_inquiries():
    user_id = g.user_id
    try:
        db_mongo = get_mongo_db()
        my_inquiries = list(db_mongo.inquiries.find({'user_id': user_id}).sort('created_at', -1))
        
        for inquiry in my_inquiries:
            inquiry['_id'] = str(inquiry['_id'])
            if 'created_at' in inquiry and isinstance(inquiry['created_at'], datetime.datetime):
                inquiry['created_at'] = inquiry['created_at'].isoformat()
            if 'replied_at' in inquiry and isinstance(inquiry['replied_at'], datetime.datetime):
                inquiry['replied_at'] = inquiry['replied_at'].isoformat()
            
        return jsonify({'inquiries': my_inquiries}), 200
    except Exception as e:
        current_app.logger.error(f"사용자 문의사항 목록 조회 중 오류 발생 (user_id: {user_id}): {e}", exc_info=True)
        return jsonify({'message': '문의사항 목록을 불러오는 데 실패했습니다.'}), 500

@inquiry_bp.route('/my_inquiries/<string:inquiry_id>', methods=['GET'])
@token_required
def get_my_inquiry_detail(inquiry_id):
    user_id = g.user_id
    try:
        db_mongo = get_mongo_db()
        inquiry = db_mongo.inquiries.find_one({'_id': ObjectId(inquiry_id), 'user_id': user_id})
        if not inquiry:
            return jsonify({'message': '문의사항을 찾을 수 없거나 접근 권한이 없습니다.'}), 404
        
        inquiry['_id'] = str(inquiry['_id'])
        if 'created_at' in inquiry and isinstance(inquiry['created_at'], datetime.datetime):
            inquiry['created_at'] = inquiry['created_at'].isoformat()
        if 'replied_at' in inquiry and isinstance(inquiry['replied_at'], datetime.datetime):
            inquiry['replied_at'] = inquiry['replied_at'].isoformat()

        return jsonify(inquiry), 200
    except Exception as e:
        current_app.logger.error(f"사용자 문의사항 상세 조회 중 오류 발생 (inquiry_id: {inquiry_id}, user_id: {user_id}): {e}", exc_info=True)
        return jsonify({'message': '문의사항 상세 정보를 불러오는 데 실패했습니다.'}), 500
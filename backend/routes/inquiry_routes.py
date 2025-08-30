# backend/routes/inquiry_routes.py
from flask import Blueprint, request, jsonify, g, current_app
from backend.extensions import mongo
from backend.routes.auth_routes import token_required
from backend.mongo_models import Inquiry
from bson.objectid import ObjectId
import datetime

inquiry_bp = Blueprint('inquiry_api', __name__)

@inquiry_bp.route('/submit', methods=['POST'])
@token_required
def submit_inquiry():
    """사용자 문의사항을 제출합니다."""
    user_id = g.user_id
    username = g.username
    email = g.email # g.email을 사용하여 이메일 가져오기
    
    data = request.get_json()
    title = data.get('title')
    content = data.get('content')

    if not all([title, content]):
        return jsonify({'message': '제목과 내용을 모두 입력해주세요.'}), 400

    new_inquiry = Inquiry(
        user_id=user_id,
        username=username,
        email=email, # 이메일 저장
        title=title,
        content=content
    )

    try:
        mongo.db.inquiries.insert_one(new_inquiry.to_dict())
        return jsonify({'message': '문의사항이 성공적으로 제출되었습니다.'}), 201
    except Exception as e:
        current_app.logger.error(f"문의사항 제출 중 오류 발생: {e}", exc_info=True)
        return jsonify({'message': '문의사항 제출에 실패했습니다.'}), 500

@inquiry_bp.route('/my_inquiries', methods=['GET'])
@token_required
def get_my_inquiries():
    """현재 로그인된 사용자의 문의사항 목록을 조회합니다."""
    user_id = g.user_id
    try:
        my_inquiries = list(mongo.db.inquiries.find({'user_id': user_id}).sort('created_at', -1))
        
        for inquiry in my_inquiries:
            inquiry['_id'] = str(inquiry['_id'])
            # created_at과 replied_at이 datetime 객체인 경우 ISO 포맷 문자열로 변환
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
    """현재 로그인된 사용자의 특정 문의사항 상세 정보를 조회합니다."""
    user_id = g.user_id
    try:
        inquiry = mongo.db.inquiries.find_one({'_id': ObjectId(inquiry_id), 'user_id': user_id})
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

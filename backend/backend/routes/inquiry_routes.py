# backend/routes/inquiry_routes.py
from flask import Blueprint, request, jsonify, g, current_app
from backend.extensions import mongo
from backend.routes.auth_routes import token_required
from backend.mongo_models import Inquiry
import datetime

inquiry_bp = Blueprint('inquiry_api', __name__)

@inquiry_bp.route('/submit', methods=['POST'])
@token_required
def submit_inquiry():
    """사용자 문의사항을 제출합니다."""
    user_id = g.user_id
    username = g.username # auth_routes에서 g 객체에 추가된 사용자 이름
    email = g.email # auth_routes에서 g 객체에 추가된 사용자 이메일 (필요시)
    
    data = request.get_json()
    title = data.get('title')
    content = data.get('content')

    if not all([title, content]):
        return jsonify({'message': '제목과 내용을 모두 입력해주세요.'}), 400

    new_inquiry = Inquiry(
        user_id=user_id,
        username=username,
        email=email,
        title=title,
        content=content
    )

    try:
        mongo.db.inquiries.insert_one(new_inquiry.to_dict())
        return jsonify({'message': '문의사항이 성공적으로 제출되었습니다.'}), 201
    except Exception as e:
        current_app.logger.error(f"문의사항 제출 중 오류 발생: {e}", exc_info=True)
        return jsonify({'message': '문의사항 제출에 실패했습니다.'}), 500

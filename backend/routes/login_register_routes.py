# backend/routes/login_register_routes.py
from flask import Blueprint, request, jsonify, g
import jwt # Import jwt
import datetime # Import datetime
import os # Import os for JWT_SECRET_KEY
from werkzeug.security import generate_password_hash, check_password_hash
from maria_models import User # User 모델 임포트
from extensions import db
import random
import string # random과 string 모듈 임포트
from auth import token_required, generate_numeric_uid # auth.py에서 데코레이터와 유틸리티 함수 임포트

auth_bp = Blueprint('auth_api', __name__) # auth_bp Blueprint를 여기서 정의

# 회원가입
@auth_bp.route('/register', methods=['POST']) # /signup 대신 /register로 통일
def register():
    data = request.get_json()
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    nickname = data.get('nickname') # 닉네임 필드 추가

    if not username or not email or not password:
        return jsonify({'message': 'Username, email, and password are required'}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({'message': 'Email already registered'}), 409

    if User.query.filter_by(username=username).first():
        return jsonify({'message': 'Username already taken'}), 409

    # 사용자 UID 생성 (auth.py에서 임포트한 함수 사용)
    generated_uid = None
    max_retries = 5 # UID 생성 실패 시 최대 재시도 횟수
    for _ in range(max_retries):
        temp_uid = generate_numeric_uid(length=5) # 5자리 UID 생성
        if not User.query.filter_by(user_uid=temp_uid).first():
            generated_uid = temp_uid
            break

    if not generated_uid:
        return jsonify({'message': 'Failed to generate a unique user UID. Please try again.'}), 500

    new_user = User(
        username=username,
        email=email,
        user_uid=generated_uid, # 생성된 UID 할당
        nickname=nickname # 닉네임 추가
    )
    new_user.set_password(password) # 비밀번호 해싱
    db.session.add(new_user)
    db.session.commit()

    return jsonify({'message': 'User registered successfully!'}), 201

# 로그인
@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({'message': 'Email and password are required'}), 400

    user = User.query.filter_by(email=email).first()

    if not user or not user.check_password(password):
        return jsonify({'message': 'Invalid credentials'}), 401

    # 로그인 성공 시 JWT 토큰 생성 (여기서 직접 생성)
    token = jwt.encode({
        'user_uid': user.user_uid,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24) # 24시간 유효
    }, os.getenv('JWT_SECRET_KEY'), algorithm="HS256")

    return jsonify({
        'message': 'Login successful!',
        'token': token,
        'user_uid': user.user_uid,
        'user_id': user.id, # MariaDB의 user_id도 함께 반환
        'nickname': user.nickname, # 닉네임도 함께 반환
        'is_admin': user.is_admin # 관리자 여부도 함께 반환
    }), 200

# 사용자 정보 조회 (로그인 상태 확인)
@auth_bp.route('/me', methods=['GET'])
@token_required # JWT 토큰 필요 (auth.py에서 임포트)
def get_current_user_info(): # 함수 이름 유지
    """
    현재 로그인된 사용자의 정보를 반환합니다.
    """
    user_id = int(g.user_id) # token_required 데코레이터에서 설정된 사용자 ID
    user = User.query.get(user_id) # MariaDB에서 사용자 조회

    if not user:
        return jsonify({'message': 'User not found'}), 404

    # 사용자 정보를 딕셔너리로 반환 (비밀번호 해시는 제외)
    return jsonify({
        'id': user.id,
        'username': user.username,
        'email': user.email,
        'user_uid': user.user_uid,
        'nickname': user.nickname, # 닉네임 반환
        'is_admin': user.is_admin, # 관리자 여부 반환
        'created_at': user.created_at.isoformat(),
        'updated_at': user.updated_at.isoformat()
    }), 200

# 비밀번호 찾기 (재설정 요청)
@auth_bp.route('/forgot_password_request', methods=['POST'])
def forgot_password_request():
    data = request.get_json()
    email = data.get('email')

    if not email:
        return jsonify({'message': 'Email is required'}), 400

    user = User.query.filter_by(email=email).first()

    if not user:
        # 보안을 위해 이메일이 존재하지 않아도 존재하지 않는다는 메시지를 직접적으로 주지 않는 것이 좋음
        return jsonify({'message': 'If an account with that email exists, a password reset link will be sent.'}), 200

    # 실제 환경에서는 여기에서 비밀번호 재설정 토큰을 생성하고, 사용자 이메일로 링크를 전송하는 로직이 들어갑니다.
    return jsonify({'message': 'Password reset link sent to your email if the account exists.'}), 200

# 비밀번호 재설정 (새 비밀번호 설정) - 실제로는 토큰 검증 로직 필요
@auth_bp.route('/reset_password', methods=['POST'])
def reset_password():
    data = request.get_json()
    # reset_token = data.get('token') # 이메일을 통해 받은 재설정 토큰
    email = data.get('email') # 어떤 사용자의 비밀번호를 재설정하는지 식별
    new_password = data.get('new_password')

    if not email or not new_password:
        return jsonify({'message': 'Email and new password are required'}), 400

    user = User.query.filter_by(email=email).first()

    if not user:
        return jsonify({'message': 'User not found'}), 404

    # 실제 환경에서는 여기서 reset_token을 검증하는 로직이 필요합니다.
    user.set_password(new_password)
    db.session.commit()

    return jsonify({'message': 'Password has been reset successfully!'}), 200

# backend/auth.py
from flask import Blueprint, request, jsonify, g
from functools import wraps
import jwt
import datetime
import os
from extensions import db
from maria_models import User # User 모델 임포트
from werkzeug.security import generate_password_hash, check_password_hash
import random
import string

auth_bp = Blueprint('auth_api', __name__)

# JWT 토큰을 요구하는 데코레이터
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            token = request.headers['Authorization'].split(" ")[1] # "Bearer <token>"
        
        if not token:
            return jsonify({'message': 'Token is missing!'}), 401

        try:
            data = jwt.decode(token, os.getenv('JWT_SECRET_KEY'), algorithms=["HS256"])
            # 토큰에서 user_uid를 사용하여 사용자 조회
            current_user = User.query.filter_by(user_uid=data['user_uid']).first()
            if not current_user:
                return jsonify({'message': 'Token is invalid or user not found!'}), 401
            
            g.user_id = current_user.id # g 객체에 user_id 저장
            g.user_uid = current_user.user_uid # g 객체에 user_uid 저장 (필요시)
            g.is_admin = current_user.is_admin # g 객체에 is_admin 저장 (필요시)

        except jwt.ExpiredSignatureError:
            return jsonify({'message': 'Token has expired!'}), 401
        except (jwt.InvalidTokenError, KeyError): # KeyError를 함께 처리하여 'user_uid' 누락 문제 해결
            return jsonify({'message': 'Token is invalid or malformed! Please log in again.'}), 401
        except Exception as e:
            return jsonify({'message': f'An unexpected error occurred during token processing: {str(e)}'}), 500

        return f(*args, **kwargs) # 유효한 경우, 원래 함수를 실행합니다.
    return decorated

# 관리자 권한을 요구하는 데코레이터
def admin_required(f):
    @wraps(f)
    @token_required # 먼저 토큰 유효성 검사
    def decorated(*args, **kwargs):
        if not g.is_admin: # g.is_admin은 token_required에서 설정됨
            return jsonify({'message': '관리자 권한이 필요합니다.'}), 403
        return f(*args, **kwargs)
    return decorated

# 숫자 6자리 user_uid 생성 함수
def generate_numeric_uid():
    while True:
        # 6자리 숫자 문자열 생성
        uid = ''.join(random.choices(string.digits, k=6))
        # 데이터베이스에서 중복 확인
        if not User.query.filter_by(user_uid=uid).first():
            return uid

# 회원가입
@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    nickname = data.get('nickname') # 닉네임 필드 추가

    if not username or not email or not password:
        return jsonify({'message': 'Username, email, and password are required!'}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({'message': 'Username already exists!'}), 409
    
    if User.query.filter_by(email=email).first():
        return jsonify({'message': 'Email already exists!'}), 409

    hashed_password = generate_password_hash(password)
    user_uid = generate_numeric_uid() # 고유한 6자리 숫자 UID 생성

    new_user = User(
        username=username,
        email=email,
        password_hash=hashed_password,
        user_uid=user_uid,
        nickname=nickname # 닉네임 저장
    )
    db.session.add(new_user)
    db.session.commit()

    return jsonify({'message': 'User registered successfully!', 'user_uid': user_uid}), 201

# 로그인
@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify({'message': 'Email and password are required!'}), 400

    user = User.query.filter_by(email=email).first()

    if not user or not user.check_password(password):
        return jsonify({'message': 'Invalid credentials!'}), 401

    # JWT 토큰 생성
    token = jwt.encode({
        'user_uid': user.user_uid,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24) # 24시간 유효
    }, os.getenv('JWT_SECRET_KEY'), algorithm="HS256")

    return jsonify({
        'message': 'Logged in successfully!',
        'token': token,
        'user_uid': user.user_uid,
        'user_id': user.id, # MariaDB의 user_id도 함께 반환
        'nickname': user.nickname, # 닉네임도 함께 반환
        'is_admin': user.is_admin # 관리자 여부도 함께 반환
    }), 200

# 사용자 정보 조회 (토큰 필요)
@auth_bp.route('/me', methods=['GET'])
@token_required
def me():
    # token_required 데코레이터에서 g.user_id와 g.user_uid가 설정됨
    user_id = g.user_id
    user = db.session.get(User, user_id) # MariaDB에서 사용자 정보 조회

    if not user:
        return jsonify({'message': 'User not found in database'}), 404
    
    # User 모델의 to_dict() 메서드를 사용하여 사용자 정보 반환
    # 이 to_dict() 메서드가 username과 nickname을 모두 포함하는지 확인해야 합니다.
    return jsonify(user.to_dict()), 200

# 비밀번호 재설정 요청 (실제 구현은 이메일 전송 등 복잡)
@auth_bp.route('/forgot_password_request', methods=['POST'])
def forgot_password_request():
    data = request.get_json()
    email = data.get('email')

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'message': 'Email not found.'}), 404

    # 실제 앱에서는 여기에 비밀번호 재설정 토큰 생성 및 이메일 전송 로직이 들어갑니다.
    # 이메일 전송은 복잡하므로 여기서는 간단히 성공 메시지만 반환합니다.
    return jsonify({'message': 'Password reset link sent to your email (dummy).'}), 200

# 비밀번호 재설정 (실제 구현은 토큰 검증 후 비밀번호 변경)
@auth_bp.route('/reset_password', methods=['POST'])
def reset_password():
    data = request.get_json()
    email = data.get('email')
    new_password = data.get('new_password')
    # reset_token = data.get('reset_token') # 실제 구현 시 필요

    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'message': 'User not found.'}), 404

    # 실제 앱에서는 reset_token 검증 로직이 여기에 들어갑니다.
    # 여기서는 토큰 검증 없이 바로 비밀번호를 변경합니다 (개발용).
    user.set_password(new_password)
    db.session.commit()

    return jsonify({'message': 'Password has been reset successfully.'}), 200

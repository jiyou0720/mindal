# backend/auth.py
import jwt
import datetime
from functools import wraps
from flask import request, jsonify, current_app, g
from werkzeug.security import generate_password_hash, check_password_hash
from maria_models import User # User 모델 임포트

def generate_token(user_id):
    """
    주어진 user_id를 사용하여 JWT 토큰을 생성합니다.
    토큰에는 만료 시간(exp), 발행 시간(iat), 그리고 사용자 ID(sub)가 포함됩니다.
    """
    payload = {
        'exp': datetime.datetime.utcnow() + datetime.timedelta(days=1), # 토큰은 1일 후 만료됩니다.
        'iat': datetime.datetime.utcnow(), # 토큰 발행 시간
        'sub': str(user_id) # 사용자 ID (MariaDB의 Integer ID를 문자열로 변환)
    }
    # `current_app.config['JWT_SECRET_KEY']`를 사용하여 .env에서 설정한 비밀 키를 가져옵니다.
    return jwt.encode(payload, current_app.config['JWT_SECRET_KEY'], algorithm='HS256')

def token_required(f):
    """
    API 엔드포인트에 적용될 데코레이터입니다.
    요청 헤더에서 JWT 토큰을 검증하고, 유효한 경우 사용자 ID를 `g.user_id`에 저장합니다.
    토큰이 없거나 유효하지 않으면 401 Unauthorized 응답을 반환합니다.
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        # Authorization 헤더에서 'Bearer <token>' 형식으로 토큰을 추출합니다.
        if 'Authorization' in request.headers:
            token = request.headers['Authorization'].split(" ")[1] # 'Bearer' 다음의 문자열이 토큰입니다.

        if not token:
            return jsonify({'message': 'Token is missing!'}), 401

        try:
            # 토큰을 디코딩하여 페이로드 데이터를 가져옵니다.
            # `current_app.config['JWT_SECRET_KEY']`를 사용하여 비밀 키로 검증합니다.
            data = jwt.decode(token, current_app.config['JWT_SECRET_KEY'], algorithms=['HS256'])
            g.user_id = data['sub'] # g 객체에 사용자 ID 저장 (요청 수명 동안 접근 가능)
        except jwt.ExpiredSignatureError:
            # 토큰이 만료된 경우
            return jsonify({'message': 'Token has expired!'}), 401
        except jwt.InvalidTokenError:
            # 토큰이 유효하지 않은 경우 (변조되었거나 형식이 잘못된 경우)
            return jsonify({'message': 'Token is invalid!'}), 401

        return f(*args, **kwargs) # 유효한 경우, 원래 함수를 실행합니다.
    return decorated

def admin_required(f):
    """
    관리자 권한을 요구하는 API 엔드포인트에 적용될 데코레이터입니다.
    먼저 JWT 토큰을 검증하고, 해당 사용자가 관리자인지 확인합니다.
    """
    @wraps(f)
    @token_required # 먼저 토큰 유효성을 검사
    def decorated_admin(*args, **kwargs):
        user_id = g.user_id
        user = User.query.get(user_id)

        if not user or not user.is_admin:
            return jsonify({'message': 'Admin privilege required!'}), 403 # 403 Forbidden

        return f(*args, **kwargs)
    return decorated_admin
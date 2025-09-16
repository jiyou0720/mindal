from flask import Blueprint, request, jsonify, current_app, g
from backend.extensions import db, bcrypt
from backend.maria_models import User, Role, NicknameHistory
import jwt
from functools import wraps
import datetime
import random
import string

auth_bp = Blueprint('auth_api', __name__)

def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers and request.headers['Authorization'].startswith('Bearer '):
            token = request.headers['Authorization'].split(' ')[1]
        
        if not token:
            return jsonify({'message': '토큰이 필요합니다.'}), 401
        
        try:
            data = jwt.decode(token, current_app.config['JWT_SECRET_KEY'], algorithms=["HS256"])
            g.user_id = data['user_id']
            g.user_roles = data['roles']
        except jwt.ExpiredSignatureError:
            return jsonify({'message': '토큰이 만료되었습니다.'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'message': '유효하지 않은 토큰입니다.'}), 401
        
        return f(*args, **kwargs)
    return decorated

def roles_required(roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not hasattr(g, 'user_roles') or not any(role in g.user_roles for role in roles):
                return jsonify({'message': '이 작업을 수행할 권한이 없습니다.'}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# --- 회원가입 관련 API ---
@auth_bp.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    nickname = data.get('nickname')

    if not all([username, email, password, nickname]):
        return jsonify({'message': '모든 필드를 입력해주세요.'}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({'message': '이미 존재하는 사용자 이름입니다.'}), 409
    if User.query.filter_by(email=email).first():
        return jsonify({'message': '이미 존재하는 이메일입니다.'}), 409
    if User.query.filter_by(nickname=nickname).first():
        return jsonify({'message': '이미 존재하는 닉네임입니다.'}), 409

    try:
        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8')
        
        while True:
            user_uid = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
            if not User.query.filter_by(user_uid=user_uid).first():
                break

        new_user = User(
            username=username,
            email=email,
            password=hashed_password,
            nickname=nickname,
            user_uid=user_uid
        )

        default_role = Role.query.filter_by(name='일반 사용자').first()
        if default_role:
            new_user.roles.append(default_role)
        
        db.session.add(new_user)
        db.session.commit()
        
        return jsonify({'message': '회원가입이 성공적으로 완료되었습니다.'}), 201

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Signup error: {e}", exc_info=True)
        return jsonify({'message': '서버 오류로 회원가입에 실패했습니다.'}), 500

# --- 로그인/로그아웃 관련 API ---
@auth_bp.route('/login', methods=['POST'])
def login_user():
    data = request.get_json()
    identifier = data.get('identifier')
    password = data.get('password')

    if not identifier or not password:
        return jsonify({'message': '사용자 이름(또는 이메일)과 비밀번호를 입력해주세요.'}), 400

    user = User.query.filter((User.username == identifier) | (User.email == identifier)).first()

    if user and bcrypt.check_password_hash(user.password, password):
        user_roles = [role.name for role in user.roles]
        token_payload = {
            'user_id': user.id,
            'roles': user_roles,
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)
        }
        access_token = jwt.encode(token_payload, current_app.config['JWT_SECRET_KEY'], algorithm="HS256")
        
        return jsonify({
            'message': '로그인 성공',
            'access_token': access_token,
        }), 200
    else:
        return jsonify({'message': '사용자 이름(또는 이메일) 또는 비밀번호가 올바르지 않습니다.'}), 401

# --- 사용자 정보 관련 API ---
@auth_bp.route('/me', methods=['GET'])
@token_required
def get_current_user():
    user = User.query.get(g.user_id)
    if not user:
        return jsonify({"message": "사용자를 찾을 수 없습니다."}), 404
        
    return jsonify({
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "nickname": user.nickname,
            "user_uid": user.user_uid,
            "roles": [role.name for role in user.roles]
        }
    }), 200


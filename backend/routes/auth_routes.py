import os
from flask import Blueprint, request, jsonify, g, current_app
from backend.extensions import db
from backend.maria_models import User, Role, UserRole, NicknameHistory
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
import jwt
import datetime
import random
import string

auth_bp = Blueprint('auth_api', __name__)

# JWT 토큰 검증 데코레이터
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            token = request.headers['Authorization'].split(" ")[1]

        if not token:
            current_app.logger.warning("token_required: Token is missing!")
            return jsonify({'message': 'Token is missing!'}), 401

        try:
            secret_key = current_app.config.get('JWT_SECRET_KEY')
            if not secret_key:
                current_app.logger.error("token_required: JWT_SECRET_KEY is not configured!")
                return jsonify({'message': 'Server configuration error: JWT secret key missing.'}), 500

            data = jwt.decode(token, secret_key, algorithms=["HS256"])
            g.user_id = data['user_id']
            g.username = data['username']
            g.nickname = data.get('nickname')
            g.user_uid = data.get('user_uid')
            g.email = data.get('email') # JWT 토큰에서 이메일 가져와 g 객체에 할당
            
            # DB에서 최신 역할 정보 가져와 g.user_roles에 할당
            user = db.session.get(User, g.user_id)
            if user:
                g.user_roles = [role.name for role in user.roles]
            else:
                g.user_roles = []

        except jwt.ExpiredSignatureError:
            current_app.logger.warning("token_required: Token has expired!")
            return jsonify({'message': 'Token has expired!'}), 401
        except jwt.InvalidTokenError:
            current_app.logger.warning("token_required: Invalid token!")
            return jsonify({'message': 'Token is invalid!'}), 401
        except Exception as e:
            current_app.logger.error(f"token_required: An unexpected error occurred: {e}", exc_info=True)
            return jsonify({'message': 'An unexpected error occurred during token validation.'}), 500

        return f(*args, **kwargs)
    return decorated

# 역할 기반 접근 제어 데코레이터
def roles_required(roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not hasattr(g, 'user_roles') or not any(role in g.user_roles for role in roles):
                current_app.logger.warning(f"Access denied for user {g.username} (ID: {g.user_id}) with roles {g.user_roles}. Required roles: {roles}")
                return jsonify({'message': '접근 권한이 없습니다.'}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# 사용자 UID 생성 (숫자 10자리)
def generate_numeric_uid(length=10):
    return ''.join(random.choices(string.digits, k=length))

# 사용자 등록 (회원가입)
@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    nickname = data.get('nickname')
    email = data.get('email')
    password = data.get('password')
    gender = data.get('gender')
    age = data.get('age')
    major = data.get('major')

    current_app.logger.info(f"Register attempt for username: {username}, email: {email}")

    if not all([username, email, password]):
        current_app.logger.warning("Registration failed: Missing required fields.")
        return jsonify({'message': '사용자 이름, 이메일, 비밀번호는 필수입니다.'}), 400

    if User.query.filter_by(username=username).first():
        current_app.logger.warning(f"Registration failed: Username '{username}' already exists.")
        return jsonify({'message': '이미 존재하는 사용자 이름입니다.'}), 409
    
    if User.query.filter_by(email=email).first():
        current_app.logger.warning(f"Registration failed: Email '{email}' already registered.")
        return jsonify({'message': '이미 가입된 이메일 주소입니다.'}), 409

    if nickname and User.query.filter_by(nickname=nickname).first():
        current_app.logger.warning(f"Registration failed: Nickname '{nickname}' already exists.")
        return jsonify({'message': '이미 존재하는 별명입니다.'}), 409

    try:
        # 사용자 UID 생성
        user_uid = generate_numeric_uid()
        while User.query.filter_by(user_uid=user_uid).first(): # 중복 방지
            user_uid = generate_numeric_uid()

        new_user = User(
            username=username,
            email=email,
            user_uid=user_uid,
            nickname=nickname,
            gender=gender,
            age=age,
            major=major
        )
        new_user.set_password(password)

        # 기본 역할 '일반 사용자' 할당
        default_role = Role.query.filter_by(name='일반 사용자').first()
        if default_role:
            new_user.roles.append(default_role)
            current_app.logger.info("Default role '일반 사용자' assigned to new user.")
        else:
            current_app.logger.error("Default role '일반 사용자' not found in DB. Please run initialize_roles.py.")
            # 역할 할당 실패 시, 사용자 생성은 진행하되 로그를 남김 (또는 에러 반환)
            # 여기서는 사용자 생성은 진행하고 경고를 남깁니다.
            # 만약 역할 할당이 필수적이라면 여기서 500 에러를 반환해야 합니다.

        db.session.add(new_user)
        db.session.commit()
        current_app.logger.info(f"User '{username}' (ID: {new_user.id}) successfully registered and committed to DB.")
        return jsonify({'message': '회원가입이 성공적으로 완료되었습니다!'}), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error during registration for user '{username}': {e}", exc_info=True)
        return jsonify({'message': '회원가입 실패. 다시 시도해주세요.'}), 500

# 사용자 로그인
@auth_bp.route('/login', methods=['POST'])
def login_user():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    user = User.query.filter_by(email=email).first()

    if not user or not user.check_password(password):
        return jsonify({'message': '잘못된 이메일 또는 비밀번호입니다.'}), 401

    # 사용자 역할 정보 로드 (JWT에 포함하기 위해)
    user_roles_list = [user_role_obj.name for user_role_obj in user.roles]

    token = jwt.encode({
        'user_id': user.id,
        'username': user.username,
        'nickname': user.nickname,
        'user_uid': user.user_uid,
        'email': user.email, # 이메일도 토큰에 포함
        'roles': user_roles_list, # 역할 목록을 토큰에 포함
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24) # 토큰 만료 시간 24시간
    },
    current_app.config['JWT_SECRET_KEY'],
    algorithm='HS256'
    )
    
    response = jsonify({
        'message': '로그인 성공!',
        'access_token': token,
        'user_id': user.id,
        'username': user.username,
        'nickname': user.nickname,
        'user_uid': user.user_uid,
        'email': user.email, # 프론트엔드에서 바로 사용할 수 있도록 이메일도 반환
        'roles': user_roles_list
    })
    
    # 로그인 성공 시 프론트엔드에 메뉴 캐시 삭제 지시 (쿠키 또는 헤더를 통해)
    # response.headers['X-Clear-Menu-Cache'] = 'true' # 이 부분은 요청에 의해 제거됨
    
    return response, 200


@auth_bp.route('/me', methods=['GET'])
@token_required
def get_current_user():
    user_id = g.user_id
    user = db.session.get(User, user_id)

    if not user:
        return jsonify({'message': '사용자를 찾을 수 없습니다.'}), 404
    
    # User 모델의 to_dict 메서드를 사용하여 사용자 정보 반환
    # to_dict 메서드에 roles가 포함되어 있으므로 별도로 추가할 필요 없음
    return jsonify({'user': user.to_dict()}), 200

# 사용자 프로필 업데이트
@auth_bp.route('/profile', methods=['PUT'])
@token_required
def update_profile():
    user_id = g.user_id
    data = request.get_json()
    
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'message': '사용자를 찾을 수 없습니다.'}), 404

    # 닉네임 변경 시 이력 기록
    new_nickname = data.get('nickname')
    if new_nickname and new_nickname != user.nickname:
        # 새로운 닉네임이 이미 존재하는지 확인
        existing_user_with_new_nickname = User.query.filter_by(nickname=new_nickname).first()
        if existing_user_with_new_nickname and existing_user_with_new_nickname.id != user_id:
            return jsonify({'message': '이미 사용 중인 닉네임입니다.'}), 409

        nickname_history_entry = NicknameHistory(
            user_id=user.id,
            old_nickname=user.nickname,
            new_nickname=new_nickname
        )
        db.session.add(nickname_history_entry)
        user.nickname = new_nickname

    # 다른 필드 업데이트
    user.gender = data.get('gender', user.gender)
    user.age = data.get('age', user.age)
    user.major = data.get('major', user.major)
    user.updated_at = datetime.datetime.utcnow() # 업데이트 시간 갱신

    try:
        db.session.commit()
        # 업데이트된 사용자 정보를 to_dict()로 반환
        return jsonify({'message': '프로필이 성공적으로 업데이트되었습니다.', 'user': user.to_dict()}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating profile for user {user_id}: {e}", exc_info=True)
        return jsonify({'message': '프로필 업데이트 실패.'}), 500

# 닉네임 변경 이력 조회
@auth_bp.route('/nickname_history', methods=['GET'])
@token_required
def get_nickname_history():
    user_id = g.user_id
    try:
        history = NicknameHistory.query.filter_by(user_id=user_id).order_by(NicknameHistory.changed_at.desc()).all()
        history_data = [{
            'old_nickname': entry.old_nickname,
            'new_nickname': entry.new_nickname,
            'changed_at': entry.changed_at.isoformat()
        } for entry in history]
        return jsonify({'history': history_data}), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching nickname history for user {user_id}: {e}", exc_info=True)
        return jsonify({'message': '닉네임 변경 이력을 불러오는 데 실패했습니다.'}), 500

# 비밀번호 재설정 요청
@auth_bp.route('/forgot_password_request', methods=['POST'])
def forgot_password_request():
    data = request.get_json()
    email = data.get('email')
    user = User.query.filter_by(email=email).first()
    if not user:
        return jsonify({'message': '비밀번호 재설정 링크가 이메일로 전송되었습니다.'}), 200
    current_app.logger.info(f"Password reset requested for email: {email}")
    return jsonify({'message': '비밀번호 재설정 링크가 이메일로 전송되었습니다.'}), 200

# 비밀번호 재설정
@auth_bp.route('/reset_password', methods=['POST'])
def reset_password():
    data = request.get_json()
    token = data.get('token')
    new_password = data.get('new_password')

    if not token or not new_password:
        return jsonify({'message': '토큰과 새 비밀번호를 모두 제공해야 합니다.'}), 400

    try:
        return jsonify({'message': '비밀번호 재설정 기능은 아직 준비 중입니다. (토큰 검증 필요)'}), 501
    except Exception as e:
        current_app.logger.error(f"Error during password reset: {e}", exc_info=True)
        return jsonify({'message': '비밀번호 재설정 중 오류가 발생했습니다.'}), 500

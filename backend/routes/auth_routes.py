from flask import Blueprint, request, jsonify, current_app
from backend.extensions import db, bcrypt
from backend.maria_models import User, Role, NicknameHistory
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity
import datetime
from functools import wraps
import random
import string

auth_bp = Blueprint('auth_api', __name__)

def token_required(fn):
    @wraps(fn)
    def decorated(*args, **kwargs):
        # This is a simplified wrapper. For production, consider Flask-JWT-Extended's robust handling.
        try:
            return jwt_required()(fn)(*args, **kwargs)
        except Exception as e:
            # Log the exception for debugging
            current_app.logger.warning(f"JWT verification failed: {e}")
            return jsonify({'message': '토큰이 없거나 유효하지 않습니다.'}), 401
    return decorated

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
    identifier = data.get('identifier') # username or email
    password = data.get('password')

    if not identifier or not password:
        return jsonify({'message': '사용자 이름(또는 이메일)과 비밀번호를 입력해주세요.'}), 400

    user = User.query.filter((User.username == identifier) | (User.email == identifier)).first()

    if user and bcrypt.check_password_hash(user.password, password):
        user_claims = {
            "user_id": user.id,
            "username": user.username,
            "roles": [role.name for role in user.roles]
        }
        access_token = create_access_token(identity=user.id, additional_claims=user_claims)
        refresh_token = create_refresh_token(identity=user.id)
        return jsonify({
            'message': '로그인 성공',
            'access_token': access_token,
            'refresh_token': refresh_token
        }), 200
    else:
        return jsonify({'message': '사용자 이름(또는 이메일) 또는 비밀번호가 올바르지 않습니다.'}), 401

@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    if not user:
        return jsonify({"message": "사용자를 찾을 수 없습니다."}), 404
    
    user_claims = {
        "user_id": user.id,
        "username": user.username,
        "roles": [role.name for role in user.roles]
    }
    new_access_token = create_access_token(identity=user.id, additional_claims=user_claims)
    return jsonify({'access_token': new_access_token}), 200

# --- 사용자 정보 관련 API ---

@auth_bp.route('/me', methods=['GET'])
@token_required
def get_current_user():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
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

@auth_bp.route('/profile', methods=['PUT'])
@token_required
def update_profile():
    current_user_id = get_jwt_identity()
    user = User.query.get(current_user_id)
    if not user:
        return jsonify({"message": "사용자를 찾을 수 없습니다."}), 404

    data = request.get_json()
    new_nickname = data.get('nickname')

    if new_nickname and new_nickname != user.nickname:
        if User.query.filter(User.nickname == new_nickname, User.id != user.id).first():
            return jsonify({'message': '이미 사용 중인 닉네임입니다.'}), 409
        
        try:
            old_nickname = user.nickname
            user.nickname = new_nickname
            
            history_entry = NicknameHistory(
                user_id=user.id,
                old_nickname=old_nickname,
                new_nickname=new_nickname,
                changed_at=datetime.datetime.utcnow()
            )
            db.session.add(history_entry)
            db.session.commit()
            
            return jsonify({'message': '닉네임이 성공적으로 변경되었습니다.'}), 200
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Nickname update error for user {user.id}: {e}", exc_info=True)
            return jsonify({'message': '닉네임 변경 중 오류가 발생했습니다.'}), 500

    return jsonify({'message': '변경할 닉네임 정보가 없습니다.'}), 400


# backend/routes/login_register_routes.py
from flask import Blueprint, request, jsonify, current_app, g
from werkzeug.security import generate_password_hash, check_password_hash
from backend.maria_models import User, Role, UserRole
from backend.extensions import db
from backend.routes.auth_routes import token_required
import jwt
import datetime
import uuid

user_bp = Blueprint('user_api', __name__)

# 사용자 등록 (회원가입)
@user_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    nickname = data.get('nickname')
    email = data.get('email')
    password = data.get('password')
    gender = data.get('gender')
    age = data.get('age')
    major = data.get('major')

    if not username or not email or not password or not gender or not age or not major:
        return jsonify({'message': '모든 필수 정보를 입력해주세요.'}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({'message': '이미 존재하는 사용자 이름입니다.'}), 409
    
    if User.query.filter_by(email=email).first():
        return jsonify({'message': '이미 가입된 이메일 주소입니다.'}), 409

    if nickname and User.query.filter_by(nickname=nickname).first():
        return jsonify({'message': '이미 존재하는 별명입니다.'}), 409

    # user_uid 생성 (짧은 고유 ID)
    user_uid = str(uuid.uuid4().hex)[:10] # 10자리 문자열로 제한

    new_user = User(
        username=username,
        nickname=nickname,
        email=email,
        user_uid=user_uid,
        gender=gender,
        age=age,
        major=major
    )
    new_user.set_password(password)

    # 기본 역할 할당
    default_role = Role.query.filter_by(name='일반 사용자').first()
    if not default_role:
        default_role = Role(name='일반 사용자', description='기본 사용자 역할')
        db.session.add(default_role)
        db.session.commit()

    user_role_association = UserRole(user=new_user, role=default_role)
    db.session.add(new_user)
    db.session.add(user_role_association)
    db.session.commit()

    return jsonify({'message': '회원가입이 성공적으로 완료되었습니다!'}), 201

# 사용자 로그인
@user_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    user = User.query.filter_by(email=email).first()

    if not user or not user.check_password(password):
        return jsonify({'message': '잘못된 이메일 또는 비밀번호입니다.'}), 401

    token = jwt.encode({
        'user_id': user.id,
        'username': user.username,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24) # 토큰 만료 시간 24시간
    },
    current_app.config['JWT_SECRET_KEY'],
    algorithm='HS256'
    )
    

    user_roles_list = [user_role_obj.role.name for user_role_obj in user.user_roles_association]

    return jsonify({
        'message': '로그인 성공!',
        'token': token,
        'user_id': user.id,
        'username': user.username,
        'nickname': user.nickname,
        'roles': user_roles_list
    }), 200


@user_bp.route('/me', methods=['GET'])
@token_required
def get_current_user():
    user_id = g.user_id
    user = db.session.get(User, user_id)

    if not user:
        return jsonify({'message': '사용자를 찾을 수 없습니다.'}), 404
    
    user_roles_list = [user_role_obj.role.name for user_role_obj in user.user_roles_association]

    return jsonify({
        'user_id': user.id,
        'username': user.username,
        'nickname': user.nickname,
        'email': user.email,
        'user_uid': user.user_uid,
        'gender': user.gender,
        'age': user.age,
        'major': user.major,
        'roles': user_roles_list
    }), 200
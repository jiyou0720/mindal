# backend/routes/login_register_routes.py
from flask import Blueprint, request, jsonify, current_app, g
from werkzeug.security import generate_password_hash, check_password_hash
from maria_models import User, Role, UserRole # UserRole 모델 임포트
from extensions import db
from auth import token_required # 토큰 유효성 검사를 위한 데코레이터 임포트
import jwt
import datetime
import uuid # user_uid 생성을 위해 uuid 모듈 임포트

# Blueprint 생성
auth_bp = Blueprint('auth_api', __name__)

# 사용자 등록 (회원가입)
@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    nickname = data.get('nickname') # 닉네임 필드 추가
    email = data.get('email')
    password = data.get('password')
    gender = data.get('gender') # 성별 필드 추가
    age = data.get('age')       # 나이 필드 추가
    major = data.get('major')   # 학과 필드 추가

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
        nickname=nickname, # 닉네임 저장
        email=email,
        user_uid=user_uid,
        gender=gender, # 성별 저장
        age=age,       # 나이 저장
        major=major    # 학과 저장
    )
    new_user.set_password(password)

    # 기본 역할 할당 (예: '일반 사용자')
    default_role = Role.query.filter_by(name='일반 사용자').first()
    if not default_role:
        # '일반 사용자' 역할이 없으면 생성
        default_role = Role(name='일반 사용자', description='기본 사용자 역할')
        db.session.add(default_role)
        db.session.commit() # 역할 먼저 커밋하여 ID 확보

    user_role_association = UserRole(user=new_user, role=default_role)
    db.session.add(new_user)
    db.session.add(user_role_association)
    db.session.commit()

    return jsonify({'message': '회원가입이 성공적으로 완료되었습니다!'}), 201

# 사용자 로그인
@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    user = User.query.filter_by(email=email).first()

    if not user or not user.check_password(password):
        return jsonify({'message': '잘못된 이메일 또는 비밀번호입니다.'}), 401

    # JWT 토큰 생성
    token = jwt.encode({
        'user_id': user.id,
        'username': user.username,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=24) # 토큰 만료 시간 24시간
    },
    current_app.config['JWT_SECRET_KEY'],
    algorithm='HS256'
    )
    
    # 사용자의 역할 이름을 리스트로 가져옴
    # user.user_roles_association는 UserRole 객체들의 리스트이므로, 각 UserRole 객체의 .role.name에 접근해야 합니다.
    user_roles_list = [user_role_obj.role.name for user_role_obj in user.user_roles_association]

    return jsonify({
        'message': '로그인 성공!',
        'token': token,
        'user_id': user.id,
        'username': user.username,
        'nickname': user.nickname, # 닉네임도 함께 반환
        'roles': user_roles_list # 역할 목록 반환
    }), 200

# 토큰 유효성 검사 및 사용자 정보 반환
@auth_bp.route('/me', methods=['GET'])
@token_required
def get_current_user():
    # token_required 데코레이터에 의해 g.user_id와 g.username이 설정됨
    user_id = g.user_id
    user = db.session.get(User, user_id)

    if not user:
        return jsonify({'message': '사용자를 찾을 수 없습니다.'}), 404
    
    # 사용자 역할도 함께 반환
    # user.user_roles_association는 UserRole 객체들의 리스트이므로, 각 UserRole 객체의 .role.name에 접근해야 합니다.
    user_roles_list = [user_role_obj.role.name for user_role_obj in user.user_roles_association]

    return jsonify({
        'user_id': user.id,
        'username': user.username,
        'nickname': user.nickname, # 닉네임도 반환
        'email': user.email,
        'user_uid': user.user_uid,
        'gender': user.gender,
        'age': user.age,
        'major': user.major,
        'roles': user_roles_list # 역할 목록 반환
    }), 200

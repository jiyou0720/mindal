# backend/initialize_roles_and_admin.py

import os
from flask import Flask
from extensions import db
from maria_models import Role, User
from werkzeug.security import generate_password_hash
from dotenv import load_dotenv

# .env 파일 로드 (환경 변수 사용을 위해)
load_dotenv()

# Flask 앱 초기화 (스크립트 실행을 위한 최소한의 앱 설정)
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("MARIADB_URI")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY") # JWT_SECRET_KEY도 필요할 수 있음

db.init_app(app)

with app.app_context():
    print("데이터베이스 역할 및 관리자 계정 초기화 시작...")

    # 역할 추가
    roles_to_add = ['관리자', '일반 사용자', '운영자', '에디터', '모더레이터', '게스트', '개발자', '연구자']
    for role_name in roles_to_add:
        if not Role.query.filter_by(name=role_name).first():
            new_role = Role(name=role_name)
            db.session.add(new_role)
            print(f"'{role_name}' 역할 추가됨.")
        else:
            print(f"'{role_name}' 역할은(는) 이미 존재합니다.")
    db.session.commit()
    print("모든 역할 초기화 완료.")

    # 관리자 계정 생성 또는 업데이트
    admin_username = 'adminuser' # 원하는 관리자 사용자 이름
    admin_email = 'admin@mindlink.com' # 원하는 관리자 이메일
    admin_password = 'adminpass' # 안전한 비밀번호로 변경하세요

    admin_user = User.query.filter_by(email=admin_email).first()
    if not admin_user:
        print(f"관리자 사용자 '{admin_username}' 생성 중...")
        admin_user = User(
            username=admin_username,
            email=admin_email,
            password_hash=generate_password_hash(admin_password),
            user_uid='000001', # 고정 UID 예시 (충돌 시 변경 필요)
            nickname='관리자',
            gender='미정',
            age=0,
            major='관리'
        )
        db.session.add(admin_user)
        db.session.commit() # 사용자 먼저 커밋하여 ID를 할당받음
        print(f"관리자 사용자 '{admin_username}' 생성 완료.")
    else:
        print(f"관리자 사용자 '{admin_username}'({admin_email})은(는) 이미 존재합니다.")

    admin_role = Role.query.filter_by(name='관리자').first()
    if admin_role:
        if admin_role not in admin_user.roles.all():
            admin_user.roles.append(admin_role)
            db.session.commit()
            print(f"관리자 사용자 '{admin_username}'에 '관리자' 역할 부여.")
        else:
            print(f"관리자 사용자 '{admin_username}'은(는) 이미 '관리자' 역할을 가지고 있습니다.")
    else:
        print("경고: '관리자' 역할을 찾을 수 없습니다. 역할 초기화 스크립트를 확인하세요.")

    print("데이터베이스 역할 및 관리자 계정 초기화 완료.")
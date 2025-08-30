# backend/create_admin_user.py
import os
from dotenv import load_dotenv
from flask import Flask
from backend.extensions import db
from backend.maria_models import User, Role
from backend.routes.auth_routes import generate_numeric_uid

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('MARIADB_URI')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.getenv('JWT_SECRET_KEY')

db.init_app(app)

with app.app_context():
    admin_email = os.getenv('ADMIN_EMAIL')
    admin_password = os.getenv('ADMIN_PASSWORD')
    admin_username = "admin"
    admin_nickname = "관리자"

    if not admin_email or not admin_password:
        print("ERROR: .env 파일에 ADMIN_EMAIL 또는 ADMIN_PASSWORD가 설정되지 않았습니다.")
        print("관리자 계정을 생성할 수 없습니다.")
    else:
        user_by_username = User.query.filter_by(username=admin_username).first()
        user_by_nickname = User.query.filter_by(nickname=admin_nickname).first()

        if user_by_username:
            print(f"관리자 계정 '{admin_username}'이(가) 이미 존재합니다. (username)")
            print(f"이메일: {user_by_username.email}, 닉네임: {user_by_username.nickname}, UID: {user_by_username.user_uid}")
        elif user_by_nickname:
            print(f"관리자 계정 '{admin_nickname}'이(가) 이미 존재합니다. (nickname)")
            print(f"이메일: {user_by_nickname.email}, 사용자 이름: {user_by_nickname.username}, UID: {user_by_nickname.user_uid}")
        else:
            # 사용자 UID 생성
            user_uid = generate_numeric_uid()
            while User.query.filter_by(user_uid=user_uid).first():
                user_uid = generate_numeric_uid()

            admin_user = User(
                username=admin_username,
                email=admin_email,
                user_uid=user_uid,
                nickname=admin_nickname,
                gender="기타", # 기본값
                age=99,      # 기본값
                major="관리"   # 기본값
            )
            admin_user.set_password(admin_password)

            admin_role = Role.query.filter_by(name='관리자').first()
            if admin_role:
                admin_user.roles.append(admin_role)
                db.session.add(admin_user)
                db.session.commit()
                print(f"관리자 계정 '{admin_username}'이(가) 성공적으로 생성되었습니다.")
                print(f"이메일: {admin_email}, 비밀번호: {admin_password}")
                print(f"닉네임: {admin_nickname}, UID: {user_uid}")
            else:
                print("ERROR: '관리자' 역할을 찾을 수 없습니다. initialize_roles.py를 먼저 실행해주세요.")


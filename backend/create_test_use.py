# backend/create_test_user.py
import os
import sys
from dotenv import load_dotenv
from flask import Flask
# sys.path에 프로젝트 루트를 추가하여 모듈 임포트 문제를 해결합니다.
# 이 스크립트가 backend/create_test_user.py에 있다고 가정하고,
# 프로젝트 루트는 backend의 부모 디렉토리입니다.
script_dir = os.path.dirname(__file__)
project_root = os.path.abspath(os.path.join(script_dir, '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root) # 경로의 가장 앞에 추가하여 우선순위를 높입니다.

from backend.extensions import db
from backend.maria_models import User, Role
from backend.routes.auth_routes import generate_numeric_uid
from werkzeug.security import generate_password_hash # 비밀번호 해싱을 위해 임포트


# .env 파일 로드
load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

# Flask 앱 인스턴스 생성 (DB 연결을 위해 필요)
app = Flask(__name__)

# MariaDB 설정
MARIA_USER = os.environ.get("MARIA_USER")
MARIA_PASSWORD = os.environ.get("MARIA_PASSWORD")
MARIA_HOST = os.environ.get("MARIA_HOST")
MARIA_PORT = os.environ.get("MARIA_PORT")
MARIA_DB = os.environ.get("MARIA_DB")

app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql+pymysql://{MARIA_USER}:{MARIA_PASSWORD}@{MARIA_HOST}:{MARIA_PORT}/{MARIA_DB}?charset=utf8mb4'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'default_jwt_secret_key') # JWT_SECRET_KEY도 설정

db.init_app(app)

def create_test_user():
    with app.app_context():
        print("--- 테스트 사용자 생성 시작 ---")

        test_username = "박지유"
        test_email = "jiyou060720@gmail.com"
        test_password = "saman"
        test_nickname = "무명이"

        # 1. 사용자 이름 또는 이메일로 기존 사용자 확인
        existing_user_by_username = User.query.filter_by(username=test_username).first()
        existing_user_by_email = User.query.filter_by(email=test_email).first()

        if existing_user_by_username:
            print(f"오류: 사용자 이름 '{test_username}'이(가) 이미 존재합니다. (ID: {existing_user_by_username.id})")
            return
        if existing_user_by_email:
            print(f"오류: 이메일 '{test_email}'이(가) 이미 존재합니다. (ID: {existing_user_by_email.id})")
            return

        # 2. 사용자 UID 생성
        user_uid = generate_numeric_uid()
        while User.query.filter_by(user_uid=user_uid).first(): # 중복 방지
            user_uid = generate_numeric_uid()

        # 3. 새로운 User 객체 생성
        new_user = User(
            username=test_username,
            email=test_email,
            password_hash=generate_password_hash(test_password), # 비밀번호 해싱
            user_uid=user_uid,
            nickname=test_nickname,
            gender="여성",
            age=20,
            major="컴퓨터공학"
        )

        # 4. '일반 사용자' 역할 찾기 및 할당
        default_role = Role.query.filter_by(name='일반 사용자').first()
        if default_role:
            new_user.roles.append(default_role)
            print(f"역할 '{default_role.name}'이(가) 사용자에게 할당됨.")
        else:
            print("경고: '일반 사용자' 역할이 데이터베이스에 없습니다. 역할을 할당할 수 없습니다.")
            print("`python initialize_roles.py`를 먼저 실행하여 역할을 초기화해주세요.")
            # 역할이 없어도 사용자는 생성될 수 있지만, 역할 할당은 실패합니다.

        # 5. 사용자 저장 및 커밋
        try:
            db.session.add(new_user)
            db.session.commit()
            print(f"사용자 '{test_username}' (ID: {new_user.id}, UID: {new_user.user_uid}) 생성 완료 및 DB에 저장됨.")
            print(f"이메일: {test_email}, 비밀번호: {test_password}")
        except Exception as e:
            db.session.rollback()
            print(f"오류: 사용자 생성 중 데이터베이스 오류 발생: {e}")
            print("트랜잭션이 롤백되었습니다.")

        print("--- 테스트 사용자 생성 종료 ---")

if __name__ == '__main__':
    create_test_user()

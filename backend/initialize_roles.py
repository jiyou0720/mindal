# backend/initialize_roles.py
import os
from flask import Flask
from extensions import db
from maria_models import Role # Role 모델 임포트
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# Flask 앱 초기화 (스크립트 실행을 위한 최소한의 앱 설정)
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("MARIADB_URI")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

# --- 기본 역할 초기화 로직 ---
with app.app_context():
    print("MariaDB 기본 역할 초기화 시작...")

    default_roles = [
        '모든 사용자',
        '일반 사용자',
        '관리자',
        '운영자',
        '에디터',
        '개발자',
        '연구자'
    ]

    for role_name in default_roles:
        existing_role = Role.query.filter_by(name=role_name).first()
        if not existing_role:
            new_role = Role(name=role_name)
            db.session.add(new_role)
            print(f"역할 '{role_name}' 추가됨.")
        else:
            print(f"역할 '{role_name}'은(는) 이미 존재합니다. 건너뜀.")
    
    db.session.commit()
    print("MariaDB 기본 역할 초기화 완료.")

if __name__ == '__main__':
    # 이 스크립트를 직접 실행할 경우 이 부분이 실행됩니다.
    pass

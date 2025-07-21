# 이 코드는 backend/initialize_roles_and_admin.py 파일에 포함되거나
# Flask 애플리케이션 컨텍스트 내에서 실행되어야 합니다.

import os
from flask import Flask
from extensions import db
from maria_models import Role, User # User와 Role 모델 임포트
from werkzeug.security import generate_password_hash
from dotenv import load_dotenv

# .env 파일 로드 (스크립트 실행을 위해 필요)
load_dotenv()

# Flask 앱 초기화 (스크립트 실행을 위한 최소한의 앱 설정)
# 이 부분은 스크립트 파일 전체에 한 번만 필요합니다.
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("MARIADB_URI")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY")

db.init_app(app)

# --- 관리자 계정 생성 및 역할 부여 로직 ---
with app.app_context():
    print("관리자 계정 생성 및 역할 부여 시작...")

    # 관리자 계정 정보 설정 (원하는 값으로 변경하세요)
    admin_username = 'adminuser'
    admin_email = 'admin@mindlink.com'
    admin_password = 'adminpass' # 실제 사용 시에는 더 강력한 비밀번호를 사용하세요!

    # 1. 관리자 역할 찾기
    admin_role = Role.query.filter_by(name='관리자').first()
    if not admin_role:
        print("오류: '관리자' 역할을 찾을 수 없습니다. 역할 초기화 스크립트를 먼저 실행했는지 확인하세요.")
        # 역할이 없으면 관리자 계정 생성 로직을 중단합니다.
        exit()

    # 2. 관리자 사용자 계정 찾기 또는 생성
    admin_user = User.query.filter_by(email=admin_email).first()
    if not admin_user:
        print(f"관리자 사용자 '{admin_username}' 생성 중...")
        # user_uid는 고유해야 하므로, 간단한 예시로 고정 값을 사용합니다.
        # 실제 앱에서는 generate_numeric_uid() 함수 등을 사용하여 고유하게 생성해야 합니다.
        admin_user = User(
            username=admin_username,
            email=admin_email,
            password_hash=generate_password_hash(admin_password),
            user_uid='000001', # 이 UID가 이미 존재한다면 충돌이 발생할 수 있습니다.
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
        # 이미 존재하는 경우 비밀번호 업데이트 (선택 사항)
        # admin_user.set_password(admin_password)
        # db.session.commit()
        # print(f"관리자 사용자 '{admin_username}'의 비밀번호가 업데이트되었습니다.")


    # 3. 관리자 사용자에게 '관리자' 역할 부여
    if admin_role not in admin_user.roles.all(): # 이미 역할이 부여되었는지 확인
        admin_user.roles.append(admin_role)
        db.session.commit()
        print(f"관리자 사용자 '{admin_username}'에 '관리자' 역할 부여 완료.")
    else:
        print(f"관리자 사용자 '{admin_username}'은(는) 이미 '관리자' 역할을 가지고 있습니다.")

    print("관리자 계정 생성 및 역할 부여 완료.")

# 이 스크립트를 직접 실행할 경우 (예: python your_script_name.py)
if __name__ == '__main__':
    # Flask 앱 컨텍스트는 위에서 with 블록으로 이미 설정되었습니다.
    # 이 스크립트 자체는 웹 서버를 시작하지 않습니다.
    pass

import sys
import os
from werkzeug.security import generate_password_hash

# 프로젝트 루트 디렉토리를 Python 경로에 추가합니다.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from backend.extensions import db
from backend.maria_models import Role, User

def initialize_database():
    """데이터베이스의 역할과 관리자 계정을 확인하고, 없으면 생성합니다."""
    print("데이터베이스 초기화/검증을 시작합니다...")

    # 1. 기본 역할 생성/확인
    roles_to_create = ['일반 사용자', '운영자', '에디터', '모더레이터', '개발자', '연구자', '관리자']
    for role_name in roles_to_create:
        if not Role.query.filter_by(name=role_name).first():
            new_role = Role(name=role_name)
            db.session.add(new_role)
            print(f"'{role_name}' 역할 생성 완료.")
    db.session.commit()
    print("모든 역할이 준비되었습니다.")

    # 2. 관리자 계정 생성/확인
    admin_email = os.environ.get('ADMIN_EMAIL', 'admin@example.com')
    admin_password = os.environ.get('ADMIN_PASSWORD', 'admin123')
    admin_role = Role.query.filter_by(name='관리자').first()

    admin_user = User.query.filter_by(email=admin_email).first()
    if not admin_user:
        hashed_password = generate_password_hash(admin_password)
        admin_user = User(
            username='admin',
            email=admin_email,
            password_hash=hashed_password,
            nickname='관리자',
            user_uid='0000000001',
            gender='기타',
            age=0,
            major='관리'
        )
        # User 모델에 back_populates를 사용하므로, roles 리스트에 추가합니다.
        admin_user.roles.append(admin_role)
        db.session.add(admin_user)
        print(f"새로운 관리자 계정 생성 및 역할 할당 완료 (Email: {admin_email})")
    else:
        # 이미 관리자 계정이 있다면 역할이 할당되어 있는지 확인
        if admin_role not in admin_user.roles:
            admin_user.roles.append(admin_role)
            print(f"기존 관리자 계정에 '관리자' 역할 할당 완료.")
        else:
            print("기존 관리자 계정 존재 및 역할 할당 확인 완료.")

    db.session.commit()
    print("데이터베이스 초기화/검증이 성공적으로 완료되었습니다.")

if __name__ == "__main__":
    # 이 스크립트를 독립적으로 실행할 때만 app을 생성합니다.
    from backend.app import create_app
    app = create_app()
    with app.app_context():
        initialize_database()
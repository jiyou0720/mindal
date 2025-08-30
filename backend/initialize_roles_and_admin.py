<<<<<<< HEAD
import sys
import os

# 프로젝트 루트 디렉토리를 Python 경로에 추가합니다.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from backend.app import create_app
from backend.extensions import db
# FIX: 'user_roles' 대신 'UserRole' 클래스를 임포트합니다.
from backend.maria_models import Role, User, UserRole
from werkzeug.security import generate_password_hash
from sqlalchemy import select, and_

def initialize_database():
    """데이터베이스의 역할과 관리자 계정을 확인하고, 없으면 생성하거나 수정합니다."""
    app = create_app()
    with app.app_context():
        print("데이터베이스 초기화/검증을 시작합니다...")

        # 1. 기본 역할 생성/확인
        roles_to_create = [
            '일반 사용자', '운영자', '에디터', '모더레이터', 
            '개발자', '연구자', '관리자'
        ]
        for role_name in roles_to_create:
            if not Role.query.filter_by(name=role_name).first():
                new_role = Role(name=role_name)
                db.session.add(new_role)
                print(f"'{role_name}' 역할 생성 완료.")
        db.session.commit()
        print("모든 역할이 준비되었습니다.")

        # 2. 관리자 계정 및 역할 할당 확인/수정
        admin_email = os.environ.get('ADMIN_EMAIL', 'admin@example.com')
        admin_password = os.environ.get('ADMIN_PASSWORD', 'admin123')
        admin_role = Role.query.filter_by(name='관리자').first()

        if not admin_role:
            print("치명적 오류: '관리자' 역할을 찾을 수 없습니다. 스크립트를 다시 확인하세요.")
            return

        admin_user = User.query.filter_by(email=admin_email).first()

        if not admin_user:
            hashed_password = generate_password_hash(admin_password)
            admin_user = User(
                username='admin', email=admin_email, password_hash=hashed_password,
                nickname='관리자', user_uid='0000000001', gender='기타', age=0, major='관리'
            )
            admin_user.roles.append(admin_role)
            db.session.add(admin_user)
            print(f"새로운 관리자 계정 생성 및 역할 할당 완료 (Email: {admin_email})")
        else:
            print("기존 관리자 계정을 확인합니다...")
            # FIX: UserRole 클래스에서 실제 테이블 객체(__table__)를 참조합니다.
            user_roles_table = UserRole.__table__
            stmt = select(user_roles_table).where(
                and_(user_roles_table.c.user_id == admin_user.id, user_roles_table.c.role_id == admin_role.id)
            )
            result = db.session.execute(stmt).first()

            if not result:
                print(f" -> '관리자' 역할이 할당되어 있지 않습니다. 역할을 추가합니다...")
                # FIX: UserRole.__table__을 사용하여 테이블에 직접 데이터를 삽입합니다.
                insert_stmt = user_roles_table.insert().values(user_id=admin_user.id, role_id=admin_role.id)
                db.session.execute(insert_stmt)
            else:
                print("관리자 계정에 이미 '관리자' 역할이 할당되어 있습니다.")
        
        try:
            db.session.commit()
            print(" -> 데이터베이스 커밋 성공.")
        except Exception as e:
            print(f" -> 데이터베이스 커밋 실패: {e}")
            db.session.rollback()

        print("데이터베이스 초기화/검증이 성공적으로 완료되었습니다.")

if __name__ == '__main__':
    initialize_database()
=======
import sys
import os

# 프로젝트 루트 디렉토리를 Python 경로에 추가합니다.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from backend.app import create_app
from backend.extensions import db
# FIX: 'user_roles' 대신 'UserRole' 클래스를 임포트합니다.
from backend.maria_models import Role, User, UserRole
from werkzeug.security import generate_password_hash
from sqlalchemy import select, and_

def initialize_database():
    """데이터베이스의 역할과 관리자 계정을 확인하고, 없으면 생성하거나 수정합니다."""
    app = create_app()
    with app.app_context():
        print("데이터베이스 초기화/검증을 시작합니다...")

        # 1. 기본 역할 생성/확인
        roles_to_create = [
            '일반 사용자', '운영자', '에디터', '모더레이터', 
            '개발자', '연구자', '관리자'
        ]
        for role_name in roles_to_create:
            if not Role.query.filter_by(name=role_name).first():
                new_role = Role(name=role_name)
                db.session.add(new_role)
                print(f"'{role_name}' 역할 생성 완료.")
        db.session.commit()
        print("모든 역할이 준비되었습니다.")

        # 2. 관리자 계정 및 역할 할당 확인/수정
        admin_email = os.environ.get('ADMIN_EMAIL', 'admin@example.com')
        admin_password = os.environ.get('ADMIN_PASSWORD', 'admin123')
        admin_role = Role.query.filter_by(name='관리자').first()

        if not admin_role:
            print("치명적 오류: '관리자' 역할을 찾을 수 없습니다. 스크립트를 다시 확인하세요.")
            return

        admin_user = User.query.filter_by(email=admin_email).first()

        if not admin_user:
            hashed_password = generate_password_hash(admin_password)
            admin_user = User(
                username='admin', email=admin_email, password_hash=hashed_password,
                nickname='관리자', user_uid='0000000001', gender='기타', age=0, major='관리'
            )
            admin_user.roles.append(admin_role)
            db.session.add(admin_user)
            print(f"새로운 관리자 계정 생성 및 역할 할당 완료 (Email: {admin_email})")
        else:
            print("기존 관리자 계정을 확인합니다...")
            # FIX: UserRole 클래스에서 실제 테이블 객체(__table__)를 참조합니다.
            user_roles_table = UserRole.__table__
            stmt = select(user_roles_table).where(
                and_(user_roles_table.c.user_id == admin_user.id, user_roles_table.c.role_id == admin_role.id)
            )
            result = db.session.execute(stmt).first()

            if not result:
                print(f" -> '관리자' 역할이 할당되어 있지 않습니다. 역할을 추가합니다...")
                # FIX: UserRole.__table__을 사용하여 테이블에 직접 데이터를 삽입합니다.
                insert_stmt = user_roles_table.insert().values(user_id=admin_user.id, role_id=admin_role.id)
                db.session.execute(insert_stmt)
            else:
                print("관리자 계정에 이미 '관리자' 역할이 할당되어 있습니다.")
        
        try:
            db.session.commit()
            print(" -> 데이터베이스 커밋 성공.")
        except Exception as e:
            print(f" -> 데이터베이스 커밋 실패: {e}")
            db.session.rollback()

        print("데이터베이스 초기화/검증이 성공적으로 완료되었습니다.")

if __name__ == '__main__':
    initialize_database()
>>>>>>> 32e57f7623365b93a09d34dc9cad501cc18c11af

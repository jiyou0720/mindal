import os
from backend.extensions import db, bcrypt
from backend.maria_models import User, Role

def initialize_database():
    """데이터베이스 역할과 관리자 계정을 확인하고 생성합니다."""
    print("데이터베이스 초기화/검증을 시작합니다...")
    
    try:
        # 역할 목록
        roles = ['관리자', '운영자', '개발자', '연구자', '일반 사용자']
        
        # 모든 역할이 존재하는지 확인하고 없으면 생성
        for role_name in roles:
            if not Role.query.filter_by(name=role_name).first():
                new_role = Role(name=role_name)
                db.session.add(new_role)
                print(f"'{role_name}' 역할 생성 완료.")
        
        db.session.commit()
        print("모든 역할이 준비되었습니다.")

        # 관리자 계정 확인 및 생성
        admin_email = os.environ.get('ADMIN_EMAIL', 'admin@example.com')
        admin_user = User.query.filter_by(email=admin_email).first()

        admin_role = Role.query.filter_by(name='관리자').first()
        if not admin_role:
            # 이 경우는 거의 없지만, 방어적으로 코딩
            print("CRITICAL: '관리자' 역할을 찾을 수 없어 새로 생성합니다.")
            admin_role = Role(name='관리자')
            db.session.add(admin_role)
            db.session.commit()
            admin_role = Role.query.filter_by(name='관리자').first()

        if not admin_user:
            print(f"관리자 계정({admin_email})을 생성합니다...")
            admin_password = os.environ.get('ADMIN_PASSWORD')
            if not admin_password:
                raise ValueError("ADMIN_PASSWORD 환경 변수가 설정되지 않았습니다.")
            
            hashed_password = bcrypt.generate_password_hash(admin_password).decode('utf-8')
            
            new_admin_user = User(
                username='admin',
                email=admin_email,
                password_hash=hashed_password,
                nickname='관리자'
            )
            
            # 표준 다대다 관계 방식에 맞게 역할 할당
            new_admin_user.roles.append(admin_role)
            
            db.session.add(new_admin_user)
            db.session.commit()
            print("관리자 계정 생성 및 역할 할당 완료.")
        else:
            # 기존 관리자에게 역할이 할당되었는지 확인
            # 'roles'는 이제 리스트이므로 'in' 연산자로 확인
            if admin_role not in admin_user.roles:
                admin_user.roles.append(admin_role)
                db.session.commit()
                print("기존 관리자 계정에 '관리자' 역할 할당 완료.")
            else:
                print("기존 관리자 계정 존재 및 역할 할당 확인 완료.")

    except Exception as e:
        db.session.rollback()
        print(f"데이터베이스 초기화 중 오류 발생: {e}")
        raise e
    finally:
        db.session.close()

    print("데이터베이스 초기화/검증이 성공적으로 완료되었습니다.")


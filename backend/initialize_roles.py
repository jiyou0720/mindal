import os
import sys
from dotenv import load_dotenv
from flask import Flask
# 프로젝트 루트 디렉토리를 Python 경로에 추가합니다.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from backend.extensions import db
from backend.maria_models import Role 

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

app = Flask(__name__)
# app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('MARIADB_URI') # 이 부분은 .env 파일에 MARIADB_URI가 정의되어 있지 않으므로, app.py의 방식대로 수정합니다.
MARIA_USER = os.environ.get("MARIA_USER")
MARIA_PASSWORD = os.environ.get("MARIA_PASSWORD")
MARIA_HOST = os.environ.get("MARIA_HOST")
MARIA_PORT = os.environ.get("MARIA_PORT")
MARIA_DB = os.environ.get("MARIA_DB")

app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql+pymysql://{MARIA_USER}:{MARIA_PASSWORD}@{MARIA_HOST}:{MARIA_PORT}/{MARIA_DB}?charset=utf8mb4'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# JWT_SECRET_KEY도 필요할 수 있으므로 추가 (app.py에서 요구함)
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'default_jwt_secret_key')


db.init_app(app)

with app.app_context():
    # 데이터베이스 테이블이 없으면 생성
    # 이 스크립트는 역할만 추가하므로 db.create_all()은 initialize_roles_and_admin.py에서만 호출하는 것이 좋습니다.
    # 하지만, 역할 테이블이 없으면 오류가 나므로, 필요한 경우에만 실행하도록 합니다.
    # 또는, 마이그레이션을 통해 테이블이 생성되었다고 가정합니다.

    roles_to_add = ['관리자', '운영자', '에디터', '일반 사용자', '개발자', '연구자', '모든 사용자']
    
    for role_name in roles_to_add:
        role = Role.query.filter_by(name=role_name).first()
        if not role:
            new_role = Role(name=role_name)
            db.session.add(new_role)
            print(f"역할 '{role_name}' 추가됨.")
        else:
            print(f"역할 '{role_name}' 이미 존재함.")
    
    db.session.commit()
    print("역할 초기화 완료.")

import os
import sys
from dotenv import load_dotenv
from flask import Flask
# 프로젝트 루트 디렉토리를 Python 경로에 추가합니다.
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.append(project_root)

from backend.extensions import db
from backend.maria_models import Role 

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))

app = Flask(__name__)
# app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('MARIADB_URI') # 이 부분은 .env 파일에 MARIADB_URI가 정의되어 있지 않으므로, app.py의 방식대로 수정합니다.
MARIA_USER = os.environ.get("MARIA_USER")
MARIA_PASSWORD = os.environ.get("MARIA_PASSWORD")
MARIA_HOST = os.environ.get("MARIA_HOST")
MARIA_PORT = os.environ.get("MARIA_PORT")
MARIA_DB = os.environ.get("MARIA_DB")

app.config['SQLALCHEMY_DATABASE_URI'] = f'mysql+pymysql://{MARIA_USER}:{MARIA_PASSWORD}@{MARIA_HOST}:{MARIA_PORT}/{MARIA_DB}?charset=utf8mb4'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
# JWT_SECRET_KEY도 필요할 수 있으므로 추가 (app.py에서 요구함)
app.config['JWT_SECRET_KEY'] = os.environ.get('JWT_SECRET_KEY', 'default_jwt_secret_key')


db.init_app(app)

def initialize_roles():
    with app.app_context():
        roles_to_add = ['관리자', '운영자', '에디터', '일반 사용자', '개발자', '연구자', '모든 사용자']
        
        for role_name in roles_to_add:
            role = Role.query.filter_by(name=role_name).first()
            if not role:
                new_role = Role(name=role_name)
                db.session.add(new_role)
                print(f"역할 '{role_name}' 추가됨.")
            else:
                print(f"역할 '{role_name}' 이미 존재함.")
        
        db.session.commit()
        print("역할 초기화 완료.")

if __name__ == "__main__":
    initialize_roles()
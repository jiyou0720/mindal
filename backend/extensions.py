from flask_sqlalchemy import SQLAlchemy
from flask_pymongo import PyMongo
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_bcrypt import Bcrypt  # 1. Bcrypt 라이브러리를 가져옵니다.

# 각 Flask 확장 기능의 인스턴스를 생성합니다.
# 이 인스턴스들은 app.py에서 애플리케이션과 연결됩니다.
db = SQLAlchemy()
mongo = PyMongo()
migrate = Migrate()
jwt = JWTManager()
bcrypt = Bcrypt()              # 2. bcrypt 인스턴스를 생성하여 다른 파일에서 사용할 수 있도록 합니다.


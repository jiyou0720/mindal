from flask_sqlalchemy import SQLAlchemy
from flask_pymongo import PyMongo
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager

# 각 Flask 확장(extension)의 인스턴스를 생성합니다.
# 이 인스턴스들은 app.py의 create_app 함수 내에서
# 애플리케이션과 연결(init_app)됩니다.

db = SQLAlchemy()
mongo = PyMongo()
migrate = Migrate()
jwt = JWTManager() # JWTManager 인스턴스 추가

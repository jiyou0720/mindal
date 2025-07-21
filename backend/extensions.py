# backend/extensions.py
from flask_sqlalchemy import SQLAlchemy
from flask_pymongo import PyMongo # PyMongo 임포트 추가

db = SQLAlchemy()
mongo = PyMongo() # PyMongo 인스턴스 초기화 추가

# 이 함수는 app.py에서 Flask 앱 인스턴스를 받아 db와 mongo를 초기화합니다.
def init_extensions(app):
    db.init_app(app)
    mongo.init_app(app) # mongo 인스턴스도 앱과 연결

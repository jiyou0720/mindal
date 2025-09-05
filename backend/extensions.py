from flask_sqlalchemy import SQLAlchemy
from flask_pymongo import PyMongo
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_bcrypt import Bcrypt

db = SQLAlchemy()
mongo = PyMongo()
migrate = Migrate()
jwt = JWTManager()
bcrypt = Bcrypt()

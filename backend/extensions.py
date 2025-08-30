from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_pymongo import PyMongo

db = SQLAlchemy()
migrate = Migrate()
mongo = PyMongo()

from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_pymongo import PyMongo

db = SQLAlchemy()
# FIX: Add the missing Migrate object instance
migrate = Migrate()
mongo = PyMongo()

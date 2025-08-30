from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import pymongo

db = SQLAlchemy()
migrate = Migrate()
mongo = pymongo.MongoClient()

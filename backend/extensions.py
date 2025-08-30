<<<<<<< HEAD
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_pymongo import PyMongo

db = SQLAlchemy()
# FIX: Add the missing Migrate object instance
migrate = Migrate()
mongo = PyMongo()
=======
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_pymongo import PyMongo

db = SQLAlchemy()
# FIX: Add the missing Migrate object instance
migrate = Migrate()
mongo = PyMongo()
>>>>>>> 32e57f7623365b93a09d34dc9cad501cc18c11af

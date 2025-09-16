from backend.extensions import db
import datetime

# --- 사용자 및 인증 관련 모델 ---
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    nickname = db.Column(db.String(80), unique=True, nullable=False)
    user_uid = db.Column(db.String(120), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    is_social = db.Column(db.Boolean, default=False)

class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    users = db.relationship('User', backref='role', lazy=True)

class MenuAccess(db.Model):
    __tablename__ = 'menu_access'
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), primary_key=True)
    menu_item_id = db.Column(db.String(255), primary_key=True) # MongoDB _id는 문자열

# --- 커뮤니티 관련 모델 ---
class Post(db.Model):
    __tablename__ = 'posts'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    mongo_content_id = db.Column(db.String(24), nullable=False) # MongoDB ObjectId는 24자리 문자열
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    is_anonymous = db.Column(db.Boolean, default=False, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    views = db.Column(db.Integer, default=0)
    is_notice = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    is_suspended = db.Column(db.Boolean, default=False)
    suspended_until = db.Column(db.DateTime, nullable=True)
    author = db.relationship('User', backref=db.backref('posts', lazy=True))

class Comment(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)
    # ✅ 누락되었던 'is_anonymous' 컬럼 추가
    is_anonymous = db.Column(db.Boolean, default=False, nullable=False)
    
    author = db.relationship('User', backref=db.backref('comments', lazy=True))
    post = db.relationship('Post', backref=db.backref('comments', lazy=True, cascade="all, delete-orphan"))

class PostLike(db.Model):
    __tablename__ = 'post_likes'
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), primary_key=True)

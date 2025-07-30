# backend/maria_models.py

import datetime
from backend.extensions import db
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm import relationship # relationship 임포트 확인

# FIX: Define the UserRole association class as requested by other modules.
class UserRole(db.Model):
    __tablename__ = 'user_roles'
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), primary_key=True)

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    user_uid = db.Column(db.String(255), unique=True, nullable=False)
    nickname = db.Column(db.String(80), unique=True, nullable=True)
    gender = db.Column(db.String(10))
    age = db.Column(db.Integer)
    major = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # User와 Role의 다대다 관계 설정
    roles = db.relationship('Role', secondary='user_roles',
                            backref=db.backref('users', lazy='dynamic'))
    
    # User와 Post의 일대다 관계 설정
    posts = db.relationship('Post', backref='author', lazy=True, cascade="all, delete-orphan")
    # User와 Comment의 일대다 관계 설정
    comments = db.relationship('Comment', backref='author', lazy=True, cascade="all, delete-orphan")
    # User와 PostLike의 일대다 관계 설정
    post_likes = db.relationship('PostLike', backref='user', lazy=True, cascade="all, delete-orphan")
    # User와 CommentLike의 일대다 관계 설정
    comment_likes = db.relationship('CommentLike', backref='user', lazy=True, cascade="all, delete-orphan")
    # User와 NicknameHistory의 일대다 관계 설정
    nickname_history = db.relationship('NicknameHistory', backref='user', lazy=True, cascade="all, delete-orphan")


    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    # NEW: to_dict method for User model
    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'user_uid': self.user_uid,
            'nickname': self.nickname,
            'gender': self.gender,
            'age': self.age,
            'major': self.major,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'roles': [role.name for role in self.roles] # Include role names
        }

    def __repr__(self):
        return f'<User {self.username}>'

class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)

    def __repr__(self):
        return f'<Role {self.name}>'

class Post(db.Model):
    __tablename__ = 'posts'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    # MongoDB에 저장된 본문 내용의 ObjectId를 참조
    mongo_content_id = db.Column(db.String(255), nullable=False) 
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    is_anonymous = db.Column(db.Boolean, default=False)
    is_notice = db.Column(db.Boolean, default=False) # 공지사항 여부
    views = db.Column(db.Integer, default=0)
    category = db.Column(db.String(50), nullable=True) # 게시글 카테고리
    is_suspended = db.Column(db.Boolean, default=False) # NEW: 게시글 정지 여부
    suspended_until = db.Column(db.DateTime, nullable=True) # NEW: 정지 해제 일시
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    comments = db.relationship('Comment', backref='post', lazy=True, cascade="all, delete-orphan")
    likes = db.relationship('PostLike', backref='post', lazy=True, cascade="all, delete-orphan")

class Comment(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    likes = db.relationship('CommentLike', backref='comment', lazy=True, cascade="all, delete-orphan")

class PostLike(db.Model):
    __tablename__ = 'post_likes'
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), primary_key=True)

class CommentLike(db.Model):
    __tablename__ = 'comment_likes'
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    comment_id = db.Column(db.Integer, db.ForeignKey('comments.id'), primary_key=True)

class NicknameHistory(db.Model):
    __tablename__ = 'nickname_history'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    old_nickname = db.Column(db.String(80), nullable=True)
    new_nickname = db.Column(db.String(80), nullable=False)
    changed_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

# NEW: Notice Model for Notice Management
class Notice(db.Model):
    __tablename__ = 'notices'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False) # 작성자 ID
    is_public = db.Column(db.Boolean, default=True) # 공개/비공개 여부
    start_date = db.Column(db.DateTime, nullable=True) # NEW: 게시 시작일 필드 추가
    end_date = db.Column(db.DateTime, nullable=True)   # NEW: 게시 종료일 필드 추가
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # Notice와 User의 관계 설정 (작성자)
    author = relationship('User', backref='notices', lazy=True)

    def __repr__(self):
        return f'<Notice {self.title}>'


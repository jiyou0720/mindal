# backend/maria_models.py

import datetime
from extensions import db
from werkzeug.security import generate_password_hash, check_password_hash


class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    user_uid = db.Column(db.String(10), unique=True, nullable=False)
    nickname = db.Column(db.String(80), unique=False, nullable=True) # 별명 (고유하지 않아도 됨)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    is_admin = db.Column(db.Boolean, default=False, nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        # 디버깅용
        print(f"비밀번호 해싱 완료. 저장될 해시: {self.password_hash}\n")

    def check_password(self, password):
        # 디버깅용
        # print(f"입력 비밀번호: {password}, 저장된 해시: {self.password_hash}")
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username, # 이 부분이 반드시 포함되어야 합니다.
            "email": self.email,
            "user_uid": self.user_uid,
            "nickname": self.nickname,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "is_admin": self.is_admin
        }

    def __repr__(self):
        return f'<User {self.username}>'


class Post(db.Model):
    __tablename__ = 'posts'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    author_username = db.Column(db.String(80), nullable=False)
    category = db.Column(db.String(50), nullable=False)  # 추가된 category 필드
    is_anonymous = db.Column(db.Boolean, default=False, nullable=False)  # 추가된 익명 여부 필드
    display_author_name = db.Column(db.String(80), nullable=True)  # 추가된 실제 표시될 작성자 이름 필드
    mongodb_content_id = db.Column(db.String(24), unique=True, nullable=True) # MongoDB ObjectId
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    
    # --- 추가된 부분: views 컬럼 ---
    views = db.Column(db.Integer, default=0, nullable=False) # 조회수 필드 추가
    # -------------------------------

    author = db.relationship('User', backref='posts', lazy=True) # User 모델과의 관계 설정

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "author_id": self.author_id,
            "author_username": self.author_username,
            "category": self.category, # to_dict에 추가
            "is_anonymous": self.is_anonymous, # to_dict에 추가
            "display_author_name": self.display_author_name, # to_dict에 추가
            "mongodb_content_id": self.mongodb_content_id,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "views": self.views # to_dict에 추가
        }

    def __repr__(self):
        return f'<Post {self.title}>'

class Comment(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    author_username = db.Column(db.String(80), nullable=False)
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    display_author_name = db.Column(db.String(80), nullable=True) # 새로 추가: 댓글 작성자 표시 이름

    post = db.relationship('Post', backref='comments', lazy=True)
    author = db.relationship('User', backref='comments', lazy=True)

    def to_dict(self):
        return {
            "id": self.id,
            "post_id": self.post_id,
            "author_id": self.author_id,
            "author_username": self.author_username,
            "content": self.content,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "display_author_name": self.display_author_name # to_dict에 포함
        }

    def __repr__(self):
        return f'<Comment {self.id} on Post {self.post_id}>'

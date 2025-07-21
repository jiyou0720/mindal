import datetime
from extensions import db
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm import relationship # relationship 임포트 추가

# 중간 테이블: User <-> Role (Many-to-Many)
class UserRole(db.Model):
    __tablename__ = 'user_roles'
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), primary_key=True)

    user = db.relationship('User', back_populates='user_roles_association', overlaps="roles,users")
    role = db.relationship('Role', back_populates='role_users_association', overlaps="users,roles")

    def __repr__(self):
        return f'<UserRole UserID:{self.user_id} RoleID:{self.role_id}>'

# 사용자 모델
class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    user_uid = db.Column(db.String(10), unique=True, nullable=False) # 고유 숫자 ID
    nickname = db.Column(db.String(80), unique=True, nullable=True) # 닉네임 필드 추가
    gender = db.Column(db.String(10), nullable=True) # 성별 필드 추가
    age = db.Column(db.Integer, nullable=True) # 나이 필드 추가
    major = db.Column(db.String(100), nullable=True) # 전공 필드 추가
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # User-Role 관계 설정
    user_roles_association = db.relationship('UserRole', back_populates='user', cascade="all, delete-orphan")
    roles = db.relationship('Role', secondary='user_roles', back_populates='users', viewonly=True)

    # 게시글 및 댓글과의 관계
    posts = db.relationship('Post', backref='author', lazy=True, cascade="all, delete-orphan")
    comments = db.relationship('Comment', backref='author', lazy=True, cascade="all, delete-orphan")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

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
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'roles': [role.name for role in self.roles] # 역할 이름 목록 반환
        }

    def __repr__(self):
        return f'<User {self.username}>'

# 역할 모델
class Role(db.Model):
    __tablename__ = 'roles'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)

    # Role-User 관계 설정
    role_users_association = db.relationship('UserRole', back_populates='role', cascade="all, delete-orphan")
    users = db.relationship('User', secondary='user_roles', back_populates='roles', viewonly=True)

    def __repr__(self):
        return f'<Role {self.name}>'

# 게시글 모델
class Post(db.Model):
    __tablename__ = 'posts'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    author_nickname = db.Column(db.String(80), nullable=True) # ⭐ 추가: 작성자 닉네임 필드
    category = db.Column(db.String(50), nullable=False)
    is_anonymous = db.Column(db.Boolean, default=False)
    mongodb_content_id = db.Column(db.String(24), unique=True, nullable=False) # MongoDB ObjectId (24자 hex string)
    views = db.Column(db.Integer, default=0)
    likes = db.Column(db.Integer, default=0) # 공감 수 필드 추가
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # 관계 설정
    comments = db.relationship('Comment', backref='post', lazy=True, cascade="all, delete-orphan")
    post_likes = db.relationship('PostLike', back_populates='post', lazy=True, cascade="all, delete-orphan") # PostLike 관계 추가

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "author_id": self.author_id,
            "author_nickname": self.author_nickname, # 딕셔너리 반환 시 포함
            "category": self.category,
            "is_anonymous": self.is_anonymous,
            "mongodb_content_id": self.mongodb_content_id,
            "views": self.views,
            "likes": self.likes,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }

    def __repr__(self):
        return f'<Post {self.id}: {self.title}>'

# 댓글 모델
class Comment(db.Model):
    __tablename__ = 'comments'
    id = db.Column(db.Integer, primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    author_nickname = db.Column(db.String(80), nullable=True) # ⭐ 추가: 댓글 작성자 닉네임 필드
    content = db.Column(db.Text, nullable=False)
    likes = db.Column(db.Integer, default=0) # 공감 수 추가
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

    # 관계 설정
    comment_likes = db.relationship('CommentLike', back_populates='comment', lazy=True, cascade="all, delete-orphan") # CommentLike 관계 추가

    def to_dict(self):
        return {
            "id": self.id,
            "post_id": self.post_id,
            "author_id": self.author_id,
            "author_nickname": self.author_nickname, # 딕셔너리 반환 시 포함
            "content": self.content,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "likes": self.likes # 공감 수 추가
        }

    def __repr__(self):
        return f'<Comment {self.id} on Post {self.post_id}>'

# 게시글 공감 모델
class PostLike(db.Model):
    __tablename__ = 'post_likes'
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    # 관계 설정
    user = db.relationship('User', backref=db.backref('liked_posts', lazy=True))
    post = db.relationship('Post', back_populates='post_likes', lazy=True)

    def __repr__(self):
        return f'<PostLike UserID:{self.user_id} PostID:{self.post_id}>'

# 댓글 공감 모델
class CommentLike(db.Model):
    __tablename__ = 'comment_likes'
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    comment_id = db.Column(db.Integer, db.ForeignKey('comments.id'), primary_key=True)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    # 관계 설정
    user = db.relationship('User', backref=db.backref('liked_comments', lazy=True))
    comment = db.relationship('Comment', back_populates='comment_likes', lazy=True)

    def __repr__(self):
        return f'<CommentLike UserID:{self.user_id} CommentID:{self.comment_id}>'

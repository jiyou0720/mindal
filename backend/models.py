# # backend/models.py
# from werkzeug.security import generate_password_hash, check_password_hash
# from bson.objectid import ObjectId
# import datetime
# from app import db # app.py에서 초기화한 SQLAlchemy 'db' 인스턴스 임포트

# # --- MariaDB용 User 모델 (이전 단계에서 이미 수정됨) ---
# class User(db.Model):
#     __tablename__ = 'users'
#     id = db.Column(db.Integer, primary_key=True)
#     username = db.Column(db.String(80), unique=True, nullable=False)
#     email = db.Column(db.String(120), unique=True, nullable=False)
#     password_hash = db.Column(db.String(128), nullable=False)
#     created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
#     updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

#     def set_password(self, password):
#         self.password_hash = generate_password_hash(password)

#     def check_password(self, password):
#         return check_password_hash(self.password_hash, password)

#     def to_dict(self):
#         return {
#             "id": self.id,
#             "username": self.username,
#             "email": self.email,
#             "created_at": self.created_at.isoformat(),
#             "updated_at": self.updated_at.isoformat()
#         }

#     def __repr__(self):
#         return f'<User {self.username}>'

# # --- MongoDB에 게시글 '내용'만 저장할 새로운 클래스 ---
# # 기존 Post 클래스를 대체하며, 오직 'content'와 MongoDB '_id'만 관리
# class MongoPostContent:
#     def __init__(self, content, _id=None):
#         self.content = content
#         if _id:
#             self._id = _id

#     def to_dict(self):
#         return {
#             "content": self.content,
#             "_id": str(self._id) if hasattr(self, '_id') else None
#         }

#     @staticmethod
#     def from_mongo(data):
#         return MongoPostContent(
#             content=data.get('content'),
#             _id=data.get('_id')
#         )

# # --- MariaDB용 Post 모델 추가 ---
# class Post(db.Model):
#     __tablename__ = 'posts'
#     id = db.Column(db.Integer, primary_key=True)
#     title = db.Column(db.String(255), nullable=False)
#     author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False) # users 테이블의 id 참조
#     author_username = db.Column(db.String(80), nullable=False) # 사용자 이름 캐싱
#     mongodb_content_id = db.Column(db.String(24), unique=True, nullable=True) # MongoDB ObjectId (문자열로 저장)
#     created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
#     updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

#     # Relationship to User for easier access
#     author = db.relationship('User', backref='posts', lazy=True)

#     def to_dict(self):
#         return {
#             "id": self.id,
#             "title": self.title,
#             "author_id": self.author_id,
#             "author_username": self.author_username,
#             "mongodb_content_id": self.mongodb_content_id,
#             "created_at": self.created_at.isoformat(),
#             "updated_at": self.updated_at.isoformat()
#         }

#     def __repr__(self):
#         return f'<Post {self.title}>'

# # --- MariaDB용 Comment 모델 추가 ---
# # 댓글 내용은 MariaDB에 직접 저장
# class Comment(db.Model):
#     __tablename__ = 'comments'
#     id = db.Column(db.Integer, primary_key=True)
#     post_id = db.Column(db.Integer, db.ForeignKey('posts.id'), nullable=False) # posts 테이블의 id 참조
#     author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False) # users 테이블의 id 참조
#     author_username = db.Column(db.String(80), nullable=False) # 사용자 이름 캐싱
#     content = db.Column(db.Text, nullable=False) # 댓글 내용
#     created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
#     updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)

#     # Relationships
#     post = db.relationship('Post', backref='comments', lazy=True)
#     author = db.relationship('User', backref='comments', lazy=True)

#     def to_dict(self):
#         return {
#             "id": self.id,
#             "post_id": self.post_id,
#             "author_id": self.author_id,
#             "author_username": self.author_username,
#             "content": self.content,
#             "created_at": self.created_at.isoformat(),
#             "updated_at": self.updated_at.isoformat()
#         }

#     def __repr__(self):
#         return f'<Comment {self.id} on Post {self.post_id}>'

# # --- 기존 MongoDB용 DiaryEntry 클래스 (변동 없음) ---
# # user_id는 MariaDB User의 ID(정수형)를 참조하게 됩니다.
# class DiaryEntry:
#     """
#     감정 일기 항목 모델 (MongoDB 사용)
#     """
#     def __init__(self, user_id, title, content, _id=None, created_at=None, updated_at=None):
#         self.user_id = user_id # MariaDB User의 ID (정수형)
#         self.title = title
#         self.content = content
#         self.created_at = created_at if created_at else datetime.datetime.utcnow()
#         self.updated_at = updated_at if updated_at else datetime.datetime.utcnow()
#         if _id:
#             self._id = _id

#     def to_dict(self):
#         return {
#             "user_id": self.user_id,
#             "title": self.title,
#             "content": self.content,
#             "created_at": self.created_at.isoformat(),
#             "updated_at": self.updated_at.isoformat(),
#             "_id": str(self._id) if hasattr(self, '_id') else None
#         }

#     @staticmethod
#     def from_mongo(data):
#         return DiaryEntry(
#             user_id=data.get('user_id'),
#             title=data.get('title'),
#             content=data.get('content'),
#             _id=data.get('_id'),
#             created_at=data.get('created_at'),
#             updated_at=data.get('updated_at')
#         )
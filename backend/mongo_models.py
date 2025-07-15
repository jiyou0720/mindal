# backend/mongo_models.py
from bson.objectid import ObjectId
import datetime

# --- MongoDB에 게시글 '내용'만 저장할 클래스 ---
class MongoPostContent:
    def __init__(self, content, _id=None):
        self.content = content
        if _id:
            self._id = _id

    def to_dict(self):
        return {
            "content": self.content,
            "_id": str(self._id) if hasattr(self, '_id') else None
        }

    @staticmethod
    def from_mongo(data):
        return MongoPostContent(
            content=data.get('content'),
            _id=data.get('_id')
        )

# --- MongoDB용 DiaryEntry 클래스 ---
class DiaryEntry:
    # 'date'와 'mood_emoji_key' 필드 추가
    def __init__(self, user_id, title, content, date, mood_emoji_key=None, _id=None, created_at=None, updated_at=None):
        self.user_id = user_id # MariaDB User의 ID (정수형)
        self.title = title
        self.content = content
        self.date = date # 일기 날짜 (YYYY-MM-DD 형식 문자열)
        self.mood_emoji_key = mood_emoji_key # 선택된 이모티콘의 키 (예: 'happy', 'sad')
        self.created_at = created_at if created_at else datetime.datetime.utcnow()
        self.updated_at = updated_at if updated_at else datetime.datetime.utcnow()
        if _id:
            self._id = _id

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "title": self.title,
            "content": self.content,
            "date": self.date, # date 필드 to_dict에 추가
            "mood_emoji_key": self.mood_emoji_key, # mood_emoji_key 필드 to_dict에 추가
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "_id": str(self._id) if hasattr(self, '_id') else None
        }

    @staticmethod
    def from_mongo(data):
        return DiaryEntry(
            user_id=data.get('user_id'),
            title=data.get('title'),
            content=data.get('content'),
            date=data.get('date'), # from_mongo에 추가
            mood_emoji_key=data.get('mood_emoji_key'), # from_mongo에 추가
            _id=data.get('_id'),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at')
        )

# --- MongoDB용 MoodEntry 클래스 (새로 추가) ---
class MoodEntry:
    def __init__(self, user_id, mood_type, description=None, _id=None, created_at=None, updated_at=None):
        self.user_id = user_id # MariaDB User의 ID
        self.mood_type = mood_type # 예: 'happy', 'sad', 'angry' 등
        self.description = description # 감정에 대한 선택적 설명
        self.created_at = created_at if created_at else datetime.datetime.utcnow()
        self.updated_at = updated_at if updated_at else datetime.datetime.utcnow()
        if _id:
            self._id = _id

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "mood_type": self.mood_type,
            "description": self.description,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "_id": str(self._id) if hasattr(self, '_id') else None
        }

    @staticmethod
    def from_mongo(data):
        return MoodEntry(
            user_id=data.get('user_id'),
            mood_type=data.get('mood_type'),
            description=data.get('description'),
            _id=data.get('_id'),
            created_at=data.get('created_at'),
            updated_at=data.get('updated_at')
        )
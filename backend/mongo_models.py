# backend/mongo_models.py

from bson.objectid import ObjectId
import datetime

# --- MongoDB에 게시글 '내용'만 저장할 클래스 ---
class MongoPostContent:
    def __init__(self, content, attachment_paths=None, _id=None):
        self.content = content
        self.attachment_paths = attachment_paths if attachment_paths is not None else []
        if _id:
            self._id = _id

    def to_dict(self):
        data = {
            "content": self.content,
            "attachment_paths": self.attachment_paths,
        }
        # _id가 존재하고 None이 아닐 경우에만 포함
        if hasattr(self, '_id') and self._id is not None:
            # ObjectId 객체인 경우 문자열로 변환
            if isinstance(self._id, ObjectId):
                data["_id"] = str(self._id)
            else:
                data["_id"] = self._id # 이미 문자열인 경우 그대로 사용
        return data

    @staticmethod
    def from_mongo(data):
        return MongoPostContent(
            content=data.get('content'),
            attachment_paths=data.get('attachment_paths', []),
            _id=data.get('_id')
        )

# --- MongoDB에 다이어리 항목을 저장할 클래스 ---
class DiaryEntry:
    def __init__(self, user_id, date, content, mood, keywords=None, _id=None):
        self.user_id = user_id
        self.date = date # ISO 형식 문자열 또는 datetime 객체
        self.content = content
        self.mood = mood
        self.keywords = keywords if keywords is not None else []
        if _id:
            self._id = _id

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "date": self.date.isoformat() if isinstance(self.date, datetime.datetime) else self.date,
            "content": self.content,
            "mood": self.mood,
            "keywords": self.keywords,
            "_id": str(self._id) if hasattr(self, '_id') else None
        }

    @staticmethod
    def from_mongo(data):
        # date 필드가 문자열이면 datetime 객체로 변환 시도
        date_obj = data.get('date')
        if isinstance(date_obj, str):
            try:
                date_obj = datetime.datetime.fromisoformat(date_obj)
            except ValueError:
                # ISO 형식이 아니면 (예: MongoDB의 BSON Date) 그대로 사용
                pass
        
        return DiaryEntry(
            user_id=data.get('user_id'),
            date=date_obj,
            content=data.get('content'),
            mood=data.get('mood'),
            keywords=data.get('keywords', []),
            _id=data.get('_id')
        )

# --- MongoDB에 감정 기록 항목을 저장할 클래스 ---
class MoodEntry:
    def __init__(self, user_id, date, mood_score, timestamp=None, _id=None):
        self.user_id = user_id
        self.date = date # YYYY-MM-DD 형식의 문자열 (날짜만)
        self.mood_score = mood_score # 1-5점
        self.timestamp = timestamp if timestamp is not None else datetime.datetime.utcnow() # 기록 시점
        if _id:
            self._id = _id

    def to_dict(self):
        return {
            "user_id": self.user_id,
            "date": self.date, # 날짜 문자열은 그대로 사용
            "mood_score": self.mood_score,
            "timestamp": self.timestamp.isoformat(),
            "_id": str(self._id) if hasattr(self, '_id') else None
        }

    @staticmethod
    def from_mongo(data):
        return MoodEntry(
            user_id=data.get('user_id'),
            date=data.get('date'),
            mood_score=data.get('mood_score'),
            timestamp=data.get('timestamp'),
            _id=data.get('_id')
        )

# 이 파일에는 MariaDB 관련 모델(User, Post, Comment)이 없어야 합니다.
# 해당 모델들은 maria_models.py에만 정의되어야 합니다.

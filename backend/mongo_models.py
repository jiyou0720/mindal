# backend/mongo_models.py
from bson.objectid import ObjectId
import json
import datetime

class MongoPostContent:
    def __init__(self, content, attachment_paths=None, post_id=None, _id=None): # post_id 필드 추가
        self._id = _id if _id else ObjectId()
        self.post_id = post_id # MariaDB의 게시글 ID를 저장할 필드
        self.content = content
        self.attachment_paths = attachment_paths if attachment_paths is not None else []

    def to_dict(self):
        data = {
            "_id": str(self._id),
            "content": self.content,
            "attachment_paths": self.attachment_paths
        }
        if self.post_id: # post_id가 있으면 딕셔너리에 추가
            data["post_id"] = self.post_id
        return data

    @staticmethod
    def from_mongo(data):
        return MongoPostContent(
            _id=data.get('_id'),
            post_id=data.get('post_id'), # post_id 필드 로드
            content=data.get('content'),
            attachment_paths=data.get('attachment_paths', [])
        )

class MenuItem:
    def __init__(self, name, path, icon_class, required_roles=None, order=None, _id=None):
        self.name = name
        self.path = path
        self.icon_class = icon_class
        self.required_roles = required_roles if required_roles is not None else []
        self.order = order # 메뉴 순서 필드 추가
        self._id = _id if _id else None # None으로 설정하여 MongoDB가 자동 생성하도록 유도

    def to_dict(self):
        data = {
            "name": self.name,
            "path": self.path,
            "icon_class": self.icon_class,
            "required_roles": self.required_roles
        }
        if self.order is not None:
            data["order"] = self.order
        if self._id:
            data["_id"] = str(self._id)
        return data

    @staticmethod
    def from_mongo(data):
        return MenuItem(
            name=data.get('name'),
            path=data.get('path'),
            icon_class=data.get('icon_class'),
            required_roles=data.get('required_roles', []),
            order=data.get('order'),
            _id=data.get('_id')
        )

class DiaryEntry:
    def __init__(self, user_id, title, content, date, mood_emoji_key, created_at=None, updated_at=None, _id=None):
        self._id = _id if _id else ObjectId()
        self.user_id = user_id
        self.title = title
        self.content = content
        self.date = date # YYYY-MM-DD 형식의 문자열 (날짜만)
        self.mood_emoji_key = mood_emoji_key # 'happy', 'sad' 등 이모지 키
        self.created_at = created_at if created_at is not None else datetime.datetime.utcnow()
        self.updated_at = updated_at if updated_at is not None else datetime.datetime.utcnow()

    def to_dict(self):
        return {
            "_id": str(self._id),
            "user_id": self.user_id,
            "title": self.title,
            "content": self.content,
            "date": self.date,
            "mood_emoji_key": self.mood_emoji_key,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @staticmethod
    def from_mongo(data):
        _id = data.get('_id')
        user_id = data.get('user_id')
        title = data.get('title')
        content = data.get('content')
        date = data.get('date')
        mood_emoji_key = data.get('mood_emoji_key')
        created_at = data.get('created_at')
        updated_at = data.get('updated_at')

        if created_at and isinstance(created_at, str):
            created_at = datetime.datetime.fromisoformat(created_at)
        if updated_at and isinstance(updated_at, str):
            updated_at = datetime.datetime.fromisoformat(updated_at)

        return DiaryEntry(
            _id=_id,
            user_id=user_id,
            title=title,
            content=content,
            date=date,
            mood_emoji_key=mood_emoji_key,
            created_at=created_at,
            updated_at=updated_at
        )

class MoodEntry:
    def __init__(self, user_id, date, mood_score, timestamp=None, _id=None):
        self._id = _id if _id else ObjectId()
        self.user_id = user_id
        self.date = date # YYYY-MM-DD 형식의 문자열 (날짜만)
        self.mood_score = mood_score # 1-5점
        self.timestamp = timestamp if timestamp is not None else datetime.datetime.utcnow() # 기록 시점

    def to_dict(self):
        return {
            "_id": str(self._id),
            "user_id": self.user_id,
            "date": self.date,
            "mood_score": self.mood_score,
            "timestamp": self.timestamp.isoformat(),
        }

    @staticmethod
    def from_mongo(data):
        _id = data.get('_id')
        user_id = data.get('user_id')
        date = data.get('date')
        mood_score = data.get('mood_score')
        timestamp = data.get('timestamp')

        if timestamp and isinstance(timestamp, str):
            timestamp = datetime.datetime.fromisoformat(timestamp)

        return MoodEntry(
            _id=_id,
            user_id=user_id,
            date=date,
            mood_score=mood_score,
            timestamp=timestamp
        )

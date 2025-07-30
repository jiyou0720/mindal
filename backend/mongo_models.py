# backend/mongo_models.py
from bson.objectid import ObjectId
import json
import datetime

class MongoPostContent:
    def __init__(self, content, attachment_paths=None, _id=None):
        self._id = _id if _id else ObjectId()
        self.content = content
        self.attachment_paths = attachment_paths if attachment_paths is not None else []

    def to_dict(self):
        return {
            "_id": self._id,
            "content": self.content,
            "attachment_paths": self.attachment_paths
        }

    @staticmethod
    def from_mongo(data):
        return MongoPostContent(
            _id=data.get('_id'),
            content=data.get('content'),
            attachment_paths=data.get('attachment_paths', [])
        )

class MenuItem:
    def __init__(self, name, path, icon_class, required_roles=None, order=None, _id=None):
        self.name = name
        self.path = path
        self.icon_class = icon_class
        self.required_roles = required_roles if required_roles is not None else []
        self.order = order
        self._id = _id if _id else ObjectId()
    
    def to_dict(self):
        return {
            "_id": self._id,
            "name": self.name,
            "path": self.path,
            "icon_class": self.icon_class,
            "required_roles": self.required_roles,
            "order": self.order
        }

    @staticmethod
    def from_mongo(data):
        return MenuItem(
            _id=data.get('_id'),
            name=data.get('name'),
            path=data.get('path'),
            icon_class=data.get('icon_class'),
            required_roles=data.get('required_roles', []),
            order=data.get('order')
        )

class DiaryEntry:
    def __init__(self, user_id, title, content, date, mood_emoji_key, created_at=None, updated_at=None, _id=None):
        self._id = _id if _id else ObjectId()
        self.user_id = user_id
        self.title = title
        self.content = content
        self.date = date # YYYY-MM-DD string
        self.mood_emoji_key = mood_emoji_key
        self.created_at = created_at if created_at is not None else datetime.datetime.utcnow()
        self.updated_at = updated_at if updated_at is not None else datetime.datetime.utcnow()

    def to_dict(self):
        return {
            "_id": self._id,
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

        # Convert ISO format string to datetime object if necessary
        if isinstance(created_at, str):
            created_at = datetime.datetime.fromisoformat(created_at)
        if isinstance(updated_at, str):
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
        self.date = date
        self.mood_score = mood_score
        self.timestamp = timestamp if timestamp is not None else datetime.datetime.utcnow()

    def to_dict(self):
        return {
            "_id": self._id,
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

        if isinstance(timestamp, str):
            timestamp = datetime.datetime.fromisoformat(timestamp)

        return MoodEntry(
            _id=_id,
            user_id=user_id,
            date=date,
            mood_score=mood_score,
            timestamp=timestamp
        )

# NEW: ChatLog Model for AI Chatbot conversations
class ChatLog:
    def __init__(self, user_id, conversation_history, chat_style, created_at=None, _id=None, summary=None, test_result_id=None):
        self._id = _id if _id else ObjectId()
        self.user_id = user_id
        self.conversation_history = conversation_history if conversation_history is not None else [] # [{"role": "user/model", "text": "..."}]
        self.chat_style = chat_style # e.g., "empathy", "cbt", "solution"
        self.created_at = created_at if created_at is not None else datetime.datetime.utcnow()
        self.summary = summary # Optional summary of the conversation
        self.test_result_id = test_result_id # Optional: Link to a psychological test result

    def to_dict(self):
        return {
            "_id": self._id,
            "user_id": self.user_id,
            "conversation_history": self.conversation_history,
            "chat_style": self.chat_style,
            "created_at": self.created_at.isoformat(),
            "summary": self.summary,
            "test_result_id": self.test_result_id
        }

    @staticmethod
    def from_mongo(data):
        _id = data.get('_id')
        user_id = data.get('user_id')
        conversation_history = data.get('conversation_history', [])
        chat_style = data.get('chat_style')
        created_at = data.get('created_at')
        summary = data.get('summary')
        test_result_id = data.get('test_result_id')

        if isinstance(created_at, str):
            created_at = datetime.datetime.fromisoformat(created_at)

        return ChatLog(
            _id=_id,
            user_id=user_id,
            conversation_history=conversation_history,
            chat_style=chat_style,
            created_at=created_at,
            summary=summary,
            test_result_id=test_result_id
        )

# NEW: Inquiry Model for user inquiries
class Inquiry:
    def __init__(self, user_id, username, email, title, content, created_at=None, _id=None, status="pending", reply_content=None, replied_at=None, replied_by_user_id=None):
        self._id = _id if _id else ObjectId()
        self.user_id = user_id
        self.username = username # MariaDB의 사용자 이름 (조회 편의성)
        self.email = email       # MariaDB의 사용자 이메일 (조회 편의성)
        self.title = title
        self.content = content
        self.created_at = created_at if created_at is not None else datetime.datetime.utcnow()
        self.status = status # "pending", "replied", "closed"
        self.reply_content = reply_content # 답변 내용
        self.replied_at = replied_at # 답변 일시
        self.replied_by_user_id = replied_by_user_id # 답변한 관리자/운영자 ID

    def to_dict(self):
        return {
            "_id": self._id,
            "user_id": self.user_id,
            "username": self.username,
            "email": self.email,
            "title": self.title,
            "content": self.content,
            "created_at": self.created_at.isoformat(),
            "status": self.status,
            "reply_content": self.reply_content,
            "replied_at": self.replied_at.isoformat() if self.replied_at else None,
            "replied_by_user_id": self.replied_by_user_id
        }

    @staticmethod
    def from_mongo(data):
        _id = data.get('_id')
        user_id = data.get('user_id')
        username = data.get('username')
        email = data.get('email')
        title = data.get('title')
        content = data.get('content')
        created_at = data.get('created_at')
        status = data.get('status', 'pending')
        reply_content = data.get('reply_content')
        replied_at = data.get('replied_at')
        replied_by_user_id = data.get('replied_by_user_id')

        if isinstance(created_at, str):
            created_at = datetime.datetime.fromisoformat(created_at)
        if isinstance(replied_at, str):
            replied_at = datetime.datetime.fromisoformat(replied_at)

        return Inquiry(
            _id=_id,
            user_id=user_id,
            username=username,
            email=email,
            title=title,
            content=content,
            created_at=created_at,
            status=status,
            reply_content=reply_content,
            replied_at=replied_at,
            replied_by_user_id=replied_by_user_id
        )

# NEW: PsychTest Model for psychological tests
class PsychTest:
    def __init__(self, title, description, test_type, questions=None, created_at=None, _id=None):
        self._id = _id if _id else ObjectId()
        self.title = title # 테스트 제목 (예: MBTI 성격 유형 테스트)
        self.description = description # 테스트 설명
        self.test_type = test_type # "personality", "emotion_diagnosis"
        self.questions = questions if questions is not None else [] # PsychQuestion 객체들의 리스트 또는 참조 ID
        self.created_at = created_at if created_at is not None else datetime.datetime.utcnow()

    def to_dict(self):
        return {
            "_id": self._id,
            "title": self.title,
            "description": self.description,
            "test_type": self.test_type,
            "questions": self.questions, # 질문 객체 자체를 포함하거나, 질문 ID 리스트를 포함
            "created_at": self.created_at.isoformat(),
        }

    @staticmethod
    def from_mongo(data):
        _id = data.get('_id')
        title = data.get('title')
        description = data.get('description')
        test_type = data.get('test_type')
        questions = data.get('questions', [])
        created_at = data.get('created_at')

        if isinstance(created_at, str):
            created_at = datetime.datetime.fromisoformat(created_at)

        return PsychTest(
            _id=_id,
            title=title,
            description=description,
            test_type=test_type,
            questions=questions,
            created_at=created_at
        )

# NEW: PsychQuestion Model for individual test questions
class PsychQuestion:
    def __init__(self, test_id, question_text, options, order, _id=None):
        self._id = _id if _id else ObjectId()
        self.test_id = test_id # 어떤 테스트에 속하는 질문인지 (PsychTest의 _id 참조)
        self.question_text = question_text # 질문 내용
        self.options = options # [{ "text": "선택지1", "score": 1 }, { "text": "선택지2", "score": 2 }]
        self.order = order # 질문 순서

    def to_dict(self):
        return {
            "_id": self._id,
            "test_id": self.test_id,
            "question_text": self.question_text,
            "options": self.options,
            "order": self.order
        }

    @staticmethod
    def from_mongo(data):
        _id = data.get('_id')
        test_id = data.get('test_id')
        question_text = data.get('question_text')
        options = data.get('options', [])
        order = data.get('order')

        return PsychQuestion(
            _id=_id,
            test_id=test_id,
            question_text=question_text,
            options=options,
            order=order
        )

# NEW: PsychTestResult Model for storing user's test results
class PsychTestResult:
    def __init__(self, user_id, test_id, answers, result_summary, result_details=None, created_at=None, _id=None):
        self._id = _id if _id else ObjectId()
        self.user_id = user_id # 테스트를 수행한 사용자 ID
        self.test_id = test_id # 수행한 테스트 ID (PsychTest의 _id 참조)
        self.answers = answers # [{"question_id": "...", "selected_option_index": 0, "score": 1}]
        self.result_summary = result_summary # 결과 요약 (예: "당신은 외향적인 성격입니다.")
        self.result_details = result_details # 상세 결과 데이터 (그래프 데이터, 추가 설명 등)
        self.created_at = created_at if created_at is not None else datetime.datetime.utcnow()

    def to_dict(self):
        return {
            "_id": self._id,
            "user_id": self.user_id,
            "test_id": self.test_id,
            "answers": self.answers,
            "result_summary": self.result_summary,
            "result_details": self.result_details,
            "created_at": self.created_at.isoformat(),
        }

    @staticmethod
    def from_mongo(data):
        _id = data.get('_id')
        user_id = data.get('user_id')
        test_id = data.get('test_id')
        answers = data.get('answers', [])
        result_summary = data.get('result_summary')
        result_details = data.get('result_details')
        created_at = data.get('created_at')

        if isinstance(created_at, str):
            created_at = datetime.datetime.fromisoformat(created_at)

        return PsychTestResult(
            _id=_id,
            user_id=user_id,
            test_id=test_id,
            answers=answers,
            result_summary=result_summary,
            result_details=result_details,
            created_at=created_at
        )

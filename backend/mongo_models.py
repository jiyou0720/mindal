from bson.objectid import ObjectId
import json
import datetime
from flask import current_app # current_app을 임포트하여 로깅에 사용

# ChatHistory 모델은 이전에 제공된 대로 유지
class ChatHistory:
    # MongoDB collection name for chat history
    COLLECTION_NAME = "chat_history"

    @staticmethod
    def add_message(user_id, sender, message, chat_session_id=None):
        """
        Add a message to the chat history.
        Args:
            user_id (int): The ID of the user.
            sender (str): The sender of the message ('user' or 'ai').
            message (str): The content of the message.
            chat_session_id (str, optional): The ID of the chat session. If None, a new session ID will be generated.
        Returns:
            dict: The inserted document.
        """
        if chat_session_id is None:
            # Generate a new chat session ID for the first message in a session
            chat_session_id = ChatHistory._generate_session_id(user_id)

        chat_data = {
            "user_id": user_id,
            "chat_session_id": chat_session_id,
            "sender": sender,
            "message": message,
            "timestamp": datetime.datetime.utcnow() # Use datetime.datetime
        }
        try:
            from backend.extensions import mongo # mongo 객체는 app 컨텍스트 외부에서 임포트될 수 없으므로 함수 내에서 임포트
            result = mongo.db[ChatHistory.COLLECTION_NAME].insert_one(chat_data)
            return {**chat_data, "_id": str(result.inserted_id)} # Return inserted document with string _id
        except Exception as e:
            # current_app 로거 사용 전 앱 컨텍스트 확인
            if current_app:
                current_app.logger.error(f"Error adding chat message to MongoDB: {e}")
            else:
                print(f"Error adding chat message to MongoDB (no app context): {e}")
            raise

    @staticmethod
    def get_history(user_id, chat_session_id=None, limit=100):
        """
        Retrieve chat history for a user, optionally filtered by session.
        Args:
            user_id (int): The ID of the user.
            chat_session_id (str, optional): The ID of the chat session to retrieve.
            limit (int): The maximum number of messages to retrieve.
        Returns:
            list: A list of chat messages.
        """
        query = {"user_id": user_id}
        if chat_session_id:
            query["chat_session_id"] = chat_session_id
        
        try:
            from backend.extensions import mongo
            # Sort by timestamp in ascending order to get chronological history
            cursor = mongo.db[ChatHistory.COLLECTION_NAME].find(query).sort("timestamp", 1).limit(limit)
            return list(cursor)
        except Exception as e:
            if current_app:
                current_app.logger.error(f"Error fetching chat history from MongoDB: {e}")
            else:
                print(f"Error fetching chat history from MongoDB (no app context): {e}")
            raise

    @staticmethod
    def get_all_sessions(user_id):
        """
        Get all unique chat session IDs for a given user.
        Args:
            user_id (int): The ID of the user.
        Returns:
            list: A list of unique chat session IDs.
        """
        try:
            from backend.extensions import mongo
            return mongo.db[ChatHistory.COLLECTION_NAME].distinct("chat_session_id", {"user_id": user_id})
        except Exception as e:
            if current_app:
                current_app.logger.error(f"Error fetching chat sessions from MongoDB: {e}")
            else:
                print(f"Error fetching chat sessions from MongoDB (no app context): {e}")
            raise

    @staticmethod
    def _generate_session_id(user_id):
        """
        Generates a new chat session ID. This can be a UUID or a timestamp-based ID.
        For simplicity, let's use a timestamp for now.
        """
        # A simple timestamp-based session ID. In a real app, you might use UUID.
        return f"{user_id}_{datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"

    @staticmethod
    def delete_session(user_id, chat_session_id):
        """
        Deletes a specific chat session for a user.
        Args:
            user_id (int): The ID of the user.
            chat_session_id (str): The ID of the chat session to delete.
        Returns:
            int: The number of deleted documents.
        """
        try:
            from backend.extensions import mongo
            result = mongo.db[ChatHistory.COLLECTION_NAME].delete_many(
                {"user_id": user_id, "chat_session_id": chat_session_id}
            )
            return result.deleted_count
        except Exception as e:
            if current_app:
                current_app.logger.error(f"Error deleting chat session from MongoDB: {e}")
            else:
                print(f"Error deleting chat session from MongoDB (no app context): {e}")
            raise

# 기존의 다른 MongoDB 모델들은 그대로 유지됩니다.
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


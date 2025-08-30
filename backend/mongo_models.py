<<<<<<< HEAD
from bson.objectid import ObjectId
import json
import datetime
from flask import current_app # current_app을 임포트하여 로깅에 사용

# ChatHistory 모델은 이전에 제공된 대로 유지 (개별 메시지 저장용)
class ChatHistory:
    COLLECTION_NAME = "chat_history"

    @staticmethod
    def add_message(user_id, sender, message, chat_session_id=None):
        if chat_session_id is None:
            chat_session_id = ChatHistory._generate_session_id(user_id)

        chat_data = {
            "user_id": user_id,
            "chat_session_id": chat_session_id,
            "sender": sender,
            "message": message,
            "timestamp": datetime.datetime.utcnow()
        }
        try:
            from backend.extensions import mongo
            result = mongo.db[ChatHistory.COLLECTION_NAME].insert_one(chat_data)
            return {**chat_data, "_id": str(result.inserted_id)}
        except Exception as e:
            if current_app:
                current_app.logger.error(f"Error adding chat message to MongoDB: {e}")
            else:
                print(f"Error adding chat message to MongoDB (no app context): {e}")
            raise

    @staticmethod
    def get_history(user_id, chat_session_id=None, limit=None): # limit을 None으로 변경하여 전체 기록도 가져올 수 있게 함
        query = {"user_id": user_id}
        if chat_session_id:
            query["chat_session_id"] = chat_session_id
        
        try:
            from backend.extensions import mongo
            cursor = mongo.db[ChatHistory.COLLECTION_NAME].find(query).sort("timestamp", 1)
            if limit:
                cursor = cursor.limit(limit)
            return list(cursor)
        except Exception as e:
            if current_app:
                current_app.logger.error(f"Error fetching chat history from MongoDB: {e}")
            else:
                print(f"Error fetching chat history from MongoDB (no app context): {e}")
            raise

    @staticmethod
    def get_all_sessions(user_id):
        try:
            from backend.extensions import mongo
            # 이제 ChatSession 모델에서 세션 정보를 가져오므로 이 함수는 사용하지 않거나,
            # ChatSession에서 세션 ID만 가져오도록 변경해야 합니다.
            # 여기서는 ChatSession.get_all_sessions_metadata를 사용하도록 유도합니다.
            raise NotImplementedError("Use ChatSession.get_all_sessions_metadata instead.")
        except Exception as e:
            if current_app:
                current_app.logger.error(f"Error fetching chat sessions from MongoDB: {e}")
            else:
                print(f"Error fetching chat sessions from MongoDB (no app context): {e}")
            raise

    @staticmethod
    def _generate_session_id(user_id):
        return f"{user_id}_{datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"

    @staticmethod
    def delete_session(user_id, chat_session_id):
        # 사용자 대화 기록 삭제 시, 실제 데이터를 지우는 대신 소프트 삭제 플래그를 업데이트합니다.
        # ChatSession 모델에서 is_deleted_by_user 플래그를 업데이트하는 방식으로 변경
        # 여기서는 ChatHistory 메시지 자체는 관리자용으로 유지하므로 삭제하지 않습니다.
        # 이 메서드는 ChatSession.delete_session_metadata에서 호출될 때만 의미가 있습니다.
        # 따라서, 이 메서드는 더 이상 ChatHistory 컬렉션에서 실제 메시지를 삭제하지 않습니다.
        # 대신 ChatSession 문서의 is_deleted_by_user 플래그를 업데이트합니다.
        # 이 메서드의 호출 로직은 chat_routes.py에서 변경됩니다.
        current_app.logger.info(f"Soft deleting chat history for session {chat_session_id} by user {user_id}. Actual messages are retained for admin.")
        return 1 # 삭제된 것처럼 처리 (실제 삭제는 아니지만, 플래그 업데이트를 의미)


# NEW: ChatSession Model for storing entire chat sessions with summary
class ChatSession:
    COLLECTION_NAME = "chat_sessions"

    def __init__(self, user_id, chat_session_id, chat_style, summary, created_at=None, updated_at=None, _id=None, feedback=None, is_deleted_by_user=False):
        self._id = _id if _id else ObjectId()
        self.user_id = user_id
        self.chat_session_id = chat_session_id # Use the same session ID as ChatHistory
        self.chat_style = chat_style # e.g., "empathy", "cbt", "solution"
        self.summary = summary # AI generated summary of the conversation
        self.created_at = created_at if created_at is not None else datetime.datetime.utcnow()
        self.updated_at = updated_at if updated_at is not None else datetime.datetime.utcnow()
        self.feedback = feedback # {"rating": 5, "comment": "...", "submitted_at": "..."}
        self.is_deleted_by_user = is_deleted_by_user # NEW: 사용자가 삭제했는지 여부 (소프트 삭제)

    def to_dict(self):
        return {
            "_id": str(self._id), # Convert ObjectId to string
            "user_id": self.user_id,
            "chat_session_id": self.chat_session_id,
            "chat_style": self.chat_style,
            "summary": self.summary,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "feedback": self.feedback,
            "is_deleted_by_user": self.is_deleted_by_user # NEW
        }

    @staticmethod
    def from_mongo(data):
        _id = data.get('_id')
        user_id = data.get('user_id')
        chat_session_id = data.get('chat_session_id')
        chat_style = data.get('chat_style')
        summary = data.get('summary')
        created_at = data.get('created_at')
        updated_at = data.get('updated_at')
        feedback = data.get('feedback')
        is_deleted_by_user = data.get('is_deleted_by_user', False) # NEW: 기본값 False

        # Convert ISO format string to datetime object if necessary
        if isinstance(created_at, str):
            created_at = datetime.datetime.fromisoformat(created_at)
        if isinstance(updated_at, str):
            updated_at = datetime.datetime.fromisoformat(updated_at)
        
        return ChatSession(
            _id=_id,
            user_id=user_id,
            chat_session_id=chat_session_id,
            chat_style=chat_style,
            summary=summary,
            created_at=created_at,
            updated_at=updated_at,
            feedback=feedback,
            is_deleted_by_user=is_deleted_by_user # NEW
        )

    @staticmethod
    def create_session(user_id, chat_session_id, chat_style="default", summary="No summary yet"):
        from backend.extensions import mongo
        session_data = ChatSession(
            user_id=user_id,
            chat_session_id=chat_session_id,
            chat_style=chat_style,
            summary=summary
        )
        try:
            result = mongo.db[ChatSession.COLLECTION_NAME].insert_one(session_data.to_dict())
            session_data._id = result.inserted_id # Update ObjectId after insert
            return session_data
        except Exception as e:
            if current_app:
                current_app.logger.error(f"Error creating chat session in MongoDB: {e}")
            else:
                print(f"Error creating chat session in MongoDB (no app context): {e}")
            raise

    @staticmethod
    def update_session_summary(user_id, chat_session_id, summary):
        from backend.extensions import mongo
        try:
            result = mongo.db[ChatSession.COLLECTION_NAME].update_one(
                {"user_id": user_id, "chat_session_id": chat_session_id},
                {"$set": {"summary": summary, "updated_at": datetime.datetime.utcnow()}}
            )
            return result.modified_count > 0
        except Exception as e:
            if current_app:
                current_app.logger.error(f"Error updating chat session summary in MongoDB: {e}")
            else:
                print(f"Error updating chat session summary in MongoDB (no app context): {e}")
            raise

    @staticmethod
    def update_session_feedback(user_id, chat_session_id, rating, comment):
        from backend.extensions import mongo
        feedback_data = {
            "rating": rating,
            "comment": comment,
            "submitted_at": datetime.datetime.utcnow().isoformat()
        }
        try:
            result = mongo.db[ChatSession.COLLECTION_NAME].update_one(
                {"user_id": user_id, "chat_session_id": chat_session_id},
                {"$set": {"feedback": feedback_data, "updated_at": datetime.datetime.utcnow()}}
            )
            return result.modified_count > 0
        except Exception as e:
            if current_app:
                current_app.logger.error(f"Error updating chat session feedback in MongoDB: {e}")
            else:
                print(f"Error updating chat session feedback in MongoDB (no app context): {e}")
            raise

    @staticmethod
    def get_session_metadata(user_id, chat_session_id):
        from backend.extensions import mongo
        try:
            doc = mongo.db[ChatSession.COLLECTION_NAME].find_one(
                {"user_id": user_id, "chat_session_id": chat_session_id}
            )
            return ChatSession.from_mongo(doc) if doc else None
        except Exception as e:
            if current_app:
                current_app.logger.error(f"Error fetching chat session metadata from MongoDB: {e}")
            else:
                print(f"Error fetching chat session metadata from MongoDB (no app context): {e}")
            raise

    @staticmethod
    def get_all_sessions_metadata(user_id, include_deleted=False): # NEW: include_deleted 인자 추가
        from backend.extensions import mongo
        try:
            query = {"user_id": user_id}
            if not include_deleted: # include_deleted가 False일 경우, 삭제되지 않은 세션만 조회
                query["is_deleted_by_user"] = False
            
            cursor = mongo.db[ChatSession.COLLECTION_NAME].find(query).sort("created_at", -1)
            return [ChatSession.from_mongo(doc) for doc in cursor]
        except Exception as e:
            if current_app:
                current_app.logger.error(f"Error fetching all chat sessions metadata from MongoDB: {e}")
            else:
                print(f"Error fetching all chat sessions metadata from MongoDB (no app context): {e}")
            raise

    @staticmethod
    def delete_session_metadata(user_id, chat_session_id):
        from backend.extensions import mongo
        try:
            # 실제 삭제 대신 is_deleted_by_user 플래그를 True로 업데이트 (소프트 삭제)
            result = mongo.db[ChatSession.COLLECTION_NAME].update_one(
                {"user_id": user_id, "chat_session_id": chat_session_id},
                {"$set": {"is_deleted_by_user": True, "updated_at": datetime.datetime.utcnow()}}
            )
            return result.modified_count > 0
        except Exception as e:
            if current_app:
                current_app.logger.error(f"Error soft deleting chat session metadata from MongoDB: {e}")
            else:
                print(f"Error soft deleting chat session metadata from MongoDB (no app context): {e}")
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
=======
from bson.objectid import ObjectId
import json
import datetime
from flask import current_app # current_app을 임포트하여 로깅에 사용
from backend.extensions import mongo # mongo 임포트

# ChatHistory 모델은 이전에 제공된 대로 유지 (개별 메시지 저장용)
class ChatHistory:
    COLLECTION_NAME = "chat_history"

    @staticmethod
    def add_message(user_id, sender, message, chat_session_id=None):
        if chat_session_id is None:
            chat_session_id = ChatHistory._generate_session_id(user_id)

        chat_data = {
            "user_id": user_id,
            "chat_session_id": chat_session_id,
            "sender": sender,
            "message": message,
            "timestamp": datetime.datetime.utcnow()
        }
        try:
            result = mongo.db[ChatHistory.COLLECTION_NAME].insert_one(chat_data)
            return {**chat_data, "_id": str(result.inserted_id)}
        except Exception as e:
            if current_app:
                current_app.logger.error(f"Error adding chat message to MongoDB: {e}")
            else:
                print(f"Error adding chat message to MongoDB (no app context): {e}")
            raise

    @staticmethod
    def get_history(user_id, chat_session_id=None, limit=None): # limit을 None으로 변경하여 전체 기록도 가져올 수 있게 함
        query = {"user_id": user_id}
        if chat_session_id:
            query["chat_session_id"] = chat_session_id
        
        try:
            cursor = mongo.db[ChatHistory.COLLECTION_NAME].find(query).sort("timestamp", 1)
            if limit:
                cursor = cursor.limit(limit)
            return list(cursor)
        except Exception as e:
            if current_app:
                current_app.logger.error(f"Error fetching chat history from MongoDB: {e}")
            else:
                print(f"Error fetching chat history from MongoDB (no app context): {e}")
            raise

    @staticmethod
    def get_all_sessions(user_id):
        try:
            # 이제 ChatSession 모델에서 세션 정보를 가져오므로 이 함수는 사용하지 않거나,
            # ChatSession에서 세션 ID만 가져오도록 변경해야 합니다.
            # 여기서는 ChatSession.get_all_sessions_metadata를 사용하도록 유도합니다.
            raise NotImplementedError("Use ChatSession.get_all_sessions_metadata instead.")
        except Exception as e:
            if current_app:
                current_app.logger.error(f"Error fetching chat sessions from MongoDB: {e}")
            else:
                print(f"Error fetching chat sessions from MongoDB (no app context): {e}")
            raise

    @staticmethod
    def _generate_session_id(user_id):
        return f"{user_id}_{datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"

    @staticmethod
    def delete_session(user_id, chat_session_id):
        try:
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

# NEW: ChatSession Model for storing entire chat sessions with summary
class ChatSession:
    COLLECTION_NAME = "chat_sessions"

    def __init__(self, user_id, chat_session_id, chat_style, summary, created_at=None, updated_at=None, _id=None, feedback=None):
        self._id = _id if _id else ObjectId()
        self.user_id = user_id
        self.chat_session_id = chat_session_id # Use the same session ID as ChatHistory
        self.chat_style = chat_style # e.g., "empathy", "cbt", "solution"
        self.summary = summary # AI generated summary of the conversation
        self.created_at = created_at if created_at is not None else datetime.datetime.utcnow()
        self.updated_at = updated_at if updated_at is not None else datetime.datetime.utcnow()
        self.feedback = feedback # {"rating": 5, "comment": "..."}

    def to_dict(self):
        return {
            "_id": str(self._id), # Convert ObjectId to string
            "user_id": self.user_id,
            "chat_session_id": self.chat_session_id,
            "chat_style": self.chat_style,
            "summary": self.summary,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "feedback": self.feedback
        }

    @staticmethod
    def from_mongo(data):
        _id = data.get('_id')
        user_id = data.get('user_id')
        chat_session_id = data.get('chat_session_id')
        chat_style = data.get('chat_style')
        summary = data.get('summary')
        created_at = data.get('created_at')
        updated_at = data.get('updated_at')
        feedback = data.get('feedback')

        # Convert ISO format string to datetime object if necessary
        if isinstance(created_at, str):
            created_at = datetime.datetime.fromisoformat(created_at)
        if isinstance(updated_at, str):
            updated_at = datetime.datetime.fromisoformat(updated_at)
        
        return ChatSession(
            _id=_id,
            user_id=user_id,
            chat_session_id=chat_session_id,
            chat_style=chat_style,
            summary=summary,
            created_at=created_at,
            updated_at=updated_at,
            feedback=feedback
        )

    @staticmethod
    def create_session(user_id, chat_session_id, chat_style="default", summary="No summary yet"):
        session_data = ChatSession(
            user_id=user_id,
            chat_session_id=chat_session_id,
            chat_style=chat_style,
            summary=summary
        )
        try:
            result = mongo.db[ChatSession.COLLECTION_NAME].insert_one(session_data.to_dict())
            session_data._id = result.inserted_id # Update ObjectId after insert
            return session_data
        except Exception as e:
            if current_app:
                current_app.logger.error(f"Error creating chat session in MongoDB: {e}")
            else:
                print(f"Error creating chat session in MongoDB (no app context): {e}")
            raise

    @staticmethod
    def update_session_summary(user_id, chat_session_id, summary):
        try:
            result = mongo.db[ChatSession.COLLECTION_NAME].update_one(
                {"user_id": user_id, "chat_session_id": chat_session_id},
                {"$set": {"summary": summary, "updated_at": datetime.datetime.utcnow()}}
            )
            return result.modified_count > 0
        except Exception as e:
            if current_app:
                current_app.logger.error(f"Error updating chat session summary in MongoDB: {e}")
            else:
                print(f"Error updating chat session summary in MongoDB (no app context): {e}")
            raise

    @staticmethod
    def update_session_feedback(user_id, chat_session_id, rating, comment):
        feedback_data = {
            "rating": rating,
            "comment": comment,
            "submitted_at": datetime.datetime.utcnow().isoformat()
        }
        try:
            result = mongo.db[ChatSession.COLLECTION_NAME].update_one(
                {"user_id": user_id, "chat_session_id": chat_session_id},
                {"$set": {"feedback": feedback_data, "updated_at": datetime.datetime.utcnow()}}
            )
            return result.modified_count > 0
        except Exception as e:
            if current_app:
                current_app.logger.error(f"Error updating chat session feedback in MongoDB: {e}")
            else:
                print(f"Error updating chat session feedback in MongoDB (no app context): {e}")
            raise

    @staticmethod
    def get_session_metadata(user_id, chat_session_id):
        try:
            doc = mongo.db[ChatSession.COLLECTION_NAME].find_one(
                {"user_id": user_id, "chat_session_id": chat_session_id}
            )
            return ChatSession.from_mongo(doc) if doc else None
        except Exception as e:
            if current_app:
                current_app.logger.error(f"Error fetching chat session metadata from MongoDB: {e}")
            else:
                print(f"Error fetching chat session metadata from MongoDB (no app context): {e}")
            raise

    @staticmethod
    def get_all_sessions_metadata(user_id):
        try:
            cursor = mongo.db[ChatSession.COLLECTION_NAME].find({"user_id": user_id}).sort("created_at", -1)
            return [ChatSession.from_mongo(doc) for doc in cursor]
        except Exception as e:
            if current_app:
                current_app.logger.error(f"Error fetching all chat sessions metadata from MongoDB: {e}")
            else:
                print(f"Error fetching all chat sessions metadata from MongoDB (no app context): {e}")
            raise

    @staticmethod
    def delete_session_metadata(user_id, chat_session_id):
        try:
            result = mongo.db[ChatSession.COLLECTION_NAME].delete_one(
                {"user_id": user_id, "chat_session_id": chat_session_id}
            )
            return result.deleted_count > 0
        except Exception as e:
            if current_app:
                current_app.logger.error(f"Error deleting chat session metadata from MongoDB: {e}")
            else:
                print(f"Error deleting chat session metadata from MongoDB (no app context): {e}")
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

# NEW: ChatbotFeedback Model for storing user feedback on chatbot sessions
class ChatbotFeedback:
    COLLECTION_NAME = 'chatbot_feedback'

    @staticmethod
    def create(user_id, chat_session_id, rating, comment, timestamp=None):
        if timestamp is None:
            timestamp = datetime.datetime.utcnow()
        feedback_data = {
            'user_id': user_id,
            'chat_session_id': chat_session_id,
            'rating': rating,
            'comment': comment,
            'timestamp': timestamp,
        }
        # MongoDB에 피드백 저장
        result = mongo.db[ChatbotFeedback.COLLECTION_NAME].insert_one(feedback_data)
        return str(result.inserted_id)

    @staticmethod
    def get_by_id(feedback_id):
        return mongo.db[ChatbotFeedback.COLLECTION_NAME].find_one({'_id': ObjectId(feedback_id)})

    @staticmethod
    def get_all():
        # 모든 피드백을 최신순으로 정렬하여 반환
        return list(mongo.db[ChatbotFeedback.COLLECTION_NAME].find().sort('timestamp', -1))

    @staticmethod
    def get_feedback_by_user(user_id):
        # 특정 user_id에 해당하는 모든 피드백을 최신순으로 정렬하여 반환
        return list(mongo.db[ChatbotFeedback.COLLECTION_NAME].find({'user_id': user_id}).sort('timestamp', -1))

    @staticmethod
    def update(feedback_id, new_rating=None, new_comment=None):
        update_fields = {}
        if new_rating is not None:
            update_fields['rating'] = new_rating
        if new_comment is not None:
            update_fields['comment'] = new_comment

        if update_fields:
            result = mongo.db[ChatbotFeedback.COLLECTION_NAME].update_one(
                {'_id': ObjectId(feedback_id)},
                {'$set': update_fields}
            )
            return result.modified_count > 0
        return False

    @staticmethod
    def delete(feedback_id):
        result = mongo.db[ChatbotFeedback.COLLECTION_NAME].delete_one({'_id': ObjectId(feedback_id)})
        return result.deleted_count > 0

    @staticmethod
    def delete_by_chat_session_id(chat_session_id):
        # 특정 chat_session_id에 연결된 피드백 삭제
        result = mongo.db[ChatbotFeedback.COLLECTION_NAME].delete_many({'chat_session_id': chat_session_id})
        return result.deleted_count > 0
>>>>>>> 32e57f7623365b93a09d34dc9cad501cc18c11af

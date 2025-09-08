from bson.objectid import ObjectId
import json
import datetime
from flask import current_app
from backend.extensions import mongo

def get_mongo_db():
    """안정적으로 MongoDB 데이터베이스 객체를 가져옵니다."""
    db_name = current_app.config.get("MONGO_DBNAME", "mindbridge_db")
    return mongo.cx[db_name]

# ChatHistory 모델
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
            db = get_mongo_db()
            result = db[ChatHistory.COLLECTION_NAME].insert_one(chat_data)
            return {**chat_data, "_id": str(result.inserted_id)}
        except Exception as e:
            current_app.logger.error(f"Error adding chat message to MongoDB: {e}")
            raise

    @staticmethod
    def get_history(user_id, chat_session_id=None, limit=None):
        query = {"user_id": user_id}
        if chat_session_id:
            query["chat_session_id"] = chat_session_id
        
        try:
            db = get_mongo_db()
            cursor = db[ChatHistory.COLLECTION_NAME].find(query).sort("timestamp", 1)
            if limit:
                cursor = cursor.limit(limit)
            return list(cursor)
        except Exception as e:
            current_app.logger.error(f"Error fetching chat history from MongoDB: {e}")
            raise

    @staticmethod
    def get_all_sessions(user_id):
        raise NotImplementedError("Use ChatSession.get_all_sessions_metadata instead.")

    @staticmethod
    def _generate_session_id(user_id):
        return f"{user_id}_{datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S%f')}"

    @staticmethod
    def delete_session(user_id, chat_session_id):
        try:
            db = get_mongo_db()
            result = db[ChatHistory.COLLECTION_NAME].delete_many(
                {"user_id": user_id, "chat_session_id": chat_session_id}
            )
            return result.deleted_count
        except Exception as e:
            current_app.logger.error(f"Error deleting chat session from MongoDB: {e}")
            raise

# ChatSession 모델
class ChatSession:
    COLLECTION_NAME = "chat_sessions"

    def __init__(self, user_id, chat_session_id, chat_style, summary, created_at=None, updated_at=None, _id=None, feedback=None, is_hidden=False):
        self._id = _id if _id else ObjectId()
        self.user_id = user_id
        self.chat_session_id = chat_session_id
        self.chat_style = chat_style
        self.summary = summary
        self.created_at = created_at if created_at is not None else datetime.datetime.utcnow()
        self.updated_at = updated_at if updated_at is not None else datetime.datetime.utcnow()
        self.feedback = feedback
        self.is_hidden = is_hidden

    def to_dict(self):
        return {
            "_id": self._id,
            "user_id": self.user_id,
            "chat_session_id": self.chat_session_id,
            "chat_style": self.chat_style,
            "summary": self.summary,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "feedback": self.feedback,
            "is_hidden": self.is_hidden
        }

    @staticmethod
    def from_mongo(data):
        return ChatSession(**data)

    @staticmethod
    def create_session(user_id, chat_session_id, chat_style="default", summary="No summary yet"):
        session_data = ChatSession(
            user_id=user_id,
            chat_session_id=chat_session_id,
            chat_style=chat_style,
            summary=summary,
            is_hidden=False
        )
        try:
            db = get_mongo_db()
            session_dict = session_data.to_dict()
            del session_dict['_id'] 
            result = db[ChatSession.COLLECTION_NAME].insert_one(session_dict)
            session_data._id = result.inserted_id
            return session_data
        except Exception as e:
            current_app.logger.error(f"Error creating chat session in MongoDB: {e}")
            raise

    @staticmethod
    def update_session_summary(user_id, chat_session_id, summary):
        try:
            db = get_mongo_db()
            result = db[ChatSession.COLLECTION_NAME].update_one(
                {"user_id": user_id, "chat_session_id": chat_session_id},
                {"$set": {"summary": summary, "updated_at": datetime.datetime.utcnow()}}
            )
            return result.modified_count > 0
        except Exception as e:
            current_app.logger.error(f"Error updating chat session summary in MongoDB: {e}")
            raise

    @staticmethod
    def hide_session_for_user(user_id, chat_session_id):
        """사용자에게 세션을 숨김 처리합니다 (소프트 삭제)."""
        try:
            db = get_mongo_db()
            result = db[ChatSession.COLLECTION_NAME].update_one(
                {"user_id": user_id, "chat_session_id": chat_session_id},
                {"$set": {"is_hidden": True, "updated_at": datetime.datetime.utcnow()}}
            )
            return result.modified_count > 0
        except Exception as e:
            current_app.logger.error(f"Error hiding chat session in MongoDB: {e}")
            raise

    @staticmethod
    def get_session_by_id(user_id, chat_session_id):
        """숨겨지지 않은 특정 세션 정보를 가져옵니다."""
        try:
            db = get_mongo_db()
            doc = db[ChatSession.COLLECTION_NAME].find_one({
                "user_id": user_id,
                "chat_session_id": chat_session_id,
                "is_hidden": {"$ne": True}
            })
            return ChatSession.from_mongo(doc) if doc else None
        except Exception as e:
            current_app.logger.error(f"Error fetching single chat session metadata from MongoDB: {e}")
            raise

    @staticmethod
    def get_all_sessions_metadata(user_id):
        """사용자에게 보여줄 숨겨지지 않은 모든 세션 메타데이터를 가져옵니다."""
        try:
            db = get_mongo_db()
            cursor = db[ChatSession.COLLECTION_NAME].find({
                "user_id": user_id,
                "is_hidden": {"$ne": True}
            }).sort("created_at", -1)
            return [ChatSession.from_mongo(doc) for doc in cursor]
        except Exception as e:
            current_app.logger.error(f"Error fetching all chat sessions metadata from MongoDB: {e}")
            raise

    @staticmethod
    def delete_session_metadata(user_id, chat_session_id):
        """데이터베이스에서 세션 메타데이터를 완전히 삭제합니다 (하드 삭제)."""
        try:
            db = get_mongo_db()
            result = db[ChatSession.COLLECTION_NAME].delete_one(
                {"user_id": user_id, "chat_session_id": chat_session_id}
            )
            return result.deleted_count > 0
        except Exception as e:
            current_app.logger.error(f"Error deleting chat session metadata from MongoDB: {e}")
            raise

# MongoPostContent 모델
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
        return MongoPostContent(**data)

# MenuItem 모델
class MenuItem:
    def __init__(self, name, path, icon_class, required_roles=None, order=None, _id=None):
        self.name = name
        self.path = path
        self.icon_class = icon_class
        self.required_roles = required_roles if required_roles is not None else []
        self.order = order
        self._id = _id if _id else ObjectId()
    
    def to_dict(self):
        return self.__dict__

    @staticmethod
    def from_mongo(data):
        return MenuItem(**data)

# DiaryEntry 모델
class DiaryEntry:
    def __init__(self, user_id, title, content, date, mood_emoji_key, created_at=None, updated_at=None, _id=None):
        self._id = _id if _id else ObjectId()
        self.user_id = user_id
        self.title = title
        self.content = content
        self.date = date
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
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
    
    @staticmethod
    def from_mongo(data):
        return DiaryEntry(**data)

# MoodEntry 모델
class MoodEntry:
    def __init__(self, user_id, date, mood_score, timestamp=None, _id=None):
        self._id = _id if _id else ObjectId()
        self.user_id = user_id
        self.date = date
        self.mood_score = mood_score
        self.timestamp = timestamp if timestamp is not None else datetime.datetime.utcnow()

    def to_dict(self):
        return self.__dict__

    @staticmethod
    def from_mongo(data):
        return MoodEntry(**data)

# Inquiry 모델
class Inquiry:
    def __init__(self, user_id, username, email, title, content, created_at=None, _id=None, status="pending", reply_content=None, replied_at=None, replied_by_user_id=None):
        self._id = _id if _id else ObjectId()
        self.user_id = user_id
        self.username = username
        self.email = email
        self.title = title
        self.content = content
        self.created_at = created_at if created_at is not None else datetime.datetime.utcnow()
        self.status = status
        self.reply_content = reply_content
        self.replied_at = replied_at
        self.replied_by_user_id = replied_by_user_id

    def to_dict(self):
        return self.__dict__

    @staticmethod
    def from_mongo(data):
        return Inquiry(**data)

# PsychTest 모델
class PsychTest:
    def __init__(self, title, description, test_type, questions=None, created_at=None, _id=None):
        self._id = _id if _id else ObjectId()
        self.title = title
        self.description = description
        self.test_type = test_type
        self.questions = questions if questions is not None else []
        self.created_at = created_at if created_at is not None else datetime.datetime.utcnow()

    def to_dict(self):
        return self.__dict__
    
    @staticmethod
    def from_mongo(data):
        return PsychTest(**data)

# PsychQuestion 모델
class PsychQuestion:
    def __init__(self, test_id, question_text, options, order, _id=None):
        self._id = _id if _id else ObjectId()
        self.test_id = test_id
        self.question_text = question_text
        self.options = options
        self.order = order

    def to_dict(self):
        return self.__dict__

    @staticmethod
    def from_mongo(data):
        return PsychQuestion(**data)

# PsychTestResult 모델
class PsychTestResult:
    def __init__(self, user_id, test_id, answers, result_summary, result_details=None, created_at=None, _id=None):
        self._id = _id if _id else ObjectId()
        self.user_id = user_id
        self.test_id = test_id
        self.answers = answers
        self.result_summary = result_summary
        self.result_details = result_details
        self.created_at = created_at if created_at is not None else datetime.datetime.utcnow()

    def to_dict(self):
        return self.__dict__

    @staticmethod
    def from_mongo(data):
        return PsychTestResult(**data)

# ChatbotFeedback 모델
class ChatbotFeedback:
    # ✅ 컬렉션 이름을 'chat_feedback'으로 변경하여 혼란을 줄였습니다.
    COLLECTION_NAME = 'chat_feedback'

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
        db = get_mongo_db()
        result = db[ChatbotFeedback.COLLECTION_NAME].insert_one(feedback_data)
        return str(result.inserted_id)

    @staticmethod
    def get_by_id(feedback_id):
        db = get_mongo_db()
        return db[ChatbotFeedback.COLLECTION_NAME].find_one({'_id': ObjectId(feedback_id)})

    @staticmethod
    def get_all():
        db = get_mongo_db()
        return list(db[ChatbotFeedback.COLLECTION_NAME].find().sort('timestamp', -1))

    @staticmethod
    def get_feedback_by_user(user_id):
        db = get_mongo_db()
        return list(db[ChatbotFeedback.COLLECTION_NAME].find({'user_id': user_id}).sort('timestamp', -1))

    @staticmethod
    def update(feedback_id, new_rating=None, new_comment=None):
        update_fields = {}
        if new_rating is not None:
            update_fields['rating'] = new_rating
        if new_comment is not None:
            update_fields['comment'] = new_comment

        if update_fields:
            db = get_mongo_db()
            result = db[ChatbotFeedback.COLLECTION_NAME].update_one(
                {'_id': ObjectId(feedback_id)},
                {'$set': update_fields}
            )
            return result.modified_count > 0
        return False

    @staticmethod
    def delete(feedback_id):
        db = get_mongo_db()
        result = db[ChatbotFeedback.COLLECTION_NAME].delete_one({'_id': ObjectId(feedback_id)})
        return result.deleted_count > 0

    @staticmethod
    def delete_by_chat_session_id(chat_session_id):
        db = get_mongo_db()
        result = db[ChatbotFeedback.COLLECTION_NAME].delete_many({'chat_session_id': chat_session_id})
        return result.deleted_count > 0


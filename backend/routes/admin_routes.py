# backend/routes/admin_routes.py
from flask import Blueprint, request, jsonify, current_app, g # g 임포트가 필요합니다.
from auth import admin_required # 새로 생성한 admin_required 데코레이터
from maria_models import User, Post, Comment
from mongo_models import MongoPostContent, DiaryEntry, MoodEntry
from extensions import db # MariaDB db 인스턴스 (수정됨)
from flask_pymongo import PyMongo # MongoDB 인스턴스
from bson.objectid import ObjectId

admin_bp = Blueprint('admin_api', __name__)

@admin_bp.record_once
def record(state):
    # MongoDB 인스턴스를 애플리케이션 컨텍스트에 등록 (다른 라우트와 동일)
    state.app.config['MONGO_DB'] = PyMongo(state.app).db

# MongoDB 컬렉션 참조 함수
def get_posts_content_collection():
    return current_app.config['MONGO_DB'].post_contents

def get_diary_collection():
    return current_app.config['MONGO_DB'].diaries

def get_mood_collection():
    return current_app.config['MONGO_DB'].mood_entries

# --- 관리자 관련 API 엔드포인트 ---

# 1. 모든 사용자 조회 (관리자 전용)
@admin_bp.route('/users', methods=['GET'])
@admin_required
def get_all_users():
    users = User.query.all()
    users_data = [user.to_dict() for user in users]
    return jsonify({'message': 'All users retrieved successfully', 'users': users_data}), 200

# 2. 특정 사용자 삭제 (관리자 전용)
@admin_bp.route('/users/<int:user_id>', methods=['DELETE'])
@admin_required
def admin_delete_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'message': 'User not found'}), 404

    # 관리자 계정은 삭제할 수 없도록 방어 로직 추가
    if user.is_admin:
        return jsonify({'message': 'Cannot delete an admin user'}), 403

    # 사용자와 관련된 모든 게시글, 댓글, 일기, 감정 카드 삭제 (MongoDB 포함)
    # 1. 게시글 및 MongoDB 내용 삭제
    posts_by_user = Post.query.filter_by(author_id=user_id).all()
    for post in posts_by_user:
        try:
            get_posts_content_collection().delete_one({'_id': ObjectId(post.mongodb_content_id)})
        except Exception as e:
            print(f"Error deleting MongoDB post content for user {user_id}: {e}")
        db.session.delete(post)

    # 2. 댓글 삭제
    comments_by_user = Comment.query.filter_by(author_id=user_id).all()
    for comment in comments_by_user:
        db.session.delete(comment)

    # 3. 일기 삭제 (MongoDB)
    get_diary_collection().delete_many({'user_id': user_id})

    # 4. 감정 카드 삭제 (MongoDB)
    get_mood_collection().delete_many({'user_id': user_id})

    # MariaDB에서 사용자 삭제
    db.session.delete(user)
    db.session.commit()

    return jsonify({'message': 'User and all associated data deleted successfully by admin!'}), 200

# 3. 모든 게시글 조회 (관리자 전용)
@admin_bp.route('/posts', methods=['GET'])
@admin_required
def admin_get_all_posts():
    posts = Post.query.all()
    posts_data = []
    for post in posts:
        post_dict = post.to_dict()
        # MongoDB에서 게시글 내용 가져오기
        mongo_content_data = get_posts_content_collection().find_one({'_id': ObjectId(post.mongodb_content_id)})
        if mongo_content_data:
            post_dict['content'] = MongoPostContent.from_mongo(mongo_content_data).content
        else:
            post_dict['content'] = "Content not found" # MongoDB에서 내용을 찾지 못한 경우
        posts_data.append(post_dict)
    return jsonify({'message': 'All posts retrieved successfully', 'posts': posts_data}), 200

# 4. 특정 게시글 삭제 (관리자 전용)
@admin_bp.route('/posts/<int:post_id>', methods=['DELETE'])
@admin_required
def admin_delete_post(post_id):
    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({'message': 'Post not found'}), 404

    # MongoDB에서 게시글 내용 삭제
    try:
        mongo_result = get_posts_content_collection().delete_one({'_id': ObjectId(post.mongodb_content_id)})
        if mongo_result.deleted_count == 0:
            print(f"Warning: MongoDB content for post {post_id} not found.")
    except Exception as e:
        print(f"Error deleting MongoDB content for post {post_id}: {e}")

    # MariaDB에서 게시글과 관련된 댓글 삭제 (ondelete='CASCADE'가 설정되어 있다면 불필요할 수 있으나, 명시적으로 삭제)
    comments_on_post = Comment.query.filter_by(post_id=post_id).all()
    for comment in comments_on_post:
        db.session.delete(comment)

    # MariaDB에서 게시글 삭제
    db.session.delete(post)
    db.session.commit()

    return jsonify({'message': 'Post and associated comments/content deleted successfully by admin!'}), 200

# 5. 모든 댓글 조회 (관리자 전용)
@admin_bp.route('/comments', methods=['GET'])
@admin_required
def admin_get_all_comments():
    comments = Comment.query.all()
    comments_data = [comment.to_dict() for comment in comments]
    return jsonify({'message': 'All comments retrieved successfully', 'comments': comments_data}), 200

# 6. 특정 댓글 삭제 (관리자 전용)
@admin_bp.route('/comments/<int:comment_id>', methods=['DELETE'])
@admin_required
def admin_delete_comment(comment_id):
    comment = db.session.get(Comment, comment_id)
    if not comment:
        return jsonify({'message': 'Comment not found'}), 404

    db.session.delete(comment)
    db.session.commit()
    return jsonify({'message': 'Comment deleted successfully by admin!'}), 200

# 7. 특정 사용자의 모든 일기 조회 (관리자 전용)
@admin_bp.route('/users/<int:user_id>/diaries', methods=['GET'])
@admin_required
def admin_get_user_diaries(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'message': 'User not found'}), 404

    diaries_data = get_diary_collection().find({'user_id': user_id}).sort('created_at', -1)
    diaries = [DiaryEntry.from_mongo(entry).to_dict() for entry in diaries_data]
    return jsonify({'message': f'Diaries for user {user.username} retrieved successfully', 'diaries': diaries}), 200

# 8. 모든 일기 조회 (관리자 전용)
@admin_bp.route('/diaries', methods=['GET'])
@admin_required
def admin_get_all_diaries():
    diaries_data = get_diary_collection().find({}).sort('created_at', -1)
    diaries = [DiaryEntry.from_mongo(entry).to_dict() for entry in diaries_data]
    return jsonify({'message': 'All diaries retrieved successfully', 'diaries': diaries}), 200

# 9. 특정 일기 삭제 (관리자 전용)
@admin_bp.route('/diaries/<diary_id>', methods=['DELETE'])
@admin_required
def admin_delete_diary(diary_id):
    try:
        diary_obj_id = ObjectId(diary_id)
    except Exception:
        return jsonify({'message': 'Invalid Diary ID'}), 400

    result = get_diary_collection().delete_one({'_id': diary_obj_id})
    if result.deleted_count == 0:
        return jsonify({'message': 'Diary not found'}), 404
    return jsonify({'message': 'Diary deleted successfully by admin!'}), 200

# 10. 모든 감정 카드 조회 (관리자 전용)
@admin_bp.route('/moods', methods=['GET'])
@admin_required
def admin_get_all_moods():
    moods_data = get_mood_collection().find({}).sort('created_at', -1)
    moods = [MoodEntry.from_mongo(entry).to_dict() for entry in moods_data]
    return jsonify({'message': 'All mood entries retrieved successfully', 'mood_entries': moods}), 200

# 11. 특정 감정 카드 삭제 (관리자 전용)
@admin_bp.route('/moods/<mood_id>', methods=['DELETE'])
@admin_required
def admin_delete_mood(mood_id):
    try:
        mood_obj_id = ObjectId(mood_id)
    except Exception:
        return jsonify({'message': 'Invalid Mood ID'}), 400

    result = get_mood_collection().delete_one({'_id': mood_obj_id})
    if result.deleted_count == 0:
        return jsonify({'message': 'Mood entry not found'}), 404
    return jsonify({'message': 'Mood entry deleted successfully by admin!'}), 200
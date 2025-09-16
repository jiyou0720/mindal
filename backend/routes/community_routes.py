import os
from flask import Blueprint, request, jsonify, g, current_app
from backend.extensions import db, mongo
from backend.maria_models import Post, Comment, User, PostLike # PostLike 임포트 확인
from backend.routes.auth_routes import token_required
from bson.objectid import ObjectId
from werkzeug.utils import secure_filename
import datetime
import uuid
import jwt
from sqlalchemy.orm import joinedload
from sqlalchemy import func


community_bp = Blueprint('community_api', __name__)

# --- Helper to get MongoDB ---
def _get_mongo_db():
    """Returns the MongoDB database object."""
    db_name = current_app.config.get("MONGO_DBNAME", "mindbridge_db")
    return mongo.cx[db_name]

# --- 게시글 관련 API ---

# 게시글 목록 조회
@community_bp.route('/posts', methods=['GET'])
def get_posts():
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 25, type=int)
        search_query = request.args.get('search_query', '', type=str)
        category_filter = request.args.get('category_filter', '', type=str)

        query = db.session.query(
            Post, 
            func.count(db.distinct(PostLike.user_id)).label('like_count'), 
            func.count(db.distinct(Comment.id)).label('comment_count') 
        ).outerjoin(PostLike, Post.id == PostLike.post_id)\
         .outerjoin(Comment, Post.id == Comment.post_id)\
         .group_by(Post.id) 

        if search_query:
            query = query.filter(Post.title.like(f'%{search_query}%'))

        if category_filter:
            query = query.filter(Post.category == category_filter)

        query = query.order_by(Post.is_notice.desc(), Post.created_at.desc())

        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        posts_paginated = pagination.items

        posts_data = []
        for post, like_count, comment_count in posts_paginated:
            author_nickname = post.author.nickname if post.author and not post.is_anonymous else '익명'
            author_uid = post.author.user_uid if post.author and not post.is_anonymous else ''

            posts_data.append({
                'id': post.id,
                'title': post.title,
                'user_id': post.user_id,
                'author_nickname': author_nickname,
                'author_uid': author_uid,
                'is_anonymous': post.is_anonymous,
                'is_notice': post.is_notice,
                'views': post.views,
                'category': post.category,
                'likes': like_count,
                'comment_count': comment_count,
                'created_at': post.created_at.isoformat(),
                'updated_at': post.updated_at.isoformat(),
                'is_suspended': post.is_suspended, 
                'suspended_until': post.suspended_until.isoformat() if post.suspended_until else None 
            })

        return jsonify({
            'posts': posts_data,
            'total_pages': pagination.pages,
            'current_page': pagination.page,
            'total_posts': pagination.total
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error fetching community posts: {e}", exc_info=True)
        return jsonify({'message': '게시글 목록을 불러오는 데 실패했습니다.'}), 500

# 특정 게시글 상세 조회
@community_bp.route('/posts/<int:post_id>', methods=['GET'])
def get_post_detail(post_id):
    try:
        post = db.session.query(
            Post,
            func.count(db.distinct(PostLike.user_id)).label('like_count'),
            func.count(db.distinct(Comment.id)).label('comment_count')
        ).outerjoin(PostLike, Post.id == PostLike.post_id)\
         .outerjoin(Comment, Post.id == Comment.post_id)\
         .filter(Post.id == post_id)\
         .group_by(Post.id)\
         .first()
        
        if not post:
            return jsonify({'message': '게시글을 찾을 수 없습니다.'}), 404
        
        post_obj, like_count, comment_count = post
        post_obj.views += 1
        db.session.commit()

        mongo_db = _get_mongo_db()
        mongo_content = mongo_db.post_contents.find_one({'_id': ObjectId(post_obj.mongo_content_id)})
        content_text = mongo_content['content'] if mongo_content else '내용 없음'

        author_nickname = post_obj.author.nickname if post_obj.author and not post_obj.is_anonymous else '익명'
        author_username = post_obj.author.username if post_obj.author and not post_obj.is_anonymous else ''
        author_uid = post_obj.author.user_uid if post_obj.author and not post_obj.is_anonymous else ''

        user_liked = False
        if hasattr(g, 'user_id') and g.user_id:
            user_like = PostLike.query.filter_by(user_id=g.user_id, post_id=post_id).first()
            user_liked = user_like is not None

        comments = []
        comment_objects = Comment.query.filter_by(post_id=post_id).order_by(Comment.created_at.asc()).all()
        for comment_obj in comment_objects:
            comment_author_nickname = comment_obj.author.nickname if comment_obj.author else '탈퇴한 사용자'
            comments.append({
                'id': comment_obj.id,
                'content': comment_obj.content,
                'user_id': comment_obj.user_id,
                'author_nickname': comment_author_nickname,
                # [FIX] Safely access is_anonymous, defaulting to False if not present.
                # This prevents crashes if the DB column is missing.
                'is_anonymous': getattr(comment_obj, 'is_anonymous', False),
                'created_at': comment_obj.created_at.isoformat(),
                'updated_at': comment_obj.updated_at.isoformat()
            })

        return jsonify({
            'id': post_obj.id,
            'title': post_obj.title,
            'content': content_text,
            'user_id': post_obj.user_id,
            'author_nickname': author_nickname,
            'author_username': author_username,
            'author_uid': author_uid, 
            'is_anonymous': post_obj.is_anonymous,
            'is_notice': post_obj.is_notice,
            'views': post_obj.views,
            'category': post_obj.category,
            'likes': like_count,
            'comment_count': comment_count,
            'user_liked': user_liked, 
            'is_suspended': post_obj.is_suspended, 
            'suspended_until': post_obj.suspended_until.isoformat() if post_obj.suspended_until else None,
            'created_at': post_obj.created_at.isoformat(),
            'updated_at': post_obj.updated_at.isoformat(),
            'comments': comments
        }), 200

    except Exception as e:
        current_app.logger.error(f"Error fetching post detail {post_id}: {e}", exc_info=True)
        return jsonify({'message': '게시글 상세 정보를 불러오는 데 실패했습니다.'}), 500

# 게시글 작성
@community_bp.route('/posts', methods=['POST'])
@token_required
def create_post():
    data = request.get_json()
    title = data.get('title')
    content = data.get('content')
    category = data.get('category')
    is_anonymous = data.get('is_anonymous', False)

    if not all([title, content, category]):
        return jsonify({'message': '제목, 내용, 카테고리는 필수입니다.'}), 400

    try:
        mongo_db = _get_mongo_db()
        mongo_post_content = {
            'content': content,
            'created_at': datetime.datetime.utcnow(),
            'user_id': g.user_id
        }
        mongo_result = mongo_db.post_contents.insert_one(mongo_post_content)
        mongo_content_id = str(mongo_result.inserted_id)

        new_post = Post(
            title=title,
            mongo_content_id=mongo_content_id,
            user_id=g.user_id,
            is_anonymous=is_anonymous,
            category=category,
            views=0,
            is_notice=False
        )
        db.session.add(new_post)
        db.session.commit()
        return jsonify({'message': '게시글이 성공적으로 작성되었습니다.', 'post_id': new_post.id}), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating post: {e}", exc_info=True)
        return jsonify({'message': '게시글 작성에 실패했습니다.'}), 500

# 게시글 수정
@community_bp.route('/posts/<int:post_id>', methods=['PUT'])
@token_required
def update_post(post_id):
    data = request.get_json()
    title = data.get('title')
    content = data.get('content')
    category = data.get('category')
    is_anonymous = data.get('is_anonymous', None) 

    try:
        post = db.session.get(Post, post_id)
        if not post:
            return jsonify({'message': '게시글을 찾을 수 없습니다.'}), 404
        
        if post.user_id != g.user_id:
            return jsonify({'message': '게시글 수정 권한이 없습니다.'}), 403

        post.title = title if title is not None else post.title
        post.category = category if category is not None else post.category
        if is_anonymous is not None:
            post.is_anonymous = is_anonymous
        post.updated_at = datetime.datetime.utcnow()

        if content is not None:
            mongo_db = _get_mongo_db()
            mongo_db.post_contents.update_one(
                {'_id': ObjectId(post.mongo_content_id)},
                {'$set': {'content': content, 'updated_at': datetime.datetime.utcnow()}}
            )

        db.session.commit()
        return jsonify({'message': '게시글이 성공적으로 수정되었습니다.'}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating post {post_id}: {e}", exc_info=True)
        return jsonify({'message': '게시글 수정에 실패했습니다.'}), 500

# 게시글 삭제
@community_bp.route('/posts/<int:post_id>', methods=['DELETE'])
@token_required
def delete_post(post_id):
    try:
        post = db.session.get(Post, post_id)
        if not post:
            return jsonify({'message': '게시글을 찾을 수 없습니다.'}), 404
        
        if post.user_id != g.user_id:
            return jsonify({'message': '게시글 삭제 권한이 없습니다.'}), 403

        if post.mongo_content_id:
            mongo_db = _get_mongo_db()
            mongo_db.post_contents.delete_one({'_id': ObjectId(post.mongo_content_id)})

        db.session.delete(post)
        db.session.commit()
        return jsonify({'message': '게시글이 성공적으로 삭제되었습니다.'}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting post {post_id}: {e}", exc_info=True)
        return jsonify({'message': '게시글 삭제에 실패했습니다.'}), 500

# 게시글 좋아요/좋아요 취소
@community_bp.route('/posts/<int:post_id>/like', methods=['POST'])
@token_required
def toggle_post_like(post_id):
    user_id = g.user_id
    try:
        post = db.session.get(Post, post_id)
        if not post:
            return jsonify({'message': '게시글을 찾을 수 없습니다.'}), 404

        existing_like = PostLike.query.filter_by(user_id=user_id, post_id=post_id).first()

        if existing_like:
            db.session.delete(existing_like)
            db.session.commit()
            return jsonify({'message': '좋아요를 취소했습니다.', 'liked': False}), 200
        else:
            new_like = PostLike(user_id=user_id, post_id=post_id)
            db.session.add(new_like)
            db.session.commit()
            return jsonify({'message': '게시글에 좋아요를 눌렀습니다.', 'liked': True}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error toggling like for post {post_id} by user {user_id}: {e}", exc_info=True)
        return jsonify({'message': '좋아요 처리에 실패했습니다.'}), 500

# 게시글 신고 (기능 미구현)
@community_bp.route('/posts/<int:post_id>/report', methods=['POST'])
@token_required
def report_post(post_id):
    user_id = g.user_id
    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({'message': '게시글을 찾을 수 없습니다.'}), 404
    
    current_app.logger.info(f"User {user_id} reported post {post_id}.")
    
    return jsonify({'message': '게시글이 신고되었습니다. 검토 후 조치하겠습니다.'}), 200

# 댓글 작성 API
@community_bp.route('/posts/<int:post_id>/comments', methods=['POST'])
@token_required
def create_comment(post_id):
    data = request.get_json()
    user_id = g.user_id
    content = data.get('content')
    is_anonymous = data.get('is_anonymous', False)

    if not content:
        return jsonify({'message': '댓글 내용을 입력해주세요.'}), 400

    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({'message': '게시글을 찾을 수 없습니다.'}), 404

    author_user = User.query.get(user_id)
    if not author_user:
        current_app.logger.error(f"User with ID {user_id} not found when creating comment.")
        return jsonify({'message': '사용자 정보를 찾을 수 없습니다.'}), 500

    try:
        # [FIX] Check if the Comment model has the 'is_anonymous' column before trying to save it.
        # This makes the code resilient to DB schema changes.
        comment_data = {
            'content': content,
            'post_id': post_id,
            'user_id': user_id,
        }
        if hasattr(Comment, 'is_anonymous'):
             comment_data['is_anonymous'] = is_anonymous

        new_comment = Comment(**comment_data)
        db.session.add(new_comment)
        db.session.commit()
        return jsonify({'message': '댓글이 성공적으로 작성되었습니다.', 'comment_id': new_comment.id}), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating comment for post {post_id}: {e}", exc_info=True)
        return jsonify({'message': '댓글 작성에 실패했습니다.'}), 500

# 댓글 수정 (기능 미구현)
@community_bp.route('/comments/<int:comment_id>', methods=['PUT'])
@token_required
def update_comment(comment_id):
    return jsonify({'message': '댓글 수정 기능은 아직 준비 중입니다.'}), 200

# 댓글 삭제 (기능 미구현)
@community_bp.route('/comments/<int:comment_id>', methods=['DELETE'])
@token_required
def delete_comment(comment_id):
    return jsonify({'message': '댓글 삭제 기능은 아직 준비 중입니다.'}), 200


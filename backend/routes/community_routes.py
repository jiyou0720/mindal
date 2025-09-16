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

        # 게시글, 좋아요 수, 댓글 수를 함께 조회하는 쿼리
        # Post 객체를 직접 쿼리하여 attribute loader options (joinedload)를 사용할 수 있도록 합니다.
        query = db.session.query(
            Post, # Post 객체를 직접 쿼리
            func.count(db.distinct(PostLike.user_id)).label('like_count'), # PostLike를 사용하여 좋아요 수 집계
            func.count(db.distinct(Comment.id)).label('comment_count') # Comment를 사용하여 댓글 수 집계
        ).outerjoin(PostLike, Post.id == PostLike.post_id)\
         .outerjoin(Comment, Post.id == Comment.post_id)\
         .group_by(Post.id) # Post.id로 그룹화해야 집계 함수가 올바르게 작동

        if search_query:
            # 제목 또는 내용에서 검색 (MongoDB에서 내용 검색 필요)
            # 현재는 제목만 검색
            query = query.filter(Post.title.like(f'%{search_query}%'))
            # TODO: MongoDB에서 본문 내용 검색 로직 추가 필요
            # 예: post_ids_from_mongo = [str(p['_id']) for p in mongo.db.post_contents.find({'content': {'$regex': search_query, '$options': 'i'}})]
            # query = query.filter(db.or_(Post.title.like(f'%{search_query}%'), Post.mongo_content_id.in_(post_ids_from_mongo)))

        if category_filter:
            query = query.filter(Post.category == category_filter)

        # 공지사항은 항상 상단에 노출
        # is_notice 필드를 기준으로 정렬하고, 그 다음 created_at 내림차순
        query = query.order_by(Post.is_notice.desc(), Post.created_at.desc())

        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        posts_paginated = pagination.items

        posts_data = []
        for post, like_count, comment_count in posts_paginated:
            # 작성자 정보 가져오기
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
                'is_suspended': post.is_suspended, # 정지 여부 추가
                'suspended_until': post.suspended_until.isoformat() if post.suspended_until else None # 정지 해제 일시 추가
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
        # 게시글 조회 시 조회수 증가
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

        # 조회수 증가
        post_obj.views += 1
        db.session.commit()

        # [FIX] Use new MongoDB access method
        mongo_db = _get_mongo_db()
        mongo_content = mongo_db.post_contents.find_one({'_id': ObjectId(post_obj.mongo_content_id)})
        content_text = mongo_content['content'] if mongo_content else '내용 없음'

        # 작성자 정보 (익명 여부에 따라 처리)
        author_nickname = post_obj.author.nickname if post_obj.author and not post_obj.is_anonymous else '익명'
        author_username = post_obj.author.username if post_obj.author and not post_obj.is_anonymous else ''
        author_uid = post_obj.author.user_uid if post_obj.author and not post_obj.is_anonymous else ''

        # 현재 로그인된 사용자가 게시글에 좋아요를 눌렀는지 확인
        user_liked = False
        if hasattr(g, 'user_id') and g.user_id:
            user_like = PostLike.query.filter_by(user_id=g.user_id, post_id=post_id).first()
            user_liked = user_like is not None

        # 댓글 목록 가져오기
        comments = []
        comment_objects = Comment.query.filter_by(post_id=post_id).order_by(Comment.created_at.asc()).all()
        for comment_obj in comment_objects:
            comment_author_nickname = comment_obj.author.nickname if comment_obj.author else '탈퇴한 사용자'
            comments.append({
                'id': comment_obj.id,
                'content': comment_obj.content,
                'user_id': comment_obj.user_id,
                'author_nickname': comment_author_nickname,
                'created_at': comment_obj.created_at.isoformat(),
                'updated_at': comment_obj.updated_at.isoformat()
            })

        return jsonify({
            'id': post_obj.id,
            'title': post_obj.title,
            'content': content_text,
            'user_id': post_obj.user_id, # 게시글 작성자의 실제 user_id
            'author_nickname': author_nickname,
            'author_username': author_username, # 익명 아닐 경우 사용자 이름
            'author_uid': author_uid, # 익명 아닐 경우 사용자 UID
            'is_anonymous': post_obj.is_anonymous,
            'is_notice': post_obj.is_notice,
            'views': post_obj.views,
            'category': post_obj.category,
            'likes': like_count,
            'comment_count': comment_count,
            'user_liked': user_liked, # 현재 사용자가 좋아요 눌렀는지 여부
            'is_suspended': post_obj.is_suspended, # 정지 여부
            'suspended_until': post_obj.suspended_until.isoformat() if post_obj.suspended_until else None, # 정지 해제 일시
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
        # [FIX] Use new MongoDB access method
        mongo_db = _get_mongo_db()
        
        # MongoDB에 본문 내용 저장
        mongo_post_content = {
            'content': content,
            'created_at': datetime.datetime.utcnow(),
            'user_id': g.user_id # 본문 내용에도 사용자 ID 기록
        }
        mongo_result = mongo_db.post_contents.insert_one(mongo_post_content)
        mongo_content_id = str(mongo_result.inserted_id)

        new_post = Post(
            title=title,
            mongo_content_id=mongo_content_id,
            user_id=g.user_id, # g.user_id는 JWT 토큰에서 디코딩된 사용자 ID
            is_anonymous=is_anonymous,
            category=category,
            views=0,
            is_notice=False # 일반 게시글은 공지 아님
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
    is_anonymous = data.get('is_anonymous', None) # None을 허용하여 변경 없을 시 유지

    try:
        post = db.session.get(Post, post_id)
        if not post:
            return jsonify({'message': '게시글을 찾을 수 없습니다.'}), 404
        
        # 게시글 작성자만 수정 가능
        if post.user_id != g.user_id:
            return jsonify({'message': '게시글 수정 권한이 없습니다.'}), 403

        post.title = title if title is not None else post.title
        post.category = category if category is not None else post.category
        if is_anonymous is not None:
            post.is_anonymous = is_anonymous
        post.updated_at = datetime.datetime.utcnow() # 명시적으로 업데이트 시간 설정

        # MongoDB 본문 내용 업데이트
        if content is not None:
            # [FIX] Use new MongoDB access method
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
        
        # 게시글 작성자만 삭제 가능
        if post.user_id != g.user_id:
            return jsonify({'message': '게시글 삭제 권한이 없습니다.'}), 403

        # MongoDB 본문 내용 먼저 삭제
        if post.mongo_content_id:
            # [FIX] Use new MongoDB access method
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

    # User 객체를 가져와 Comment의 author 관계에 할당합니다.
    author_user = User.query.get(user_id)
    if not author_user:
        current_app.logger.error(f"User with ID {user_id} not found when creating comment.")
        return jsonify({'message': '사용자 정보를 찾을 수 없습니다.'}), 500

    try:
        new_comment = Comment(
            content=content,
            post_id=post_id,
            user_id=user_id # user_id 직접 할당
        )
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

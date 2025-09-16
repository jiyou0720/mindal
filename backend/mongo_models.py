import os
from flask import Blueprint, request, jsonify, g, current_app
from backend.extensions import db, mongo
from backend.maria_models import Post, Comment, User, PostLike 
from backend.routes.auth_routes import token_required
from bson.objectid import ObjectId
from werkzeug.utils import secure_filename
import datetime
import uuid
import jwt
from sqlalchemy.orm import joinedload
from sqlalchemy import func


community_bp = Blueprint('community_api', __name__)

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
        g.user_id = None
        auth_header = request.headers.get('Authorization')
        if auth_header and auth_header.startswith('Bearer '):
            token = auth_header.split(" ")[1]
            try:
                decoded_token = jwt.decode(token, current_app.config['JWT_SECRET_KEY'], algorithms=['HS256'])
                g.user_id = decoded_token['user_id']
            except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
                g.user_id = None
        
        post_query = db.session.query(
            Post,
            func.count(db.distinct(PostLike.user_id)).label('like_count')
        ).outerjoin(PostLike, Post.id == PostLike.post_id)\
         .filter(Post.id == post_id)\
         .group_by(Post.id)
        
        post_result = post_query.first()
        
        if not post_result:
            return jsonify({'message': '게시글을 찾을 수 없습니다.'}), 404
        
        post_obj, like_count = post_result

        post_obj.views += 1
        db.session.commit()

        mongo_content = mongo.db.post_contents.find_one({'_id': ObjectId(post_obj.mongo_content_id)})
        content_text = mongo_content['content'] if mongo_content else '내용 없음'

        author_nickname = '익명' if post_obj.is_anonymous else (post_obj.author.nickname if post_obj.author else '알 수 없음')
        author_uid = '' if post_obj.is_anonymous else (post_obj.author.user_uid if post_obj.author else '')

        user_liked = False
        if g.user_id:
            user_liked = db.session.query(PostLike).filter_by(user_id=g.user_id, post_id=post_id).first() is not None

        comments = []
        comment_objects = Comment.query.filter_by(post_id=post_id).order_by(Comment.created_at.asc()).all()
        for comment_obj in comment_objects:
            comment_author_nickname = '익명' if comment_obj.is_anonymous else (comment_obj.author.nickname if comment_obj.author else '탈퇴한 사용자')
            comments.append({
                'id': comment_obj.id,
                'content': comment_obj.content,
                'user_id': comment_obj.user_id,
                'author_nickname': comment_author_nickname,
                'is_anonymous': comment_obj.is_anonymous,
                'created_at': comment_obj.created_at.isoformat(),
                'updated_at': comment_obj.updated_at.isoformat()
            })

        return jsonify({
            'id': post_obj.id,
            'title': post_obj.title,
            'content': content_text,
            'user_id': post_obj.user_id,
            'author_nickname': author_nickname,
            'author_uid': author_uid,
            'is_anonymous': post_obj.is_anonymous,
            'views': post_obj.views,
            'category': post_obj.category,
            'likes': like_count,
            'comment_count': len(comments),
            'user_liked': user_liked,
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
        mongo_post_content = {
            'content': content,
            'created_at': datetime.datetime.utcnow(),
            'user_id': g.user_id
        }
        mongo_result = mongo.db.post_contents.insert_one(mongo_post_content)
        mongo_content_id = str(mongo_result.inserted_id)

        new_post = Post(
            title=title,
            mongo_content_id=mongo_content_id,
            user_id=g.user_id,
            is_anonymous=is_anonymous,
            category=category,
            views=0
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

        if title is not None: post.title = title
        if category is not None: post.category = category
        if is_anonymous is not None: post.is_anonymous = is_anonymous
        post.updated_at = datetime.datetime.utcnow()

        if content is not None:
            mongo.db.post_contents.update_one(
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
            mongo.db.post_contents.delete_one({'_id': ObjectId(post.mongo_content_id)})

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
            liked = False
        else:
            new_like = PostLike(user_id=user_id, post_id=post_id)
            db.session.add(new_like)
            liked = True
        
        db.session.commit()
        
        like_count = db.session.query(func.count(PostLike.user_id)).filter(PostLike.post_id == post_id).scalar()
        
        return jsonify({
            'message': '좋아요를 취소했습니다.' if not liked else '게시글에 좋아요를 눌렀습니다.',
            'liked': liked,
            'like_count': like_count
        }), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error toggling like for post {post_id} by user {user_id}: {e}", exc_info=True)
        return jsonify({'message': '좋아요 처리에 실패했습니다.'}), 500

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

    try:
        # ✅ is_anonymous 값을 Comment 모델 생성자에 전달
        new_comment = Comment(
            content=content,
            post_id=post_id,
            user_id=user_id,
            is_anonymous=is_anonymous
        )
        db.session.add(new_comment)
        db.session.commit()
        return jsonify({'message': '댓글이 성공적으로 작성되었습니다.', 'comment_id': new_comment.id}), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating comment for post {post_id}: {e}", exc_info=True)
        return jsonify({'message': '댓글 작성에 실패했습니다.'}), 500


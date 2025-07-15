# backend/routes/community_routes.py
from flask import Blueprint, request, jsonify, g, current_app
from flask_pymongo import PyMongo
from auth import token_required
from maria_models import User, Post, Comment
from mongo_models import MongoPostContent # Ensure MongoPostContent is suitable for post content
from extensions import db
from bson.objectid import ObjectId
import datetime
import os # For file operations

community_bp = Blueprint('community_api', __name__)

@community_bp.record_once
def record(state):
    state.app.config['MONGO_DB'] = PyMongo(state.app).db
    # Configure upload folder (ensure this directory exists and is writable)
    state.app.config['UPLOAD_FOLDER'] = os.path.join(state.app.root_path, '../uploads/community')
    os.makedirs(state.app.config['UPLOAD_FOLDER'], exist_ok=True) # Ensure directory exists

def get_posts_content_collection():
    return current_app.config['MONGO_DB'].post_contents

# --- 게시글 관련 API 엔드포인트 ---

# 1. 새 게시글 생성
@community_bp.route('/posts', methods=['POST'])
@token_required
def create_post():
    # When FormData is used, request.form is for text fields and request.files for files
    title = request.form.get('title')
    category = request.form.get('category') # New: Category
    content = request.form.get('content')
    is_anonymous_str = request.form.get('is_anonymous') # 'true' or 'false' string
    author_name = request.form.get('author_name') # New: Author name (nickname or '익명')

    is_anonymous = is_anonymous_str == 'true'
    user_id = int(g.user_id)

    if not title or not content or not category or not author_name:
        return jsonify({'message': 'Title, content, category, and author type are required'}), 400

    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'message': 'User not found'}), 404

    # Handle file attachments
    attached_files_info = []
    if 'attachments' in request.files:
        for file in request.files.getlist('attachments'):
            if file.filename:
                # You'd typically save the file here and store its path/URL
                # For demonstration, let's just create a dummy path and info
                filename = file.filename
                # Generate a unique filename to prevent collisions
                unique_filename = f"{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{filename}"
                file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique_filename)
                try:
                    file.save(file_path)
                    attached_files_info.append({
                        'filename': filename,
                        'unique_filename': unique_filename,
                        'file_path': file_path, # In a real app, this might be a URL
                        'mimetype': file.mimetype
                    })
                except Exception as e:
                    current_app.logger.error(f"Failed to save file {filename}: {e}")
                    # Decide how to handle file upload failure (e.g., return error or continue)
                    return jsonify({'message': f'Failed to upload file: {filename}'}), 500
    mongo_post_data = {
        'content': content,
        'category': category,
        'author_id': user_id,
        'author_username': user.username,
        'author_nickname': user.nickname, # Storing nickname for display
        'is_anonymous': is_anonymous,
        'display_author_name': author_name, # The name to actually display
        'attachments': attached_files_info,
        'created_at': datetime.datetime.utcnow()
    }
    mongo_result = get_posts_content_collection().insert_one(mongo_post_data)
    mongodb_content_id = str(mongo_result.inserted_id)

    # MariaDB에 게시글 메타데이터 저장 (수정: author_username은 실제 로그인 사용자 이름, author_name은 표시될 이름)
    # Ensure your MariaDB Post model is updated to include `category`, `is_anonymous`, `display_author_name`, etc.
    # For now, I'll update Post model assumption slightly.
    new_post = Post(
        title=title,
        author_id=user_id,
        author_username=user.username, # The actual registered username
        category=category, # New field in MariaDB Post model
        is_anonymous=is_anonymous, # New field in MariaDB Post model
        display_author_name=author_name, # New field in MariaDB Post model
        mongodb_content_id=mongodb_content_id # Link to MongoDB content
    )
    db.session.add(new_post)
    db.session.commit()

    return jsonify({'message': 'Post created successfully!', 'post_id': new_post.id}), 201


# 2. 모든 게시글 조회 (페이징, 검색, 정렬 포함)
@community_bp.route('/posts', methods=['GET'])
def get_all_posts():
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    search_query = request.args.get('search', type=str)
    sort_by = request.args.get('sort_by', 'created_at', type=str) # 'created_at' 또는 'title' 등
    order = request.args.get('order', 'desc', type=str) # 'asc' 또는 'desc'

    query = Post.query

    if search_query:
        # 제목이나 작성자 이름에 검색어가 포함된 경우
        query = query.filter(
            (Post.title.ilike(f'%{search_query}%')) |
            (Post.author_username.ilike(f'%{search_query}%'))
        )

    # 정렬
    if hasattr(Post, sort_by):
        if order == 'asc':
            query = query.order_by(getattr(Post, sort_by).asc())
        else: # 기본은 desc
            query = query.order_by(getattr(Post, sort_by).desc())
    else: # 유효하지 않은 sort_by일 경우 기본 정렬 적용
        query = query.order_by(Post.created_at.desc())

    posts_pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    posts = posts_pagination.items

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

    return jsonify({
        'message': 'Posts retrieved successfully!',
        'posts': posts_data,
        'total_posts': posts_pagination.total,
        'total_pages': posts_pagination.pages,
        'current_page': posts_pagination.page,
        'per_page': posts_pagination.per_page
    }), 200

# 3. 특정 게시글 조회 (내용 포함)
@community_bp.route('/posts/<int:post_id>', methods=['GET'])
def get_single_post(post_id):
    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({'message': 'Post not found'}), 404

    post_dict = post.to_dict()
    # MongoDB에서 게시글 내용 가져오기
    mongo_content_data = get_posts_content_collection().find_one({'_id': ObjectId(post.mongodb_content_id)})
    if mongo_content_data:
        post_dict['content'] = MongoPostContent.from_mongo(mongo_content_data).content
    else:
        post_dict['content'] = "Content not found" # MongoDB에서 내용을 찾지 못한 경우

    # 해당 게시글의 댓글도 함께 반환
    comments = Comment.query.filter_by(post_id=post_id).order_by(Comment.created_at.asc()).all()
    post_dict['comments'] = [comment.to_dict() for comment in comments]

    return jsonify({'message': 'Post retrieved successfully!', 'post': post_dict}), 200

# 4. 게시글 수정
@community_bp.route('/posts/<int:post_id>', methods=['PUT'])
@token_required
def update_post(post_id):
    data = request.get_json()
    title = data.get('title')
    content = data.get('content')
    user_id = int(g.user_id)

    # MariaDB에서 게시글 조회
    existing_post = db.session.get(Post, post_id)
    if not existing_post:
        return jsonify({'message': 'Post not found'}), 404

    # 작성자 확인
    if existing_post.author_id != user_id:
        return jsonify({'message': 'Unauthorized to update this post'}), 403

    if not title and not content: # 아무것도 수정하지 않으려 할 때
        return jsonify({'message': 'No content to update'}), 400

    # 제목 업데이트
    if title is not None:
        existing_post.title = title

    # MongoDB 내용 업데이트
    if content is not None:
        get_posts_content_collection().update_one(
            {'_id': ObjectId(existing_post.mongodb_content_id)},
            {'$set': {'content': content}}
        )

    existing_post.updated_at = datetime.datetime.utcnow()
    db.session.commit()

    # 업데이트된 정보와 함께 MongoDB의 최신 내용 포함하여 반환
    updated_post_dict = existing_post.to_dict()
    updated_mongo_content = get_posts_content_collection().find_one({'_id': ObjectId(existing_post.mongodb_content_id)})
    if updated_mongo_content:
        updated_post_dict['content'] = MongoPostContent.from_mongo(updated_mongo_content).content
    else:
        updated_post_dict['content'] = "Content not found after update"

    return jsonify({
        'message': 'Post updated successfully!',
        'post': updated_post_dict
    }), 200

# 5. 게시글 삭제
@community_bp.route('/posts/<int:post_id>', methods=['DELETE'])
@token_required
def delete_post(post_id):
    user_id = int(g.user_id)

    existing_post = db.session.get(Post, post_id)
    if not existing_post:
        return jsonify({'message': 'Post not found'}), 404

    # 작성자 확인
    if existing_post.author_id != user_id:
        return jsonify({'message': 'Unauthorized to delete this post'}), 403

    # MongoDB에서 게시글 내용 삭제
    try:
        get_posts_content_collection().delete_one({'_id': ObjectId(existing_post.mongodb_content_id)})
    except Exception as e:
        print(f"Error deleting MongoDB content for post {post_id}: {e}")

    # MariaDB에서 게시글과 관련된 댓글 삭제 (DB 스키마에 따라 cascade 설정되어 있다면 이 부분은 불필요할 수 있음)
    comments_on_post = Comment.query.filter_by(post_id=post_id).all()
    for comment in comments_on_post:
        db.session.delete(comment)

    # MariaDB에서 게시글 삭제
    db.session.delete(existing_post)
    db.session.commit()

    return jsonify({'message': 'Post and associated content/comments deleted successfully!'}), 200


# --- 댓글 관련 API 엔드포인트 ---

# 1. 댓글 생성
@community_bp.route('/posts/<int:post_id>/comments', methods=['POST'])
@token_required
def create_comment(post_id):
    data = request.get_json()
    content = data.get('content')
    user_id = int(g.user_id)

    if not content:
        return jsonify({'message': 'Comment content is required'}), 400

    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({'message': 'Post not found'}), 404

    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'message': 'User not found'}), 404

    new_comment = Comment(
        post_id=post_id,
        author_id=user_id,
        author_username=user.username, # 댓글 작성자 이름 저장
        content=content
    )
    db.session.add(new_comment)
    db.session.commit()

    return jsonify({
        'message': 'Comment created successfully!',
        'comment': new_comment.to_dict()
    }), 201

# 2. 특정 게시글의 모든 댓글 조회 (게시글 조회 시 함께 반환되므로 별도로 필요 없을 수 있으나, API로 제공)
@community_bp.route('/posts/<int:post_id>/comments', methods=['GET'])
def get_comments_for_post(post_id):
    comments = Comment.query.filter_by(post_id=post_id).order_by(Comment.created_at.asc()).all()
    if not comments:
        # If no comments are found, return an empty list instead of 404,
        # as an empty comment section is a valid state.
        return jsonify({'message': 'No comments found for this post', 'comments': []}), 200
    comments_data = [comment.to_dict() for comment in comments]
    return jsonify({
        'message': 'Comments retrieved successfully!',
        'comments': comments_data
    }), 200

# 3. 댓글 수정
@community_bp.route('/comments/<int:comment_id>', methods=['PUT'])
@token_required
def update_comment(comment_id):
    data = request.get_json()
    content = data.get('content')
    user_id = int(g.user_id)

    if not content:
        return jsonify({'message': 'Comment content is required'}), 400

    # MariaDB에서 댓글 조회
    existing_comment = db.session.get(Comment, comment_id)
    if not existing_comment:
        return jsonify({'message': 'Comment not found'}), 404

    # 작성자 확인
    if existing_comment.author_id != user_id:
        return jsonify({'message': 'Unauthorized to update this comment'}), 403

    existing_comment.content = content
    existing_comment.updated_at = datetime.datetime.utcnow()
    db.session.commit()

    return jsonify({
        'message': 'Comment updated successfully!',
        'comment': existing_comment.to_dict()
    }), 200

# 4. 댓글 삭제
@community_bp.route('/comments/<int:comment_id>', methods=['DELETE'])
@token_required
def delete_comment(comment_id):
    user_id = int(g.user_id)

    # MariaDB에서 댓글 조회
    existing_comment = db.session.get(Comment, comment_id)
    if not existing_comment:
        return jsonify({'message': 'Comment not found'}), 404

    # 작성자 확인
    if existing_comment.author_id != user_id:
        return jsonify({'message': 'Unauthorized to delete this comment'}), 403

    db.session.delete(existing_comment)
    db.session.commit()

    return jsonify({'message': 'Comment deleted successfully!'}), 200
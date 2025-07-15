# backend/routes/community_routes.py
import os
from flask import Blueprint, request, jsonify, g, current_app
from flask_pymongo import PyMongo
from auth import token_required
from mongo_models import MongoPostContent
from maria_models import Post, User, Comment # Comment 모델 임포트
from extensions import db
from bson.objectid import ObjectId, InvalidId
import datetime
from werkzeug.utils import secure_filename

community_bp = Blueprint('community_api', __name__)

# 파일 업로드 경로 설정
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'frontend', 'static', 'uploads', 'community')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'mp3', 'wav'}

# UPLOAD_FOLDER가 없으면 생성
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# 허용된 파일 확장자 확인 함수
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@community_bp.record_once
def record(state):
    if 'MONGO_DB' not in state.app.config:
        state.app.config['MONGO_DB'] = PyMongo(state.app).db

# MongoDB 컬렉션 참조 함수
def get_mongo_post_content_collection():
    return current_app.config['MONGO_DB'].post_contents

# --- 게시글 관련 API 엔드포인트 ---

# 게시글 생성
@community_bp.route('/posts', methods=['POST'])
@token_required
def create_post():
    title = request.form.get('title')
    content = request.form.get('content')
    category = request.form.get('category')
    is_anonymous = request.form.get('is_anonymous') == 'true'

    user_id = int(g.user_id)
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'message': 'User not found'}), 404

    if not title or not content or not category:
        return jsonify({'message': 'Title, content, and category are required'}), 400

    attachment_paths = []
    if 'attachments' in request.files:
        files = request.files.getlist('attachments')
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(UPLOAD_FOLDER, filename)
                file.save(filepath)
                attachment_paths.append(f'/static/uploads/community/{filename}')
            else:
                return jsonify({'message': f'허용되지 않는 파일 형식 또는 파일이 없습니다: {file.filename}'}), 400

    new_mongo_content = MongoPostContent(content=content, attachment_paths=attachment_paths)
    mongo_result = get_mongo_post_content_collection().insert_one(new_mongo_content.to_dict())
    mongodb_content_id = str(mongo_result.inserted_id)

    display_author_name = user.nickname if user.nickname and not is_anonymous else user.username if not is_anonymous else '익명'

    new_post = Post(
        title=title,
        author_id=user_id,
        author_username=user.username,
        category=category,
        is_anonymous=is_anonymous,
        display_author_name=display_author_name,
        mongodb_content_id=mongodb_content_id
    )
    db.session.add(new_post)
    db.session.commit()

    return jsonify({
        'message': '게시글이 성공적으로 작성되었습니다!',
        'post_id': new_post.id
    }), 201

# 게시글 목록 조회
@community_bp.route('/posts', methods=['GET'])
def get_all_posts():
    page = request.args.get('page', 1, type=int)
    limit = request.args.get('limit', 10, type=int)
    offset = (page - 1) * limit

    posts = Post.query.order_by(Post.created_at.desc()).offset(offset).limit(limit).all()
    total_posts = Post.query.count()

    posts_data = []
    for post in posts:
        content_preview = ''
        if post.mongodb_content_id:
            try:
                mongo_content_data = get_mongo_post_content_collection().find_one({'_id': ObjectId(post.mongodb_content_id)})
                if mongo_content_data:
                    content_preview = mongo_content_data.get('content', '')
            except InvalidId:
                print(f"Warning: Invalid ObjectId for post {post.id}: {post.mongodb_content_id}. Skipping content load.")
                content_preview = '[내용 로드 오류: 유효하지 않은 ID]'
            except Exception as e:
                print(f"Error loading MongoDB content for post {post.id}: {e}")
                content_preview = '[내용 로드 오류]'
        else:
            content_preview = '[내용 없음]'

        author = db.session.get(User, post.author_id)
        display_author_name = author.nickname if author and author.nickname and not post.is_anonymous else author.username if author and not post.is_anonymous else '익명'

        posts_data.append({
            'id': post.id,
            'title': post.title,
            'category': post.category,
            'author_id': post.author_id,
            'author_username': post.author_username,
            'display_author_name': display_author_name,
            'content_preview': content_preview[:100] + '...' if len(content_preview) > 100 else content_preview,
            'created_at': post.created_at.isoformat(),
            'views': post.views,
            'comment_count': len(post.comments)
        })

    return jsonify({
        'message': '게시글 목록 조회 성공',
        'posts': posts_data,
        'total_posts': total_posts,
        'page': page,
        'limit': limit
    }), 200

# 게시글 상세 정보 조회
@community_bp.route('/posts/<int:post_id>', methods=['GET'])
@token_required
def get_post_detail(post_id):
    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({'message': '게시글을 찾을 수 없습니다.'}), 404

    post.views = (post.views or 0) + 1
    db.session.commit()

    mongo_content_data = None
    if post.mongodb_content_id:
        try:
            mongo_content_data = get_mongo_post_content_collection().find_one({'_id': ObjectId(post.mongodb_content_id)})
        except InvalidId:
            print(f"Warning: Invalid ObjectId for post {post.id} in get_post_detail: {post.mongodb_content_id}")
            return jsonify({'message': '게시글 내용을 불러올 수 없습니다 (유효하지 않은 MongoDB ID).'}), 500
        except Exception as e:
            print(f"Error loading MongoDB content for post {post.id} in get_post_detail: {e}")
            return jsonify({'message': '게시글 내용을 불러오는 중 오류가 발생했습니다.'}), 500

    if not mongo_content_data:
        return jsonify({'message': '게시글 내용을 찾을 수 없습니다.'}), 404
    
    mongo_content = MongoPostContent.from_mongo(mongo_content_data)

    author = db.session.get(User, post.author_id)
    if not author:
        return jsonify({'message': '작성자 정보를 찾을 수 없습니다.'}), 404

    return jsonify({
        'message': '게시글 상세 정보 조회 성공',
        'post': {
            'id': post.id,
            'title': post.title,
            'category': post.category,
            'author_id': post.author_id,
            'author_username': post.author_username,
            'is_anonymous': post.is_anonymous,
            'display_author_name': author.nickname if author.nickname and not post.is_anonymous else author.username if not post.is_anonymous else '익명',
            'content': mongo_content.content,
            'attachment_paths': mongo_content.attachment_paths,
            'created_at': post.created_at.isoformat(),
            'updated_at': post.updated_at.isoformat(),
            'views': post.views
        },
        'author': author.to_dict()
    }), 200

# 게시글 수정
@community_bp.route('/posts/<int:post_id>', methods=['PUT'])
@token_required
def update_post(post_id):
    title = request.form.get('title')
    content = request.form.get('content')
    category = request.form.get('category')
    is_anonymous = request.form.get('is_anonymous') == 'true'
    
    attachment_paths = []
    if 'attachments' in request.files:
        files = request.files.getlist('attachments')
        for file in files:
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(UPLOAD_FOLDER, filename)
                file.save(filepath)
                attachment_paths.append(f'/static/uploads/community/{filename}')
            else:
                return jsonify({'message': f'허용되지 않는 파일 형식 또는 파일이 없습니다: {file.filename}'}), 400

    user_id = int(g.user_id)
    post = db.session.get(Post, post_id)

    if not post:
        return jsonify({'message': '게시글을 찾을 수 없습니다.'}), 404

    if post.author_id != user_id:
        return jsonify({'message': '이 게시글을 수정할 권한이 없습니다.'}), 403

    if not title or not content or not category:
        return jsonify({'message': 'Title, content, and category are required'}), 400

    post.title = title
    post.category = category
    post.is_anonymous = is_anonymous
    
    user = db.session.get(User, user_id)
    post.display_author_name = user.nickname if user.nickname and not is_anonymous else user.username if not is_anonymous else '익명'
    
    post.updated_at = datetime.datetime.utcnow()
    db.session.commit()

    update_fields = {
        'content': content,
    }
    if attachment_paths:
        update_fields['attachment_paths'] = attachment_paths

    get_mongo_post_content_collection().update_one(
        {'_id': ObjectId(post.mongodb_content_id)},
        {'$set': update_fields}
    )

    return jsonify({'message': '게시글이 성공적으로 수정되었습니다!'}), 200

# 게시글 삭제
@community_bp.route('/posts/<int:post_id>', methods=['DELETE'])
@token_required
def delete_post(post_id):
    user_id = int(g.user_id)
    post = db.session.get(Post, post_id)

    if not post:
        return jsonify({'message': '게시글을 찾을 수 없습니다.'}), 404

    if post.author_id != user_id:
        return jsonify({'message': '이 게시글을 삭제할 권한이 없습니다.'}), 403

    if post.mongodb_content_id:
        mongo_content_data = get_mongo_post_content_collection().find_one({'_id': ObjectId(post.mongodb_content_id)})
        if mongo_content_data:
            mongo_content = MongoPostContent.from_mongo(mongo_content_data)
            for path in mongo_content.attachment_paths:
                filename = os.path.basename(path)
                filepath = os.path.join(UPLOAD_FOLDER, filename)
                if os.path.exists(filepath):
                    os.remove(filepath)
                    print(f"Deleted attachment: {filepath}")
            get_mongo_post_content_collection().delete_one({'_id': ObjectId(post.mongodb_content_id)})

    db.session.delete(post)
    db.session.commit()

    return jsonify({'message': '게시글이 성공적으로 삭제되었습니다!'}), 200

# --- 댓글 관련 API 엔드포인트 ---

# 댓글 작성
@community_bp.route('/posts/<int:post_id>/comments', methods=['POST'])
@token_required
def create_comment(post_id):
    data = request.get_json()
    content = data.get('content')

    user_id = int(g.user_id)
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'message': 'User not found'}), 404

    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({'message': '게시글을 찾을 수 없습니다.'}), 404

    if not content:
        return jsonify({'message': '댓글 내용을 입력해주세요.'}), 400

    # --- 수정된 부분: 댓글 작성자의 표시 이름 결정 ---
    # 댓글은 익명 옵션이 없으므로, 닉네임이 있으면 닉네임, 없으면 username 사용
    comment_display_name = user.nickname if user.nickname else user.username

    new_comment = Comment(
        post_id=post_id,
        author_id=user_id,
        author_username=user.username, # MariaDB에 저장되는 실제 username
        content=content,
        display_author_name=comment_display_name # 새로 추가된 필드에 표시 이름 저장
    )
    db.session.add(new_comment)
    db.session.commit()

    return jsonify({
        'message': '댓글이 성공적으로 작성되었습니다!',
        'comment': new_comment.to_dict()
    }), 201

# 게시글의 모든 댓글 조회
@community_bp.route('/posts/<int:post_id>/comments', methods=['GET'])
@token_required
def get_comments_for_post(post_id):
    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({'message': '게시글을 찾을 수 없습니다.'}), 404

    comments = Comment.query.filter_by(post_id=post_id).order_by(Comment.created_at.asc()).all()
    comments_data = []
    for comment in comments:
        # --- 수정된 부분: 댓글 작성자의 표시 이름 반환 ---
        # Comment 모델에 display_author_name이 저장되어 있으므로 이를 사용
        comments_data.append({
            'id': comment.id,
            'post_id': comment.post_id,
            'author_id': comment.author_id,
            'author_username': comment.author_username, # 실제 username (디버깅용 등)
            'display_author_name': comment.display_author_name, # 표시될 이름 (닉네임 또는 username)
            'content': comment.content,
            'created_at': comment.created_at.isoformat(),
            'updated_at': comment.updated_at.isoformat()
        })

    return jsonify({
        'message': '댓글 목록 조회 성공',
        'comments': comments_data
    }), 200

# 댓글 수정
@community_bp.route('/comments/<int:comment_id>', methods=['PUT'])
@token_required
def update_comment(comment_id):
    data = request.get_json()
    content = data.get('content')
    user_id = int(g.user_id)

    comment = db.session.get(Comment, comment_id)
    if not comment:
        return jsonify({'message': '댓글을 찾을 수 없습니다.'}), 404

    if comment.author_id != user_id:
        return jsonify({'message': '이 댓글을 수정할 권한이 없습니다.'}), 403

    if not content:
        return jsonify({'message': '댓글 내용을 입력해주세요.'}), 400

    comment.content = content
    comment.updated_at = datetime.datetime.utcnow()
    db.session.commit()

    return jsonify({'message': '댓글이 성공적으로 수정되었습니다!', 'comment': comment.to_dict()}), 200

# 댓글 삭제
@community_bp.route('/comments/<int:comment_id>', methods=['DELETE'])
@token_required
def delete_comment(comment_id):
    user_id = int(g.user_id)

    comment = db.session.get(Comment, comment_id)
    if not comment:
        return jsonify({'message': '댓글을 찾을 수 없습니다.'}), 404

    if comment.author_id != user_id:
        return jsonify({'message': '이 댓글을 삭제할 권한이 없습니다.'}), 403

    db.session.delete(comment)
    db.session.commit()

    return jsonify({'message': '댓글이 성공적으로 삭제되었습니다!'}), 200

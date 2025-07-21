# backend/routes/community_routes.py
import os
import json
from flask import Blueprint, request, jsonify, g, current_app
from flask_pymongo import PyMongo
from auth import token_required, roles_required
from maria_models import Post, Comment, User, PostLike, CommentLike
from mongo_models import MongoPostContent # CommunityContent 대신 MongoPostContent 사용
from extensions import db, mongo # mongo 임포트 추가
from bson.objectid import ObjectId
import datetime
import uuid
from werkzeug.utils import secure_filename

community_bp = Blueprint('community_api', __name__)

# UPLOAD_FOLDER 정의
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'frontend', 'static', 'uploads', 'community')

@community_bp.record_once
def record(state):
    # PyMongo 인스턴스를 앱 컨텍스트에 저장
    state.app.config['MONGO_DB'] = PyMongo(state.app).db

def get_mongo_post_content_collection():
    # MongoDB post_contents 컬렉션 참조 함수
    return current_app.config['MONGO_DB'].post_contents

# Helper to generate unique filename
def generate_unique_filename(filename):
    ext = filename.rsplit('.', 1)[1].lower()
    unique_name = str(uuid.uuid4()) + '.' + ext
    return unique_name

# 게시글 생성 (POST)
@community_bp.route('/posts', methods=['POST'])
@token_required
@roles_required('일반 사용자', '에디터', '운영자', '관리자') # 게시글 작성 권한
def create_post():
    try:
        title = request.form.get('title')
        category = request.form.get('category')
        content = request.form.get('content') # 게시글 본문 (HTML)
        is_anonymous = request.form.get('is_anonymous') == 'true'

        current_app.logger.debug(f"게시글 생성 요청: title={title}, category={category}, is_anonymous={is_anonymous}")
        current_app.logger.debug(f"게시글 본문 길이: {len(content) if content else 0}")

        if not title or not category or not content:
            current_app.logger.warning("필수 필드 누락: 제목, 카테고리, 내용 중 하나 이상이 없습니다.")
            return jsonify({'message': '제목, 카테고리, 내용을 모두 입력해주세요.'}), 400

        # 1. MongoDB에 게시글 본문 저장
        attachment_paths = []
        if 'attachments' in request.files:
            for file in request.files.getlist('attachments'):
                if file.filename == '':
                    continue
                unique_filename = generate_unique_filename(secure_filename(file.filename))
                file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
                os.makedirs(UPLOAD_FOLDER, exist_ok=True)
                file.save(file_path)
                attachment_paths.append(f'/static/uploads/community/{unique_filename}')
            current_app.logger.debug(f"첨부 파일 저장 완료: {attachment_paths}")

        mongo_post_content = MongoPostContent(content=content, attachment_paths=attachment_paths)
        
        try:
            # MongoDB에 저장하고 _id를 가져옴
            inserted_mongo_doc = get_mongo_post_content_collection().insert_one(mongo_post_content.to_dict())
            mongo_content_id = str(inserted_mongo_doc.inserted_id)
            current_app.logger.info(f"MongoDB에 게시글 본문 저장 성공. MongoDB ID: {mongo_content_id}")
        except Exception as e:
            current_app.logger.error(f"MongoDB 저장 중 오류 발생: {e}")
            return jsonify({'message': '게시글 본문 저장 중 오류가 발생했습니다.'}), 500

        # 2. MariaDB에 게시글 메타데이터 저장
        author_id = g.user_id
        # g.nickname이 없을 경우 g.username을 사용하거나 기본값 설정
        author_nickname = g.nickname if g.nickname else g.username if g.username else "알 수 없음"
        
        new_post = Post(
            title=title,
            category=category,
            author_id=author_id,
            author_nickname=author_nickname,
            is_anonymous=is_anonymous,
            mongodb_content_id=mongo_content_id # MongoDB 문서 ID 연결
        )

        db.session.add(new_post)
        db.session.commit()
        current_app.logger.info(f"MariaDB에 게시글 메타데이터 저장 성공. Post ID: {new_post.id}")

        return jsonify({
            'message': '게시글이 성공적으로 작성되었습니다!',
            'post_id': new_post.id,
            'mongodb_content_id': mongo_content_id
        }), 201

    except Exception as e:
        db.session.rollback() # 오류 발생 시 MariaDB 트랜잭션 롤백
        current_app.logger.error(f"게시글 생성 중 예상치 못한 오류 발생: {e}", exc_info=True)
        return jsonify({'message': '게시글 작성 중 서버 오류가 발생했습니다.'}), 500

# 2. 모든 게시글 조회 (GET)
@community_bp.route('/posts', methods=['GET'])
def get_posts():
    category = request.args.get('category')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)

    query = Post.query
    if category and category != 'all':
        query = query.filter_by(category=category)

    # 최신순 정렬 (기본)
    query = query.order_by(Post.created_at.desc())

    paginated_posts = query.paginate(page=page, per_page=per_page, error_out=False)
    posts = paginated_posts.items

    posts_data = []
    for post in posts:
        # 게시글 본문은 리스트에서 필요 없으므로 제외
        posts_data.append({
            'id': post.id,
            'title': post.title,
            'category': post.category,
            'author_nickname': '익명' if post.is_anonymous else post.author_nickname,
            'views': post.views,
            'likes': post.likes,
            'comment_count': len(post.comments), # 댓글 수 계산
            'created_at': post.created_at.isoformat(),
            'updated_at': post.updated_at.isoformat(),
            'is_anonymous': post.is_anonymous
        })

    return jsonify({
        'posts': posts_data,
        'total_pages': paginated_posts.pages,
        'current_page': paginated_posts.page,
        'total_posts': paginated_posts.total
    }), 200


# 3. 특정 게시글 조회 (GET)
@community_bp.route('/posts/<int:post_id>', methods=['GET'])
def get_post_detail(post_id):
    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({'message': '게시글을 찾을 수 없습니다.'}), 404

    # 조회수 증가
    post.views += 1
    db.session.commit()

    # MongoDB에서 게시글 본문 내용 가져오기
    mongo_content = None
    attachment_paths = []
    if post.mongodb_content_id:
        try:
            mongo_doc = get_mongo_post_content_collection().find_one({'_id': ObjectId(post.mongodb_content_id)})
            if mongo_doc:
                mongo_content = mongo_doc.get('content')
                attachment_paths = mongo_doc.get('attachment_paths', [])
                current_app.logger.debug(f"MongoDB에서 본문 로드 성공: Post ID {post_id}, MongoDB ID {post.mongodb_content_id}")
            else:
                current_app.logger.warning(f"MongoDB에서 해당 ID의 본문 문서({post.mongodb_content_id})를 찾을 수 없습니다.")
        except Exception as e:
            current_app.logger.error(f"MongoDB에서 본문 로드 중 오류 발생: {e}", exc_info=True)
            # 오류 발생 시에도 게시글 메타데이터는 반환
    else:
        current_app.logger.warning(f"게시글 {post_id}에 연결된 MongoDB content ID가 없습니다.")


    # 현재 사용자가 이 게시글에 공감했는지 확인 (로그인된 경우)
    # g.user_id에 직접 접근하기 전에 속성 존재 여부 확인
    user_id_from_g = getattr(g, 'user_id', None)
    user_liked = False
    if user_id_from_g: # ⭐ 수정: getattr 사용
        existing_like = PostLike.query.filter_by(user_id=user_id_from_g, post_id=post_id).first()
        if existing_like:
            user_liked = True

    post_data = {
        'id': post.id,
        'title': post.title,
        'category': post.category,
        'content': mongo_content, # MongoDB에서 가져온 본문 내용
        'attachment_paths': attachment_paths, # MongoDB에서 가져온 첨부파일 경로
        'author_id': post.author_id, # 작성자 ID 추가
        'author_nickname': '익명' if post.is_anonymous else post.author_nickname,
        'views': post.views,
        'likes': post.likes,
        'created_at': post.created_at.isoformat(),
        'updated_at': post.updated_at.isoformat(),
        'is_anonymous': post.is_anonymous,
        'user_liked': user_liked # 사용자가 좋아요 눌렀는지 여부
    }
    return jsonify(post_data), 200

# 4. 게시글 수정 (PUT)
@community_bp.route('/posts/<int:post_id>', methods=['PUT'])
@token_required
@roles_required('일반 사용자', '에디터', '운영자', '관리자') # 게시글 수정 권한
def update_post(post_id):
    try:
        post = db.session.get(Post, post_id)
        if not post:
            current_app.logger.warning(f"게시글 수정 실패: Post ID {post_id}를 찾을 수 없습니다.")
            return jsonify({'message': '게시글을 찾을 수 없습니다.'}), 404

        # 권한 확인: 본인 게시글이거나 관리자/운영자/에디터만 수정 가능
        user_id = g.user_id
        if post.author_id != user_id and not any(role in g.user_roles for role in ['관리자', '운영자', '에디터']):
            current_app.logger.warning(f"권한 없음: 사용자 {user_id}가 게시글 {post_id}를 수정하려 했으나 권한이 없습니다.")
            return jsonify({'message': '이 게시글을 수정할 권한이 없습니다.'}), 403

        title = request.form.get('title')
        category = request.form.get('category')
        content = request.form.get('content') # 게시글 본문 (HTML)
        is_anonymous = request.form.get('is_anonymous') == 'true'
        
        # 기존 첨부파일 유지 여부 (JSON 문자열로 넘어옴)
        # 예: '["/static/uploads/community/abc.png", "/static/uploads/community/def.jpg"]'
        existing_attachments_json = request.form.get('existing_attachments', '[]')
        try:
            existing_attachments = json.loads(existing_attachments_json)
        except json.JSONDecodeError:
            current_app.logger.error(f"existing_attachments 파싱 오류: {existing_attachments_json}")
            existing_attachments = []

        current_app.logger.debug(f"게시글 수정 요청: Post ID={post_id}, title={title}, category={category}, is_anonymous={is_anonymous}")
        current_app.logger.debug(f"게시글 본문 길이: {len(content) if content else 0}")
        current_app.logger.debug(f"기존 첨부파일: {existing_attachments}")

        if not title or not category or not content:
            current_app.logger.warning("필수 필드 누락: 제목, 카테고리, 내용 중 하나 이상이 없습니다.")
            return jsonify({'message': '제목, 카테고리, 내용을 모두 입력해주세요.'}), 400

        # 1. MongoDB 게시글 본문 업데이트 또는 새로 생성
        new_attachment_paths = []
        if 'attachments' in request.files:
            for file in request.files.getlist('attachments'):
                if file.filename == '':
                    continue
                unique_filename = generate_unique_filename(secure_filename(file.filename))
                file_path = os.path.join(UPLOAD_FOLDER, unique_filename)
                os.makedirs(UPLOAD_FOLDER, exist_ok=True)
                file.save(file_path)
                new_attachment_paths.append(f'/static/uploads/community/{unique_filename}')
            current_app.logger.debug(f"새 첨부 파일 저장 완료: {new_attachment_paths}")

        # 기존 첨부파일과 새로 추가된 첨부파일 병합
        final_attachment_paths = list(set(existing_attachments + new_attachment_paths))
        current_app.logger.debug(f"최종 첨부파일 목록: {final_attachment_paths}")

        mongo_content_id = post.mongodb_content_id
        if mongo_content_id:
            try:
                # 기존 MongoDB 문서 업데이트
                get_mongo_post_content_collection().update_one(
                    {'_id': ObjectId(mongo_content_id)},
                    {'$set': {'content': content, 'attachment_paths': final_attachment_paths, 'updated_at': datetime.datetime.utcnow()}}
                )
                current_app.logger.info(f"MongoDB 게시글 본문 업데이트 성공. MongoDB ID: {mongo_content_id}")
            except Exception as e:
                current_app.logger.error(f"MongoDB 업데이트 중 오류 발생: {e}", exc_info=True)
                return jsonify({'message': '게시글 본문 업데이트 중 오류가 발생했습니다.'}), 500
        else:
            # MongoDB content ID가 없으면 새로 생성
            mongo_post_content = MongoPostContent(content=content, attachment_paths=final_attachment_paths)
            try:
                inserted_mongo_doc = get_mongo_post_content_collection().insert_one(mongo_post_content.to_dict())
                mongo_content_id = str(inserted_mongo_doc.inserted_id)
                post.mongodb_content_id = mongo_content_id # MariaDB에도 업데이트
                current_app.logger.info(f"MongoDB 게시글 본문 새로 생성 성공. MongoDB ID: {mongo_content_id}")
            except Exception as e:
                current_app.logger.error(f"MongoDB 새로 생성 중 오류 발생: {e}", exc_info=True)
                return jsonify({'message': '게시글 본문 저장 중 오류가 발생했습니다.'}), 500

        # 2. MariaDB 게시글 메타데이터 업데이트
        post.title = title
        post.category = category
        post.is_anonymous = is_anonymous
        post.updated_at = datetime.datetime.utcnow() # 업데이트 시간 갱신
        
        # 닉네임 업데이트 (수정 시에도 닉네임이 변경될 수 있으므로)
        post.author_nickname = g.nickname if g.nickname else g.username if g.username else "알 수 없음"

        db.session.commit()
        current_app.logger.info(f"MariaDB 게시글 메타데이터 업데이트 성공. Post ID: {post.id}")

        return jsonify({
            'message': '게시글이 성공적으로 수정되었습니다!',
            'post_id': post.id,
            'mongodb_content_id': mongo_content_id
        }), 200

    except Exception as e:
        db.session.rollback() # 오류 발생 시 MariaDB 트랜잭션 롤백
        current_app.logger.error(f"게시글 수정 중 예상치 못한 오류 발생: {e}", exc_info=True)
        return jsonify({'message': '게시글 수정 중 서버 오류가 발생했습니다.'}), 500


# 5. 게시글 삭제 (DELETE)
@community_bp.route('/posts/<int:post_id>', methods=['DELETE'])
@token_required
@roles_required('일반 사용자', '운영자', '관리자') # 게시글 삭제 권한 (일반 사용자는 본인 글만)
def delete_post(post_id):
    try:
        post = db.session.get(Post, post_id)
        if not post:
            return jsonify({'message': '게시글을 찾을 수 없습니다.'}), 404

        user_id = g.user_id
        if post.author_id != user_id and not ('관리자' in g.user_roles or '운영자' in g.user_roles):
            return jsonify({'message': '이 게시글을 삭제할 권한이 없습니다.'}), 403

        # MongoDB에서 본문 내용 삭제
        if post.mongodb_content_id:
            try:
                get_mongo_post_content_collection().delete_one({'_id': ObjectId(post.mongodb_content_id)})
                current_app.logger.info(f"MongoDB 본문 삭제 성공: MongoDB ID {post.mongodb_content_id}")
            except Exception as e:
                current_app.logger.error(f"MongoDB 본문 삭제 중 오류 발생: {e}", exc_info=True)
                # MongoDB 삭제 실패해도 MariaDB 삭제는 진행 (데이터 일관성 유지 노력)

        # MariaDB에서 게시글 삭제
        db.session.delete(post)
        db.session.commit()
        current_app.logger.info(f"MariaDB 게시글 삭제 성공: Post ID {post_id}")

        return jsonify({'message': '게시글이 성공적으로 삭제되었습니다!'}), 200

    except Exception as e:
        db.session.rollback() # 오류 발생 시 MariaDB 트랜잭션 롤백
        current_app.logger.error(f"게시글 삭제 중 예상치 못한 오류 발생: {e}", exc_info=True)
        return jsonify({'message': '게시글 삭제 중 서버 오류가 발생했습니다.'}), 500


# 1. 댓글 작성 (POST)
@community_bp.route('/posts/<int:post_id>/comments', methods=['POST'])
@token_required
def create_comment(post_id):
    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({'message': '게시글을 찾을 수 없습니다.'}), 404

    data = request.get_json()
    content = data.get('content')

    if not content:
        return jsonify({'message': '댓글 내용을 입력해주세요.'}), 400

    new_comment = Comment(
        post_id=post_id,
        author_id=g.user_id,
        author_nickname=g.nickname if g.nickname else g.username if g.username else "알 수 없음",
        content=content
    )
    db.session.add(new_comment)
    db.session.commit()

    return jsonify({'message': '댓글이 성공적으로 작성되었습니다!', 'comment_id': new_comment.id}), 201

# 2. 게시글의 모든 댓글 조회 (GET)
@community_bp.route('/posts/<int:post_id>/comments', methods=['GET'])
def get_comments(post_id):
    comments = Comment.query.filter_by(post_id=post_id).order_by(Comment.created_at.asc()).all()
    comments_data = []

    # g.user_id에 직접 접근하기 전에 속성 존재 여부 확인
    user_id_from_g = getattr(g, 'user_id', None) # ⭐ 수정: getattr 사용

    for comment in comments:
        user_liked_comment = False
        if user_id_from_g: # ⭐ 수정: user_id_from_g 사용
            existing_like = CommentLike.query.filter_by(user_id=user_id_from_g, comment_id=comment.id).first()
            if existing_like:
                user_liked_comment = True

        comments_data.append({
            'id': comment.id,
            'author_nickname': comment.author_nickname,
            'content': comment.content,
            'created_at': comment.created_at.isoformat(),
            'updated_at': comment.updated_at.isoformat(),
            'likes': comment.likes,
            'is_author': (comment.author_id == user_id_from_g), # 현재 로그인한 사용자가 작성자인지 여부
            'user_liked': user_liked_comment # 현재 로그인한 사용자가 이 댓글에 좋아요를 눌렀는지 여부
        })
    return jsonify({'comments': comments_data}), 200

# 3. 댓글 삭제 (DELETE)
@community_bp.route('/comments/<int:comment_id>', methods=['DELETE'])
@token_required
def delete_comment(comment_id):
    comment = db.session.get(Comment, comment_id)
    if not comment:
        return jsonify({'message': '댓글을 찾을 수 없습니다.'}), 404

    user_id = g.user_id
    if comment.author_id != user_id and not ('관리자' in g.user_roles or '운영자' in g.user_roles):
        return jsonify({'message': '이 댓글을 삭제할 권한이 없습니다.'}), 403

    db.session.delete(comment)
    db.session.commit()

    return jsonify({'message': '댓글이 성공적으로 삭제되었습니다!'}), 200

# 4. 게시글 공감/추천 (POST)
@community_bp.route('/posts/<int:post_id>/like', methods=['POST'])
@token_required
def like_post(post_id):
    user_id = int(g.user_id)
    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({'message': '게시글을 찾을 수 없습니다.'}), 404

    existing_like = PostLike.query.filter_by(user_id=user_id, post_id=post_id).first()

    if existing_like:
        # 이미 좋아요를 눌렀으면 좋아요 취소
        db.session.delete(existing_like)
        post.likes = post.likes - 1 if post.likes > 0 else 0
        db.session.commit()
        return jsonify({'message': '게시글 좋아요가 취소되었습니다.', 'likes': post.likes}), 200
    else:
        # 좋아요 추가
        new_like = PostLike(user_id=user_id, post_id=post_id)
        db.session.add(new_like)
        post.likes += 1
        db.session.commit()
        return jsonify({'message': '게시글에 좋아요를 눌렀습니다!', 'likes': post.likes}), 200

# 댓글 좋아요/좋아요 취소
@community_bp.route('/comments/<int:comment_id>/like', methods=['POST'])
@token_required
def like_comment(comment_id):
    user_id = int(g.user_id)
    comment = db.session.get(Comment, comment_id)
    if not comment:
        return jsonify({'message': '댓글을 찾을 수 없습니다.'}), 404

    existing_like = CommentLike.query.filter_by(user_id=user_id, comment_id=comment_id).first()

    if existing_like:
        # 이미 좋아요를 눌렀으면 좋아요 취소
        db.session.delete(existing_like)
        comment.likes = comment.likes - 1 if comment.likes > 0 else 0
        db.session.commit()
        return jsonify({'message': '댓글 좋아요가 취소되었습니다.', 'likes': comment.likes}), 200
    else:
        # 좋아요 추가
        new_like = CommentLike(user_id=user_id, comment_id=comment_id)
        db.session.add(new_like)
        comment.likes += 1
        db.session.commit()
        return jsonify({'message': '댓글에 좋아요를 눌렀습니다!', 'likes': comment.likes}), 200

# 게시글 신고
@community_bp.route('/posts/<int:post_id>/report', methods=['POST'])
@token_required
def report_post(post_id):
    # 신고 로직 구현 (예: 신고 테이블에 기록, 관리자에게 알림 등)
    # 여기서는 단순히 성공 메시지만 반환
    return jsonify({'message': '게시글이 신고되었습니다. 관리자가 검토할 예정입니다.'}), 200

# 댓글 신고
@community_bp.route('/comments/<int:comment_id>/report', methods=['POST'])
@token_required
def report_comment(comment_id):
    # 신고 로직 구현
    return jsonify({'message': '댓글이 신고되었습니다. 관리자가 검토할 예정입니다.'}), 200

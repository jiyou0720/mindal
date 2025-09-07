# backend/routes/admin_routes.py
import os
import logging
import sys
from flask import Blueprint, request, jsonify, g, current_app
from backend.extensions import db, mongo
from backend.maria_models import User, Post, Comment, Role, UserRole, Notice, PostLike
from backend.mongo_models import DiaryEntry, MoodEntry, Inquiry, PsychTest, PsychQuestion, PsychTestResult
from backend.routes.auth_routes import token_required, roles_required
from bson.objectid import ObjectId
import datetime
from datetime import timedelta
from collections import Counter
from sqlalchemy import and_
from sqlalchemy.orm import joinedload

admin_bp = Blueprint('admin_api', __name__)

@admin_bp.record_once
def record(state):
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'frontend', 'static', 'uploads', 'admin')
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
        state.app.logger.info(f"ADMIN UPLOAD_FOLDER created: {UPLOAD_FOLDER}")
    else:
        state.app.logger.info(f"ADMIN UPLOAD_FOLDER already exists: {UPLOAD_FOLDER}")

# [수정] 안정적인 MongoDB 연결을 위한 헬퍼 함수
def get_mongo_db():
    db_name = current_app.config.get("MONGO_DBNAME")
    if not db_name or not mongo.cx:
        raise ConnectionError("MongoDB is not configured or connected.")
    return mongo.cx[db_name]

# 대시보드 통계 API
@admin_bp.route('/dashboard/stats', methods=['GET'])
@token_required
@roles_required(['관리자'])
def get_dashboard_stats():
    try:
        db_mongo = get_mongo_db()
        total_users = User.query.count()
        ai_chat_count = db_mongo.chat_history.count_documents({})
        diary_entry_count = db_mongo.diary_entries.count_documents({})
        community_post_count = Post.query.count()

        return jsonify({
            'total_users': total_users,
            'ai_chat_count': ai_chat_count,
            'diary_entry_count': diary_entry_count,
            'community_post_count': community_post_count
        }), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching admin dashboard stats: {e}", exc_info=True)
        return jsonify({'message': '대시보드 통계를 불러오는 데 실패했습니다.'}), 500

# 내 메뉴 아이템 조회
@admin_bp.route('/menu_items/my_menu', methods=['GET'])
@token_required
def get_my_menu_items():
    user_roles = g.user_roles
    if not user_roles:
        return jsonify({'menu_items': []}), 200
    try:
        db_mongo = get_mongo_db()
        assignments_collection = db_mongo.role_menu_assignments
        menu_items_collection = db_mongo.menu_items
        
        assigned_menus = assignments_collection.find({'role_name': {'$in': user_roles}})
        
        all_menu_ids = set()
        for assignment in assigned_menus:
            for menu_id in assignment.get('menu_ids', []):
                all_menu_ids.add(ObjectId(menu_id))

        if not all_menu_ids:
            return jsonify({'menu_items': []}), 200

        menu_items = list(menu_items_collection.find({'_id': {'$in': list(all_menu_ids)}}).sort('order', 1))
        
        for item in menu_items:
            item['_id'] = str(item['_id'])
            
        return jsonify({'menu_items': menu_items}), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching my menu items: {e}", exc_info=True)
        return jsonify({'message': '메뉴를 불러오는 데 실패했습니다.'}), 500


# 모든 메뉴 아이템 조회
@admin_bp.route('/menu_items', methods=['GET'])
@token_required
@roles_required(['관리자'])
def get_all_menu_items():
    try:
        db_mongo = get_mongo_db()
        menu_items_collection = db_mongo.menu_items
        all_items = list(menu_items_collection.find({}).sort('order', 1))
        for item in all_items:
            item['_id'] = str(item['_id'])
        return jsonify({'menu_items': all_items}), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching all menu items: {e}", exc_info=True)
        return jsonify({'message': '메뉴 목록을 불러오는 데 실패했습니다.'}), 500

# 특정 메뉴 아이템 조회
@admin_bp.route('/menu_items/<string:menu_id>', methods=['GET'])
@token_required
@roles_required(['관리자'])
def get_menu_item(menu_id):
    try:
        db_mongo = get_mongo_db()
        menu_item_collection = db_mongo.menu_items
        menu_item = menu_item_collection.find_one({'_id': ObjectId(menu_id)})
        if not menu_item:
            return jsonify({'message': '메뉴 아이템을 찾을 수 없습니다.'}), 404
        menu_item['_id'] = str(menu_item['_id'])
        return jsonify(menu_item), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching menu item {menu_id}: {e}", exc_info=True)
        return jsonify({'message': '메뉴 아이템을 불러오는 데 실패했습니다.'}), 500


# 메뉴 아이템 추가
@admin_bp.route('/menu_items', methods=['POST'])
@token_required
@roles_required(['관리자'])
def add_menu_item():
    data = request.get_json()
    name = data.get('name')
    url = data.get('url')
    icon_class = data.get('icon_class')
    order = data.get('order', 0)
    required_roles = data.get('required_roles', [])

    if not all([name, url]):
        return jsonify({'message': '메뉴 이름과 URL은 필수입니다.'}), 400
    
    try:
        db_mongo = get_mongo_db()
        menu_items_collection = db_mongo.menu_items
        new_menu = {
            'name': name,
            'url': url,
            'icon_class': icon_class,
            'order': order,
            'required_roles': required_roles
        }
        result = menu_items_collection.insert_one(new_menu)
        return jsonify({'message': '메뉴 아이템이 성공적으로 추가되었습니다.', 'id': str(result.inserted_id)}), 201
    except Exception as e:
        current_app.logger.error(f"Error adding menu item: {e}", exc_info=True)
        return jsonify({'message': '메뉴 아이템 추가에 실패했습니다.'}), 500

# 메뉴 아이템 수정
@admin_bp.route('/menu_items/<string:menu_id>', methods=['PUT'])
@token_required
@roles_required(['관리자'])
def update_menu_item(menu_id):
    data = request.get_json()
    
    try:
        db_mongo = get_mongo_db()
        menu_items_collection = db_mongo.menu_items
        update_data = {}
        if 'name' in data: update_data['name'] = data['name']
        if 'url' in data: update_data['url'] = data['url']
        if 'icon_class' in data: update_data['icon_class'] = data['icon_class']
        if 'order' in data: update_data['order'] = data['order']
        if 'required_roles' in data: update_data['required_roles'] = data['required_roles']

        result = menu_items_collection.update_one(
            {'_id': ObjectId(menu_id)},
            {'$set': update_data}
        )

        if result.matched_count == 0:
            return jsonify({'message': '메뉴 아이템을 찾을 수 없습니다.'}), 404
        
        return jsonify({'message': '메뉴 아이템이 성공적으로 업데이트되었습니다.'}), 200
    except Exception as e:
        current_app.logger.error(f"Error updating menu item {menu_id}: {e}", exc_info=True)
        return jsonify({'message': '메뉴 아이템 수정에 실패했습니다.'}), 500

# 메뉴 아이템 삭제
@admin_bp.route('/menu_items/<string:menu_id>', methods=['DELETE'])
@token_required
@roles_required(['관리자'])
def delete_menu_item(menu_id):
    try:
        db_mongo = get_mongo_db()
        menu_items_collection = db_mongo.menu_items
        result = menu_items_collection.delete_one({'_id': ObjectId(menu_id)})
        if result.deleted_count == 0:
            return jsonify({'message': '메뉴 아이템을 찾을 수 없습니다.'}), 404
        return jsonify({'message': '메뉴 아이템이 성공적으로 삭제되었습니다.'}), 200
    except Exception as e:
        current_app.logger.error(f"Error deleting menu item {menu_id}: {e}", exc_info=True)
        return jsonify({'message': '메뉴 아이템 삭제에 실패했습니다.'}), 500


# 모든 역할 조회 API
@admin_bp.route('/roles', methods=['GET'])
@token_required
@roles_required(['관리자'])
def get_all_roles():
    try:
        all_roles = Role.query.all()
        roles_data = [{'id': role.id, 'name': role.name} for role in all_roles]
        return jsonify({'roles': roles_data}), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching all roles: {e}", exc_info=True)
        return jsonify({'message': '역할 목록을 불러오는 데 실패했습니다.'}), 500


# 특정 역할의 메뉴 설정 조회 API
@admin_bp.route('/roles/<int:role_id>/menu_configs', methods=['GET'])
@token_required
@roles_required(['관리자'])
def get_role_menu_configs(role_id):
    try:
        role = db.session.get(Role, role_id)
        if not role:
            return jsonify({'message': '역할을 찾을 수 없습니다.'}), 404

        role_name = role.name
        
        db_mongo = get_mongo_db()
        assignments_collection = db_mongo.role_menu_assignments
        assignment = assignments_collection.find_one({'role_name': role_name})

        if not assignment:
            return jsonify({'menu_item_ids': []}), 200

        menu_item_ids = assignment.get('menu_ids', [])
        
        return jsonify({'menu_item_ids': menu_item_ids}), 200

    except Exception as e:
        current_app.logger.error(f"Error fetching role menu configs for role_id {role_id}: {e}", exc_info=True)
        return jsonify({'message': '역할 메뉴 설정을 불러오는 데 실패했습니다.'}), 500


# 특정 역할의 메뉴 설정 업데이트 API
@admin_bp.route('/roles/<int:role_id>/menu_configs', methods=['PUT'])
@token_required
@roles_required(['관리자'])
def update_role_menu_configs(role_id):
    data = request.get_json()
    menu_item_ids = data.get('menu_item_ids', [])

    if not isinstance(menu_item_ids, list):
        return jsonify({'message': 'menu_item_ids는 리스트 형태여야 합니다.'}), 400

    try:
        role = db.session.get(Role, role_id)
        if not role:
            return jsonify({'message': '역할을 찾을 수 없습니다.'}), 404

        role_name = role.name
        
        db_mongo = get_mongo_db()
        assignments_collection = db_mongo.role_menu_assignments
        
        result = assignments_collection.update_one(
            {'role_name': role_name},
            {'$set': {'menu_ids': menu_item_ids}},
            upsert=True
        )
        
        if result.matched_count == 0 and result.upserted_id is None:
            return jsonify({'message': '메뉴 할당 업데이트에 실패했습니다.'}), 500

        return jsonify({'message': '메뉴 할당이 성공적으로 업데이트되었습니다.'}), 200

    except Exception as e:
        current_app.logger.error(f"Error updating role menu configs for role_id {role_id}: {e}", exc_info=True)
        return jsonify({'message': '역할 메뉴 할당 업데이트에 실패했습니다.'}), 500

# 사용자 관리 API
@admin_bp.route('/users', methods=['GET'])
@token_required
@roles_required(['관리자'])
def get_all_users():
    try:
        users = User.query.options(joinedload(User.roles)).all()
        users_data = [user.to_dict() for user in users]
        return jsonify({'users': users_data}), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching all users: {e}", exc_info=True)
        return jsonify({'message': '사용자 목록을 불러오는 데 실패했습니다.'}), 500

# 사용자 역할 업데이트
@admin_bp.route('/users/<int:user_id>/roles', methods=['PUT'])
@token_required
@roles_required(['관리자'])
def update_user_roles(user_id):
    data = request.get_json()
    new_role_names = data.get('roles', [])

    if not isinstance(new_role_names, list):
        return jsonify({'message': '역할은 리스트 형태여야 합니다.'}), 400

    try:
        user = db.session.get(User, user_id)
        if not user:
            return jsonify({'message': '사용자를 찾을 수 없습니다.'}), 404

        user.roles.clear()
        
        for role_name in new_role_names:
            role = Role.query.filter_by(name=role_name).first()
            if role:
                user.roles.append(role)
        db.session.commit()
        return jsonify({'message': '사용자 역할이 성공적으로 업데이트되었습니다.'}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating roles for user {user_id}: {e}", exc_info=True)
        return jsonify({'message': '사용자 역할 업데이트에 실패했습니다.'}), 500

# 사용자 강제 삭제
@admin_bp.route('/users/<int:user_id>/force_delete', methods=['DELETE'])
@token_required
@roles_required(['관리자'])
def force_delete_user(user_id):
    try:
        user = db.session.get(User, user_id)
        if not user:
            return jsonify({'message': '사용자를 찾을 수 없습니다.'}), 404
        
        db_mongo = get_mongo_db()
        
        posts_by_user = Post.query.filter_by(user_id=user_id).all()
        for post in posts_by_user:
            if post.mongo_content_id:
                db_mongo.post_contents.delete_one({'_id': ObjectId(post.mongo_content_id)})
        
        db_mongo.diary_entries.delete_many({'user_id': user_id})
        db_mongo.mood_entries.delete_many({'user_id': user_id})

        db.session.delete(user)
        db.session.commit()

        return jsonify({'message': '사용자 및 관련 데이터가 성공적으로 삭제되었습니다.'}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error force deleting user {user_id}: {e}", exc_info=True)
        return jsonify({'message': '사용자 삭제에 실패했습니다.'}), 500

# 공지사항 관련 API들은 MongoDB를 사용하지 않으므로 수정 불필요

# DB 관리 API
@admin_bp.route('/db_records', methods=['GET'])
@token_required
@roles_required(['관리자', '개발자', '연구자'])
def get_db_records():
    try:
        db_mongo = get_mongo_db()
        records_data = []

        # 일기 기록
        diary_entries = db_mongo.diary_entries.find({}).sort('created_at', -1).limit(100)
        for entry in diary_entries:
            entry['_id'] = str(entry['_id'])
            user = db.session.get(User, entry.get('user_id'))
            username = user.username if user else 'Unknown'
            user_email = user.email if user else 'Unknown'
            records_data.append({
                'id': entry['_id'],
                'user_id': entry.get('user_id'),
                'user_username': username,
                'user_email': user_email,
                'type': '일기',
                'summary': entry.get('title', '제목 없음'),
                'timestamp': entry.get('created_at', datetime.datetime.utcnow()).isoformat(),
                'conversation': [{'role': '일기 내용', 'text': entry.get('content', '내용 없음')}]
            })
        
        # 감정 기록
        mood_entries = db_mongo.mood_entries.find({}).sort('timestamp', -1).limit(100)
        for entry in mood_entries:
            entry['_id'] = str(entry['_id'])
            user = db.session.get(User, entry.get('user_id'))
            username = user.username if user else 'Unknown'
            user_email = user.email if user else 'Unknown'
            records_data.append({
                'id': entry['_id'],
                'user_id': entry.get('user_id'),
                'user_username': username,
                'user_email': user_email,
                'type': '감정 기록',
                'summary': f"감정: {entry.get('mood', '알 수 없음')}",
                'timestamp': entry.get('timestamp', datetime.datetime.utcnow()).isoformat(),
                'conversation': [{'role': '감정', 'text': entry.get('mood', '알 수 없음')}]
            })

        # 최신순으로 정렬
        records_data.sort(key=lambda x: x['timestamp'], reverse=True)

        return jsonify({'records': records_data}), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching DB records: {e}", exc_info=True)
        return jsonify({'message': 'DB 기록을 불러오는 데 실패했습니다.'}), 500

# 게시글 관리 API
@admin_bp.route('/posts', methods=['GET'])
@token_required
@roles_required(['관리자', '운영자'])
def get_all_posts_admin():
    try:
        db_mongo = get_mongo_db()
        posts_query = db.session.query(
            Post,
            db.func.count(db.distinct(Comment.id)).label('comment_count'),
            db.func.count(db.distinct(PostLike.user_id)).label('like_count')
        ).outerjoin(Comment, Post.id == Comment.post_id)\
         .outerjoin(PostLike, Post.id == PostLike.post_id)\
         .group_by(Post.id)\
         .options(joinedload(Post.author))\
         .order_by(Post.created_at.desc()).all()

        posts_data = []
        for post, comment_count, like_count in posts_query:
            post_content = db_mongo.post_contents.find_one({'_id': ObjectId(post.mongo_content_id)})
            content_text = post_content.get('content', '내용 없음') if post_content else '내용 없음'

            posts_data.append({
                'id': post.id,
                'title': post.title,
                'content': content_text,
                'author_id': post.user_id,
                'author_username': post.author.username if post.author else '알 수 없음',
                'author_nickname': post.author.nickname if post.author else '탈퇴한 사용자',
                'is_anonymous': post.is_anonymous,
                'category': post.category,
                'views': post.views,
                'likes': like_count,
                'comment_count': comment_count,
                'report_count': 0,
                'is_suspended': post.is_suspended,
                'suspended_until': post.suspended_until.isoformat() if post.suspended_until else None,
                'created_at': post.created_at.isoformat() if post.created_at else None,
                'updated_at': post.updated_at.isoformat() if post.updated_at else None
            })
        return jsonify({'posts': posts_data}), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching all posts for admin: {e}", exc_info=True)
        return jsonify({'message': '게시글 목록을 불러오는 데 실패했습니다.'}), 500
# 특정 게시글 상세 조회 (관리자용)
@admin_bp.route('/posts/<int:post_id>', methods=['GET'])
@token_required
@roles_required(['관리자', '운영자'])
def get_post_detail_admin(post_id):
    try:
        post = db.session.query(
            Post,
            db.func.count(db.distinct(Comment.id)).label('comment_count'),
            db.func.count(db.distinct(PostLike.user_id)).label('like_count')
        ).outerjoin(Comment, Post.id == Comment.post_id)\
         .outerjoin(PostLike, Post.id == PostLike.post_id)\
         .filter(Post.id == post_id)\
         .group_by(Post.id)\
         .options(joinedload(Post.author))\
         .first()

        if not post:
            return jsonify({'message': '게시글을 찾을 수 없습니다.'}), 404
        
        post_obj, comment_count, like_count = post
        
        author_nickname = post_obj.author.nickname if post_obj.author else '탈퇴한 사용자'
        author_username = post_obj.author.username if post_obj.author else '알 수 없음'

        # MongoDB에서 본문 내용 가져오기
        post_content = mongo.db.post_contents.find_one({'_id': ObjectId(post_obj.mongo_content_id)})
        content_text = post_content.get('content', '내용 없음') if post_content else '내용 없음'

        # TODO: 신고 내역 가져오기 (Report 모델 구현 시)
        reports = [] # 예시: [{'type': '욕설', 'reason': '심한 욕설', 'timestamp': '2025-07-25T10:00:00Z'}]

        return jsonify({
            'id': post_obj.id,
            'title': post_obj.title,
            'content': content_text,
            'author_id': post_obj.user_id,
            'author_username': author_username,
            'author_nickname': author_nickname,
            'is_anonymous': post_obj.is_anonymous,
            'category': post_obj.category,
            'views': post_obj.views,
            'likes': like_count,
            'comment_count': comment_count,
            'report_count': len(reports), # TODO: 실제 신고 수로 대체
            'reports': reports, # 신고 내역
            'is_suspended': post_obj.is_suspended, # 정지 여부 추가
            'suspended_until': post_obj.suspended_until.isoformat() if post_obj.suspended_until else None, # 정지 해제 일시 추가
            'created_at': post_obj.created_at.isoformat() if post_obj.created_at else None,
            'updated_at': post_obj.updated_at.isoformat() if post_obj.updated_at else None
        }), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching post detail {post_id} for admin: {e}", exc_info=True)
        return jsonify({'message': '게시글 상세 정보를 불러오는 데 실패했습니다.'}), 500

# 게시글 삭제 (관리자용)
@admin_bp.route('/posts/<int:post_id>/delete', methods=['DELETE'])
@token_required
@roles_required(['관리자', '운영자'])
def delete_post_admin(post_id):
    try:
        post = db.session.get(Post, post_id)
        if not post:
            return jsonify({'message': '게시글을 찾을 수 없습니다.'}), 404
        
        # MongoDB 본문 내용 먼저 삭제
        if post.mongo_content_id:
            mongo.db.post_contents.delete_one({'_id': ObjectId(post.mongo_content_id)})

        db.session.delete(post)
        db.session.commit()
        return jsonify({'message': '게시글이 성공적으로 삭제되었습니다.'}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting post {post_id}: {e}", exc_info=True)
        return jsonify({'message': '게시글 삭제에 실패했습니다.'}), 500

# NEW: 게시글 정지/복구 기능
@admin_bp.route('/posts/<int:post_id>/toggle_suspension', methods=['PUT'])
@token_required
@roles_required(['관리자', '운영자'])
def toggle_post_suspension(post_id): # post_id를 인자로 받도록 수정
    # 'suspend'가 True면 정지, False면 해제
    # 정지 기간 (시간 단위), suspend가 True일 때만 유효
    # post_id는 URL 경로에서 가져옴

    data = request.get_json()
    suspend = data.get('suspend', None) 
    duration_hours = data.get('duration_hours', None) 

    if suspend is None:
        return jsonify({'message': '정지 여부(suspend)를 지정해야 합니다.'}), 400

    try:
        post = db.session.get(Post, post_id)
        if not post:
            return jsonify({'message': '게시글을 찾을 수 없습니다.'}), 404
        
        if suspend: # 게시글 정지
            if duration_hours is None or not isinstance(duration_hours, (int, float)) or duration_hours <= 0:
                return jsonify({'message': '유효한 정지 기간(시간)을 입력해야 합니다.'}), 400
            
            post.is_suspended = True
            post.suspended_until = datetime.datetime.utcnow() + datetime.timedelta(hours=duration_hours)
            message = f"게시글이 성공적으로 {duration_hours}시간 동안 정지되었습니다."
        else: # 게시글 정지 해제
            post.is_suspended = False
            post.suspended_until = None
            message = "게시글 정지가 성공적으로 해제되었습니다."
        
        db.session.commit()
        return jsonify({'message': message, 'is_suspended': post.is_suspended, 'suspended_until': post.suspended_until.isoformat() if post.suspended_until else None}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error toggling suspension for post {post_id}: {e}", exc_info=True)
        return jsonify({'message': '게시글 정지/해제 처리에 실패했습니다.'}), 500


# NEW: CMS (콘텐츠 관리 시스템) APIs
# CMS 콘텐츠 조회 (유형별)
@admin_bp.route('/cms/<string:content_type>', methods=['GET'])
@token_required
@roles_required(['관리자'])
def get_cms_content(content_type):
    # content_type은 'psych_test_questions', 'chatbot_responses', 'risk_detection_materials' 등
    valid_types = ['psych_test_questions', 'chatbot_responses', 'risk_detection_materials']
    if content_type not in valid_types:
        return jsonify({'message': '유효하지 않은 콘텐츠 유형입니다.'}), 400

    try:
        # 각 유형별로 별도의 컬렉션을 사용하거나, 단일 컬렉션 내에서 type 필드로 구분
        # 여기서는 단일 컬렉션 'cms_content'를 사용하고 'type' 필드로 구분
        cms_collection = mongo.db.cms_content
        content_items = list(cms_collection.find({'type': content_type}).sort('created_at', 1))
        
        for item in content_items:
            item['_id'] = str(item['_id'])
            # MongoDB ObjectId를 문자열로 변환
            if 'options' in item and isinstance(item['options'], list):
                # 옵션이 리스트 형태면 그대로 사용, 아니면 빈 리스트
                pass
            else:
                item['options'] = [] # 기본값 설정
        
        return jsonify({'content': content_items}), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching CMS content for type {content_type}: {e}", exc_info=True)
        return jsonify({'message': '콘텐츠를 불러오는 데 실패했습니다.'}), 500

# 특정 CMS 콘텐츠 조회
@admin_bp.route('/cms/<string:content_type>/<string:item_id>', methods=['GET'])
@token_required
@roles_required(['관리자'])
def get_cms_item(content_type, item_id):
    valid_types = ['psych_test_questions', 'chatbot_responses', 'risk_detection_materials']
    if content_type not in valid_types:
        return jsonify({'message': '유효하지 않은 콘텐츠 유형입니다.'}), 400

    try:
        cms_collection = mongo.db.cms_content
        item = cms_collection.find_one({'_id': ObjectId(item_id), 'type': content_type})
        if not item:
            return jsonify({'message': '콘텐츠를 찾을 수 없습니다.'}), 404
        
        item['_id'] = str(item['_id'])
        if 'options' in item and isinstance(item['options'], list):
            pass
        else:
            item['options'] = []
        
        return jsonify(item), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching CMS item {item_id} of type {content_type}: {e}", exc_info=True)
        return jsonify({'message': '콘텐츠를 불러오는 데 실패했습니다.'}), 500

# CMS 콘텐츠 추가
@admin_bp.route('/cms/<string:content_type>', methods=['POST'])
@token_required
@roles_required(['관리자'])
def add_cms_content(content_type):
    valid_types = ['psych_test_questions', 'chatbot_responses', 'risk_detection_materials']
    if content_type not in valid_types:
        return jsonify({'message': '유효하지 않은 콘텐츠 유형입니다.'}), 400

    data = request.get_json()
    title = data.get('title')
    content = data.get('content')
    options = data.get('options', []) # 심리 테스트 문항용

    if not all([title, content]):
        return jsonify({'message': '제목과 내용은 필수입니다.'}), 400
    
    try:
        cms_collection = mongo.db.cms_content
        new_item = {
            'type': content_type,
            'title': title,
            'content': content,
            'created_at': datetime.datetime.utcnow(),
            'updated_at': datetime.datetime.utcnow(),
            'user_id': g.user_id # 작성자 ID
        }
        if content_type == 'psych_test_questions':
            new_item['options'] = options # 옵션 필드 추가

        result = cms_collection.insert_one(new_item)
        return jsonify({'message': '콘텐츠가 성공적으로 추가되었습니다.', 'id': str(result.inserted_id)}), 201
    except Exception as e:
        current_app.logger.error(f"Error adding CMS content of type {content_type}: {e}", exc_info=True)
        return jsonify({'message': '콘텐츠 추가에 실패했습니다.'}), 500

# CMS 콘텐츠 수정
@admin_bp.route('/cms/<string:content_type>/<string:item_id>', methods=['PUT'])
@token_required
@roles_required(['관리자'])
def update_cms_content(content_type, item_id):
    valid_types = ['psych_test_questions', 'chatbot_responses', 'risk_detection_materials']
    if content_type not in valid_types:
        return jsonify({'message': '유효하지 않은 콘텐츠 유형입니다.'}), 400

    data = request.get_json()
    
    try:
        cms_collection = mongo.db.cms_content
        update_data = {
            'updated_at': datetime.datetime.utcnow()
        }
        if 'title' in data: update_data['title'] = data['title']
        if 'content' in data: update_data['content'] = data['content']
        if content_type == 'psych_test_questions' and 'options' in data:
            update_data['options'] = data['options']

        result = cms_collection.update_one(
            {'_id': ObjectId(item_id), 'type': content_type},
            {'$set': update_data}
        )

        if result.matched_count == 0:
            return jsonify({'message': '콘텐츠를 찾을 수 없습니다.'}), 404
        
        return jsonify({'message': '콘텐츠가 성공적으로 업데이트되었습니다.'}), 200
    except Exception as e:
        current_app.logger.error(f"Error updating CMS content {item_id} of type {content_type}: {e}", exc_info=True)
        return jsonify({'message': '콘텐츠 수정에 실패했습니다.'}), 500

# CMS 콘텐츠 삭제
@admin_bp.route('/cms/<string:content_type>/<string:item_id>', methods=['DELETE'])
@token_required
@roles_required(['관리자'])
def delete_cms_content(content_type, item_id):
    valid_types = ['psych_test_questions', 'chatbot_responses', 'risk_detection_materials']
    if content_type not in valid_types:
        return jsonify({'message': '유효하지 않은 콘텐츠 유형입니다.'}), 400

    try:
        cms_collection = mongo.db.cms_content
        result = cms_collection.delete_one({'_id': ObjectId(item_id), 'type': content_type})
        if result.deleted_count == 0:
            return jsonify({'message': '콘텐츠를 찾을 수 없습니다.'}), 404
        return jsonify({'message': '콘텐츠가 성공적으로 삭제되었습니다.'}), 200
    except Exception as e:
        current_app.logger.error(f"Error deleting CMS content {item_id}: {e}", exc_info=True)
        return jsonify({'message': '콘텐츠 삭제에 실패했습니다.'}), 500


# NEW: 데이터 분석 및 통계 대시보드 APIs
# 감정 분포 데이터 (기존 graph_routes의 복사본, 관리자용)
@admin_bp.route('/analytics/mood_distribution', methods=['GET'])
@token_required
@roles_required(['관리자', '연구자'])
def get_analytics_mood_distribution():
    try:
        # 모든 사용자의 감정 기록을 가져와 분석 (관리자/연구자용)
        mood_entries = mongo.db.mood_entries.find({})
        moods = [entry['mood'] for entry in mood_entries]
        mood_counts = Counter(moods)
        
        data = {
            'labels': list(mood_counts.keys()),
            'datasets': [{
                'label': '감정 분포',
                'data': list(mood_counts.values()),
                'backgroundColor': [
                    'rgba(255, 99, 132, 0.7)', 'rgba(54, 162, 235, 0.7)', 
                    'rgba(255, 206, 86, 0.7)', 'rgba(75, 192, 192, 0.7)',
                    'rgba(153, 102, 255, 0.7)', 'rgba(255, 159, 64, 0.7)',
                    'rgba(199, 199, 199, 0.7)'
                ],
                'borderColor': '#fff',
                'borderWidth': 1
            }]
        }
        return jsonify(data), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching analytics mood distribution: {e}", exc_info=True)
        return jsonify({'message': '감정 분포 데이터를 불러오는 데 실패했습니다.'}), 500

# 월별 일기 작성량 (관리자용)
@admin_bp.route('/analytics/diary_entry_counts', methods=['GET'])
@token_required
@roles_required(['관리자', '연구자'])
def get_analytics_diary_entry_counts():
    try:
        # 모든 사용자의 일기 작성 날짜를 가져와 월별로 집계
        pipeline = [
            {
                '$group': {
                    '_id': { '$dateToString': { 'format': '%Y-%m', 'date': '$created_at' } },
                    'count': { '$sum': 1 }
                }
            },
            {
                '$sort': { '_id': 1 }
            }
        ]
        results = list(mongo.db.diary_entries.aggregate(pipeline))

        labels = [res['_id'] for res in results]
        counts = [res['count'] for res in results]

        data = {
            'labels': labels,
            'datasets': [{
                'label': '월별 일기 작성량',
                'data': counts,
                'backgroundColor': 'rgba(54, 162, 235, 0.8)',
                'borderColor': 'rgba(54, 162, 235, 1)',
                'borderWidth': 1
            }]
        }
        return jsonify(data), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching analytics diary entry counts: {e}", exc_info=True)
        return jsonify({'message': '월별 일기 작성량 데이터를 불러오는 데 실패했습니다.'}), 500

# 상위 키워드 빈도 (관리자용)
@admin_bp.route('/analytics/top_keywords', methods=['GET'])
@token_required
@roles_required(['관리자', '연구자'])
def get_analytics_top_keywords():
    try:
        # 모든 일기에서 키워드를 가져와 집계 (현재 DiaryEntry 모델에 keywords 필드가 없으므로 임시)
        # TODO: DiaryEntry 모델에 keywords 필드 추가 후 실제 데이터 사용
        # 임시 데이터:
        all_keywords = [
            "스트레스", "불안", "행복", "우울", "친구", "가족", "직장", "학교", "미래", "긍정",
            "스트레스", "불안", "행복", "우울", "친구", "가족", "직장", "스트레스", "행복", "긍정"
        ]
        # 실제 구현 시:
        # diary_entries = mongo.db.diary_entries.find({})
        # all_keywords = []
        # for entry in diary_entries:
        #     all_keywords.extend(entry.get('keywords', [])) # keywords 필드가 있다고 가정

        keyword_counts = Counter(all_keywords)
        top_10_keywords = keyword_counts.most_common(10)
        
        labels = [item[0] for item in top_10_keywords]
        values = [item[1] for item in top_10_keywords]

        data = {
            'labels': labels,
            'datasets': [{
                'label': '키워드 빈도',
                'data': values,
                'backgroundColor': 'rgba(75, 192, 192, 0.8)',
                'borderColor': 'rgba(75, 192, 192, 1)',
                'borderWidth': 1
            }]
        }
        return jsonify(data), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching analytics top keywords: {e}", exc_info=True)
        return jsonify({'message': '상위 키워드 데이터를 불러오는 데 실패했습니다.'}), 500


# NEW: 챗봇 피드백/별점 관리 APIs (admin_routes에서 제거됨)
# 이 부분은 chat_routes.py로 이동했습니다.


# NEW: 문의사항 관리 API
@admin_bp.route('/inquiries', methods=['GET'])
@token_required
@roles_required(['관리자', '운영자'])
def get_all_inquiries_admin():
    """모든 문의사항을 조회합니다 (관리자/운영자용)."""
    try:
        inquiries_collection = mongo.db.inquiries
        all_inquiries = list(inquiries_collection.find({}).sort('created_at', -1))
        
        for inquiry in all_inquiries:
            inquiry['_id'] = str(inquiry['_id'])
            # created_at과 replied_at이 datetime 객체인 경우 ISO 포맷 문자열로 변환
            if 'created_at' in inquiry and isinstance(inquiry['created_at'], datetime.datetime):
                inquiry['created_at'] = inquiry['created_at'].isoformat()
            if 'replied_at' in inquiry and isinstance(inquiry['replied_at'], datetime.datetime):
                inquiry['replied_at'] = inquiry['replied_at'].isoformat()
            
            # user_id를 사용하여 사용자 정보 가져오기 (MariaDB)
            user = db.session.get(User, inquiry.get('user_id'))
            inquiry['user_email'] = user.email if user else 'Unknown' # 이메일 필드 추가
            inquiry['user_username'] = user.username if user else 'Unknown' # 사용자 이름도 명확히
            inquiry['user_nickname'] = user.nickname if user else 'Unknown' # 닉네임도 명확히

            # 답변한 관리자 정보도 필요하다면 MariaDB에서 조회 가능
            if inquiry.get('replied_by_user_id'):
                replier = db.session.get(User, inquiry['replied_by_user_id'])
                inquiry['replied_by_username'] = replier.username if replier else 'Unknown'
                inquiry['replied_by_nickname'] = replier.nickname if replier else 'Unknown'
            else:
                inquiry['replied_by_username'] = None
                inquiry['replied_by_nickname'] = None
            
        return jsonify({'inquiries': all_inquiries}), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching all inquiries for admin: {e}", exc_info=True)
        return jsonify({'message': '문의사항 목록을 불러오는 데 실패했습니다.'}), 500

@admin_bp.route('/inquiries/<string:inquiry_id>', methods=['GET'])
@token_required
@roles_required(['관리자', '운영자'])
def get_inquiry_detail_admin(inquiry_id):
    """특정 문의사항의 상세 정보를 조회합니다."""
    try:
        inquiries_collection = mongo.db.inquiries
        # ObjectId로 변환하여 쿼리
        inquiry = inquiries_collection.find_one({'_id': ObjectId(inquiry_id)})
        if not inquiry:
            current_app.logger.warning(f"Inquiry with ID {inquiry_id} not found in MongoDB.") # 로그 추가
            return jsonify({'message': '문의사항을 찾을 수 없습니다.'}), 404
        
        inquiry['_id'] = str(inquiry['_id'])
        if 'created_at' in inquiry and isinstance(inquiry['created_at'], datetime.datetime):
            inquiry['created_at'] = inquiry['created_at'].isoformat()
        if 'replied_at' in inquiry and isinstance(inquiry['replied_at'], datetime.datetime):
            inquiry['replied_at'] = inquiry['replied_at'].isoformat()

        # 사용자 정보 추가 (이메일 포함)
        user = db.session.get(User, inquiry.get('user_id'))
        inquiry['user_email'] = user.email if user else 'Unknown'
        inquiry['user_username'] = user.username if user else 'Unknown'
        inquiry['user_nickname'] = user.nickname if user else 'Unknown'

        if inquiry.get('replied_by_user_id'):
            replier = db.session.get(User, inquiry['replied_by_user_id'])
            inquiry['replied_by_username'] = replier.username if replier else 'Unknown'
            inquiry['replied_by_nickname'] = replier.nickname if replier else 'Unknown'
        else:
            inquiry['replied_by_username'] = None
            inquiry['replied_by_nickname'] = None

        return jsonify(inquiry), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching inquiry detail {inquiry_id}: {e}", exc_info=True)
        return jsonify({'message': '문의사항 상세 정보를 불러오는 데 실패했습니다.'}), 500

@admin_bp.route('/inquiries/<string:inquiry_id>/reply', methods=['PUT'])
@token_required
@roles_required(['관리자', '운영자'])
def reply_to_inquiry(inquiry_id):
    """문의사항에 답변을 추가하고 상태를 '답변 완료'로 변경합니다."""
    data = request.get_json()
    reply_content = data.get('reply_content')

    if not reply_content:
        return jsonify({'message': '답변 내용을 입력해주세요.'}), 400
    
    try:
        inquiries_collection = mongo.db.inquiries
        result = inquiries_collection.update_one(
            {'_id': ObjectId(inquiry_id)},
            {'$set': {
                'status': 'replied',
                'reply_content': reply_content,
                'replied_at': datetime.datetime.utcnow(),
                'replied_by_user_id': g.user_id # 답변한 관리자/운영자 ID
            }}
        )
        if result.matched_count == 0:
            return jsonify({'message': '문의사항을 찾을 수 없습니다.'}), 404
        
        return jsonify({'message': '문의사항에 답변이 성공적으로 추가되었습니다.', 'status': 'replied'}), 200
    except Exception as e:
        current_app.logger.error(f"Error replying to inquiry {inquiry_id}: {e}", exc_info=True)
        return jsonify({'message': '문의사항 답변에 실패했습니다.'}), 500

@admin_bp.route('/inquiries/<string:inquiry_id>/status', methods=['PUT'])
@token_required
@roles_required(['관리자', '운영자'])
def update_inquiry_status(inquiry_id):
    """문의사항의 상태를 변경합니다."""
    data = request.get_json()
    new_status = data.get('status')

    if new_status not in ["pending", "replied", "closed"]:
        return jsonify({'message': '유효하지 않은 상태 값입니다. (pending, replied, closed 중 하나)'}), 400

    try:
        inquiries_collection = mongo.db.inquiries
        update_fields = {'status': new_status}
        
        # 만약 상태가 "replied"가 아닌데 답변 내용이 있다면 제거 (선택 사항)
        # 또는 답변 내용이 있을 때만 "replied"로 변경하도록 강제할 수도 있음
        if new_status != 'replied':
            update_fields['reply_content'] = None
            update_fields['replied_at'] = None
            update_fields['replied_by_user_id'] = None

        result = inquiries_collection.update_one(
            {'_id': ObjectId(inquiry_id)},
            {'$set': update_fields}
        )
        if result.matched_count == 0:
            return jsonify({'message': '문의사항을 찾을 수 없습니다.'}), 404
        
        return jsonify({'message': f'문의사항 상태가 "{new_status}"로 변경되었습니다.', 'status': new_status}), 200
    except Exception as e:
        current_app.logger.error(f"Error updating inquiry status {inquiry_id}: {e}", exc_info=True)
        return jsonify({'message': '문의사항 상태 변경에 실패했습니다.'}), 500

@admin_bp.route('/inquiries/<string:inquiry_id>', methods=['DELETE'])
@token_required
@roles_required(['관리자', '운영자'])
def delete_inquiry(inquiry_id):
    """문의사항을 삭제합니다."""
    try:
        inquiries_collection = mongo.db.inquiries
        result = inquiries_collection.delete_one({'_id': ObjectId(inquiry_id)})
        if result.deleted_count == 0:
            return jsonify({'message': '문의사항을 찾을 수 없습니다.'}), 404
        return jsonify({'message': '문의사항이 성공적으로 삭제되었습니다.'}), 200
    except Exception as e:
        current_app.logger.error(f"Error deleting inquiry {inquiry_id}: {e}", exc_info=True)
        return jsonify({'message': '문의사항 삭제에 실패했습니다.'}), 500

import os
import logging
import sys
from flask import Blueprint, request, jsonify, g, current_app
from backend.extensions import db, mongo
from backend.maria_models import User, Post, Comment, Role, Notice, PostLike
from backend.mongo_models import DiaryEntry, MoodEntry, Inquiry, PsychTest, PsychQuestion, PsychTestResult
from backend.routes.auth_routes import token_required, roles_required
from bson.objectid import ObjectId
import datetime
from datetime import timedelta
from collections import Counter
from sqlalchemy import and_
from sqlalchemy.orm import joinedload

# --- Helper Function for MongoDB Connection ---
def get_mongo_db():
    """Provides a stable connection to the MongoDB database."""
    db_name = current_app.config.get("MONGO_DBNAME", "mindbridge_db")
    return mongo.cx[db_name]

admin_bp = Blueprint('admin_api', __name__)

@admin_bp.record_once
def record(state):
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'frontend', 'static', 'uploads', 'admin')
    if not os.path.exists(UPLOAD_FOLDER):
        os.makedirs(UPLOAD_FOLDER)
        state.app.logger.info(f"ADMIN UPLOAD_FOLDER created: {UPLOAD_FOLDER}")
    else:
        state.app.logger.info(f"ADMIN UPLOAD_FOLDER already exists: {UPLOAD_FOLDER}")


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
        users_data = []
        for user in users:
            user_dict = {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'user_uid': user.user_uid,
                'nickname': user.nickname,
                'gender': user.gender,
                'age': user.age,
                'major': user.major,
                'created_at': user.created_at.isoformat() if user.created_at else None,
                'updated_at': user.updated_at.isoformat() if user.updated_at else None,
                'roles': [role.name for role in user.roles]
            }
            users_data.append(user_dict)
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

# 공지사항 관련 API
@admin_bp.route('/notices', methods=['POST'])
@token_required
@roles_required(['관리자', '운영자'])
def create_notice():
    data = request.get_json()
    title = data.get('title')
    content = data.get('content')
    is_public = data.get('is_public', True)
    start_date_str = data.get('start_date')
    end_date_str = data.get('end_date')

    if not all([title, content]):
        return jsonify({'message': '제목과 내용은 필수입니다.'}), 400

    start_date = datetime.datetime.fromisoformat(start_date_str.replace('Z', '+00:00')) if start_date_str else None
    end_date = datetime.datetime.fromisoformat(end_date_str.replace('Z', '+00:00')) if end_date_str else None

    if start_date and end_date and end_date < start_date:
        return jsonify({'message': '종료일은 시작일보다 빠를 수 없습니다.'}), 400
    
    try:
        new_notice = Notice(
            title=title, content=content, user_id=g.user_id,
            is_public=is_public, start_date=start_date, end_date=end_date
        )
        db.session.add(new_notice)
        db.session.commit()
        return jsonify({'message': '공지사항이 성공적으로 생성되었습니다.', 'id': new_notice.id}), 201
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error creating notice: {e}", exc_info=True)
        return jsonify({'message': '공지사항 생성에 실패했습니다.'}), 500

@admin_bp.route('/notices', methods=['GET'])
@token_required
@roles_required(['관리자', '운영자'])
def get_all_notices_admin():
    try:
        notices = Notice.query.options(joinedload(Notice.author)).order_by(Notice.created_at.desc()).all()
        notices_data = []
        for notice in notices:
            notices_data.append({
                'id': notice.id,
                'title': notice.title,
                'content': notice.content,
                'author_nickname': notice.author.nickname if notice.author else '알 수 없음',
                'is_public': notice.is_public,
                'created_at': notice.created_at.isoformat() if notice.created_at else None,
                'updated_at': notice.updated_at.isoformat() if notice.updated_at else None
            })
        return jsonify({'notices': notices_data}), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching all notices for admin: {e}", exc_info=True)
        return jsonify({'message': '공지사항 목록을 불러오는 데 실패했습니다.'}), 500

@admin_bp.route('/notices/<int:notice_id>', methods=['GET'])
@token_required
@roles_required(['관리자', '운영자'])
def get_notice(notice_id):
    try:
        notice = db.session.get(Notice, notice_id)
        if not notice:
            return jsonify({'message': '공지사항을 찾을 수 없습니다.'}), 404
        
        if notice.is_public and notice.end_date and notice.end_date < datetime.datetime.utcnow():
            notice.is_public = False
            db.session.commit()

        notice_data = {
            'id': notice.id, 'title': notice.title, 'content': notice.content,
            'user_id': notice.user_id,
            'is_public': notice.is_public,
            'start_date': notice.start_date.isoformat() if notice.start_date else None,
            'end_date': notice.end_date.isoformat() if notice.end_date else None,
            'created_at': notice.created_at.isoformat() if notice.created_at else None,
            'updated_at': notice.updated_at.isoformat() if notice.updated_at else None
        }
        return jsonify(notice_data), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error fetching notice {notice_id}: {e}", exc_info=True)
        return jsonify({'message': '공지사항을 불러오는 데 실패했습니다.'}), 500

@admin_bp.route('/notices/<int:notice_id>', methods=['PUT'])
@token_required
@roles_required(['관리자', '운영자'])
def update_notice(notice_id):
    data = request.get_json()
    try:
        notice = db.session.get(Notice, notice_id)
        if not notice:
            return jsonify({'message': '공지사항을 찾을 수 없습니다.'}), 404
        
        notice.title = data.get('title', notice.title)
        notice.content = data.get('content', notice.content)
        if data.get('is_public') is not None:
            notice.is_public = data.get('is_public')
        
        start_date_str = data.get('start_date')
        end_date_str = data.get('end_date')
        if start_date_str is not None:
            notice.start_date = datetime.datetime.fromisoformat(start_date_str.replace('Z', '+00:00')) if start_date_str else None
        if end_date_str is not None:
            notice.end_date = datetime.datetime.fromisoformat(end_date_str.replace('Z', '+00:00')) if end_date_str else None

        db.session.commit()
        return jsonify({'message': '공지사항이 성공적으로 수정되었습니다.'}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating notice {notice_id}: {e}", exc_info=True)
        return jsonify({'message': '공지사항 수정에 실패했습니다.'}), 500


@admin_bp.route('/notices/<int:notice_id>', methods=['PUT'])
@token_required
@roles_required(['관리자', '운영자'])
def update_notice(notice_id):
    data = request.get_json()
    try:
        notice = db.session.get(Notice, notice_id)
        if not notice:
            return jsonify({'message': '공지사항을 찾을 수 없습니다.'}), 404
        
        notice.title = data.get('title', notice.title)
        notice.content = data.get('content', notice.content)
        if data.get('is_public') is not None:
            notice.is_public = data.get('is_public')
        
        start_date_str = data.get('start_date')
        end_date_str = data.get('end_date')
        if start_date_str is not None:
            notice.start_date = datetime.datetime.fromisoformat(start_date_str.replace('Z', '+00:00')) if start_date_str else None
        if end_date_str is not None:
            notice.end_date = datetime.datetime.fromisoformat(end_date_str.replace('Z', '+00:00')) if end_date_str else None

        db.session.commit()
        return jsonify({'message': '공지사항이 성공적으로 수정되었습니다.'}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating notice {notice_id}: {e}", exc_info=True)
        return jsonify({'message': '공지사항 수정에 실패했습니다.'}), 500

@admin_bp.route('/notices/<int:notice_id>/toggle_visibility', methods=['PUT'])
@token_required
@roles_required(['관리자', '운영자'])
def toggle_notice_visibility(notice_id):
    try:
        notice = db.session.get(Notice, notice_id)
        if not notice:
            return jsonify({'message': '공지사항을 찾을 수 없습니다.'}), 404
        
        notice.is_public = not notice.is_public
        db.session.commit()
        status = "공개" if notice.is_public else "비공개"
        return jsonify({'message': f'공지사항이 성공적으로 {status} 처리되었습니다.', 'is_public': notice.is_public}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error toggling notice visibility {notice_id}: {e}", exc_info=True)
        return jsonify({'message': '공지사항 공개/비공개 전환에 실패했습니다.'}), 500

@admin_bp.route('/notices/<int:notice_id>', methods=['DELETE'])
@token_required
@roles_required(['관리자', '운영자'])
def delete_notice(notice_id):
    try:
        notice = db.session.get(Notice, notice_id)
        if not notice:
            return jsonify({'message': '공지사항을 찾을 수 없습니다.'}), 404
        
        db.session.delete(notice)
        db.session.commit()
        return jsonify({'message': '공지사항이 성공적으로 삭제되었습니다.'}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting notice {notice_id}: {e}", exc_info=True)
        return jsonify({'message': '공지사항 삭제에 실패했습니다.'}), 500


@admin_bp.route('/notices/public', methods=['GET'])
def get_public_notices():
    try:
        notices_to_update = Notice.query.filter(
            Notice.is_public == True,
            Notice.end_date != None,
            Notice.end_date < datetime.datetime.utcnow()
        ).all()

        for notice in notices_to_update:
            notice.is_public = False
        if notices_to_update:
            db.session.commit()

        public_notices = Notice.query.filter(
            Notice.is_public == True,
            and_(
                Notice.start_date <= datetime.datetime.utcnow(),
                (Notice.end_date == None) | (Notice.end_date > datetime.datetime.utcnow())
            )
        ).options(joinedload(Notice.author)).order_by(Notice.created_at.desc()).all()

        notices_data = []
        for n in public_notices:
            notices_data.append({
                'id': n.id, 'title': n.title, 'content': n.content,
                'author_nickname': n.author.nickname if n.author else '알 수 없음',
                'created_at': n.created_at.isoformat() if n.created_at else None
            })
        return jsonify({'notices': notices_data}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error fetching public notices: {e}", exc_info=True)
        return jsonify({'message': '공지사항을 불러오는 데 실패했습니다.'}), 500


# DB 관리 API
@admin_bp.route('/db_records', methods=['GET'])
@token_required
@roles_required(['관리자', '개발자', '연구자'])
def get_db_records():
    try:
        db_mongo = get_mongo_db()
        records_data = []

        # 일기 기록
        diary_entries = list(db_mongo.diary_entries.find({}).sort('created_at', -1).limit(100))
        for entry in diary_entries:
            user = db.session.get(User, entry.get('user_id'))
            created_at_val = entry.get('created_at', datetime.datetime.utcnow())
            timestamp_iso = created_at_val.isoformat() if isinstance(created_at_val, datetime.datetime) else created_at_val
            records_data.append({
                'id': str(entry['_id']),
                'user_id': entry.get('user_id'),
                'user_username': user.username if user else 'Unknown',
                'user_email': user.email if user else 'Unknown',
                'type': '일기',
                'summary': entry.get('title', '제목 없음'),
                'timestamp': timestamp_iso,
                'conversation': [{'role': '일기 내용', 'text': entry.get('content', '내용 없음')}]
            })
        
        # 감정 기록
        mood_entries = list(db_mongo.mood_entries.find({}).sort('timestamp', -1).limit(100))
        for entry in mood_entries:
            user = db.session.get(User, entry.get('user_id'))
            timestamp_val = entry.get('timestamp', datetime.datetime.utcnow())
            timestamp_iso_mood = timestamp_val.isoformat() if isinstance(timestamp_val, datetime.datetime) else timestamp_val
            records_data.append({
                'id': str(entry['_id']),
                'user_id': entry.get('user_id'),
                'user_username': user.username if user else 'Unknown',
                'user_email': user.email if user else 'Unknown',
                'type': '감정 기록',
                'summary': f"감정: {entry.get('mood', '알 수 없음')}",
                'timestamp': timestamp_iso_mood,
                'conversation': [{'role': '감정', 'text': entry.get('mood', '알 수 없음')}]
            })

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
        posts = db.session.query(
            Post,
            db.func.count(db.distinct(Comment.id)).label('comment_count'),
            db.func.count(db.distinct(PostLike.user_id)).label('like_count')
        ).outerjoin(Comment, Post.id == Comment.post_id)\
         .outerjoin(PostLike, Post.id == PostLike.post_id)\
         .group_by(Post.id)\
         .options(joinedload(Post.author))\
         .order_by(Post.created_at.desc()).all()

        posts_data = []
        for post, comment_count, like_count in posts:
            post_content = db_mongo.post_contents.find_one({'_id': ObjectId(post.mongo_content_id)})
            content_text = post_content.get('content', '내용 없음') if post_content else '내용 없음'
            posts_data.append({
                'id': post.id, 'title': post.title, 'content': content_text,
                'author_id': post.user_id,
                'author_username': post.author.username if post.author else '알 수 없음',
                'author_nickname': post.author.nickname if post.author else '탈퇴한 사용자',
                'is_anonymous': post.is_anonymous, 'category': post.category,
                'views': post.views, 'likes': like_count, 'comment_count': comment_count,
                'report_count': 0, 'is_suspended': post.is_suspended,
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
        db_mongo = get_mongo_db()
        post_query = db.session.query(
            Post,
            db.func.count(db.distinct(Comment.id)).label('comment_count'),
            db.func.count(db.distinct(PostLike.user_id)).label('like_count')
        ).outerjoin(Comment, Post.id == Comment.post_id)\
         .outerjoin(PostLike, Post.id == PostLike.post_id)\
         .filter(Post.id == post_id).group_by(Post.id).options(joinedload(Post.author)).first()

        if not post_query:
            return jsonify({'message': '게시글을 찾을 수 없습니다.'}), 404
        
        post_obj, comment_count, like_count = post_query
        post_content = db_mongo.post_contents.find_one({'_id': ObjectId(post_obj.mongo_content_id)})
        
        return jsonify({
            'id': post_obj.id, 'title': post_obj.title,
            'content': post_content.get('content', '내용 없음') if post_content else '내용 없음',
            # ... (rest of the fields)
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
        
        if post.mongo_content_id:
            db_mongo = get_mongo_db()
            db_mongo.post_contents.delete_one({'_id': ObjectId(post.mongo_content_id)})

        db.session.delete(post)
        db.session.commit()
        return jsonify({'message': '게시글이 성공적으로 삭제되었습니다.'}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error deleting post {post_id}: {e}", exc_info=True)
        return jsonify({'message': '게시글 삭제에 실패했습니다.'}), 500

# 게시글 정지/복구 기능
@admin_bp.route('/posts/<int:post_id>/toggle_suspension', methods=['PUT'])
@token_required
@roles_required(['관리자', '운영자'])
def toggle_post_suspension(post_id):
    data = request.get_json()
    suspend = data.get('suspend')
    duration_hours = data.get('duration_hours')

    if suspend is None:
        return jsonify({'message': '정지 여부(suspend)를 지정해야 합니다.'}), 400

    try:
        post = db.session.get(Post, post_id)
        if not post:
            return jsonify({'message': '게시글을 찾을 수 없습니다.'}), 404
        
        if suspend:
            if not isinstance(duration_hours, (int, float)) or duration_hours <= 0:
                return jsonify({'message': '유효한 정지 기간(시간)을 입력해야 합니다.'}), 400
            post.is_suspended = True
            post.suspended_until = datetime.datetime.utcnow() + timedelta(hours=duration_hours)
            message = f"게시글이 성공적으로 {duration_hours}시간 동안 정지되었습니다."
        else:
            post.is_suspended = False
            post.suspended_until = None
            message = "게시글 정지가 성공적으로 해제되었습니다."
        
        db.session.commit()
        return jsonify({'message': message}), 200
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error toggling suspension for post {post_id}: {e}", exc_info=True)
        return jsonify({'message': '게시글 정지/해제 처리에 실패했습니다.'}), 500


# CMS (콘텐츠 관리 시스템) APIs
@admin_bp.route('/cms/<string:content_type>', methods=['GET'])
@token_required
@roles_required(['관리자'])
def get_cms_content(content_type):
    try:
        db_mongo = get_mongo_db()
        content_items = list(db_mongo.cms_content.find({'type': content_type}).sort('created_at', 1))
        for item in content_items:
            item['_id'] = str(item['_id'])
        return jsonify({'content': content_items}), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching CMS content for {content_type}: {e}", exc_info=True)
        return jsonify({'message': '콘텐츠를 불러오는 데 실패했습니다.'}), 500

@admin_bp.route('/cms/<string:content_type>/<string:item_id>', methods=['GET'])
@token_required
@roles_required(['관리자'])
def get_cms_item(content_type, item_id):
    try:
        db_mongo = get_mongo_db()
        item = db_mongo.cms_content.find_one({'_id': ObjectId(item_id), 'type': content_type})
        if not item: return jsonify({'message': '콘텐츠를 찾을 수 없습니다.'}), 404
        item['_id'] = str(item['_id'])
        return jsonify(item), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching CMS item {item_id}: {e}", exc_info=True)
        return jsonify({'message': '콘텐츠를 불러오는 데 실패했습니다.'}), 500


@admin_bp.route('/cms/<string:content_type>', methods=['POST'])
@token_required
@roles_required(['관리자'])
def add_cms_content(content_type):
    data = request.get_json()
    try:
        db_mongo = get_mongo_db()
        new_item = {
            'type': content_type, 'title': data.get('title'), 'content': data.get('content'),
            'created_at': datetime.datetime.utcnow(), 'updated_at': datetime.datetime.utcnow(),
            'user_id': g.user_id
        }
        if content_type == 'psych_test_questions':
            new_item['options'] = data.get('options', [])
        result = db_mongo.cms_content.insert_one(new_item)
        return jsonify({'id': str(result.inserted_id)}), 201
    except Exception as e:
        current_app.logger.error(f"Error adding CMS content for {content_type}: {e}", exc_info=True)
        return jsonify({'message': '콘텐츠 추가에 실패했습니다.'}), 500

@admin_bp.route('/cms/<string:content_type>/<string:item_id>', methods=['PUT'])
@token_required
@roles_required(['관리자'])
def update_cms_content(content_type, item_id):
    data = request.get_json()
    try:
        db_mongo = get_mongo_db()
        update_data = {'updated_at': datetime.datetime.utcnow()}
        if 'title' in data: update_data['title'] = data['title']
        if 'content' in data: update_data['content'] = data['content']
        if content_type == 'psych_test_questions' and 'options' in data:
            update_data['options'] = data['options']
        result = db_mongo.cms_content.update_one({'_id': ObjectId(item_id)}, {'$set': update_data})
        if result.matched_count == 0: return jsonify({'message': '콘텐츠를 찾을 수 없습니다.'}), 404
        return jsonify({'message': '콘텐츠가 성공적으로 업데이트되었습니다.'}), 200
    except Exception as e:
        current_app.logger.error(f"Error updating CMS item {item_id}: {e}", exc_info=True)
        return jsonify({'message': '콘텐츠 수정에 실패했습니다.'}), 500


@admin_bp.route('/cms/<string:content_type>/<string:item_id>', methods=['DELETE'])
@token_required
@roles_required(['관리자'])
def delete_cms_content(content_type, item_id):
    try:
        db_mongo = get_mongo_db()
        result = db_mongo.cms_content.delete_one({'_id': ObjectId(item_id)})
        if result.deleted_count == 0: return jsonify({'message': '콘텐츠를 찾을 수 없습니다.'}), 404
        return jsonify({'message': '콘텐츠가 성공적으로 삭제되었습니다.'}), 200
    except Exception as e:
        current_app.logger.error(f"Error deleting CMS item {item_id}: {e}", exc_info=True)
        return jsonify({'message': '콘텐츠 삭제에 실패했습니다.'}), 500


# 데이터 분석 API
@admin_bp.route('/analytics/mood_distribution', methods=['GET'])
@token_required
@roles_required(['관리자', '연구자'])
def get_analytics_mood_distribution():
    try:
        db_mongo = get_mongo_db()
        mood_entries = db_mongo.mood_entries.find({})
        mood_counts = Counter(entry['mood'] for entry in mood_entries)
        return jsonify({
            'labels': list(mood_counts.keys()),
            'datasets': [{'data': list(mood_counts.values())}]
        }), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching mood distribution data: {e}", exc_info=True)
        return jsonify({'message': '감정 분포 데이터를 불러오는 데 실패했습니다.'}), 500


@admin_bp.route('/analytics/diary_entry_counts', methods=['GET'])
@token_required
@roles_required(['관리자', '연구자'])
def get_analytics_diary_entry_counts():
    try:
        db_mongo = get_mongo_db()
        pipeline = [
            {'$group': {'_id': {'$dateToString': {'format': '%Y-%m', 'date': '$created_at'}}, 'count': {'$sum': 1}}},
            {'$sort': {'_id': 1}}
        ]
        results = list(db_mongo.diary_entries.aggregate(pipeline))
        return jsonify({
            'labels': [res['_id'] for res in results],
            'datasets': [{'data': [res['count'] for res in results]}]
        }), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching diary entry counts data: {e}", exc_info=True)
        return jsonify({'message': '월별 일기 작성량 데이터를 불러오는 데 실패했습니다.'}), 500

@admin_bp.route('/analytics/top_keywords', methods=['GET'])
@token_required
@roles_required(['관리자', '연구자'])
def get_analytics_top_keywords():
    try:
        db_mongo = get_mongo_db()
        all_keywords = ["스트레스", "불안", "행복", "우울", "친구", "가족", "직장"] # 임시 데이터
        top_10 = Counter(all_keywords).most_common(10)
        return jsonify({
            'labels': [item[0] for item in top_10],
            'datasets': [{'data': [item[1] for item in top_10]}]
        }), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching top keywords data: {e}", exc_info=True)
        return jsonify({'message': '상위 키워드 데이터를 불러오는 데 실패했습니다.'}), 500

# 문의사항 관리 API
@admin_bp.route('/inquiries', methods=['GET'])
@token_required
@roles_required(['관리자', '운영자'])
def get_all_inquiries_admin():
    try:
        db_mongo = get_mongo_db()
        all_inquiries = list(db_mongo.inquiries.find({}).sort('created_at', -1))
        for inquiry in all_inquiries:
            inquiry['_id'] = str(inquiry['_id'])
        return jsonify({'inquiries': all_inquiries}), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching all inquiries for admin: {e}", exc_info=True)
        return jsonify({'message': '문의사항 목록을 불러오는 데 실패했습니다.'}), 500

@admin_bp.route('/inquiries/<string:inquiry_id>', methods=['GET'])
@token_required
@roles_required(['관리자', '운영자'])
def get_inquiry_detail_admin(inquiry_id):
    try:
        db_mongo = get_mongo_db()
        inquiry = db_mongo.inquiries.find_one({'_id': ObjectId(inquiry_id)})
        if not inquiry: return jsonify({'message': '문의사항을 찾을 수 없습니다.'}), 404
        inquiry['_id'] = str(inquiry['_id'])
        return jsonify(inquiry), 200
    except Exception as e:
        current_app.logger.error(f"Error fetching inquiry detail {inquiry_id} for admin: {e}", exc_info=True)
        return jsonify({'message': '문의사항 상세 정보를 불러오는 데 실패했습니다.'}), 500

@admin_bp.route('/inquiries/<string:inquiry_id>/reply', methods=['PUT'])
@token_required
@roles_required(['관리자', '운영자'])
def reply_to_inquiry(inquiry_id):
    data = request.get_json()
    try:
        db_mongo = get_mongo_db()
        result = db_mongo.inquiries.update_one(
            {'_id': ObjectId(inquiry_id)},
            {'$set': {
                'status': 'replied', 'reply_content': data.get('reply_content'),
                'replied_at': datetime.datetime.utcnow(), 'replied_by_user_id': g.user_id
            }}
        )
        if result.matched_count == 0: return jsonify({'message': '문의사항을 찾을 수 없습니다.'}), 404
        return jsonify({'message': '문의사항에 답변이 성공적으로 추가되었습니다.'}), 200
    except Exception as e:
        current_app.logger.error(f"Error replying to inquiry {inquiry_id}: {e}", exc_info=True)
        return jsonify({'message': '문의사항 답변에 실패했습니다.'}), 500


@admin_bp.route('/inquiries/<string:inquiry_id>/status', methods=['PUT'])
@token_required
@roles_required(['관리자', '운영자'])
def update_inquiry_status(inquiry_id):
    data = request.get_json()
    new_status = data.get('status')
    try:
        db_mongo = get_mongo_db()
        update_fields = {'status': new_status}
        if new_status != 'replied':
             update_fields.update({'reply_content': None, 'replied_at': None, 'replied_by_user_id': None})
        result = db_mongo.inquiries.update_one({'_id': ObjectId(inquiry_id)}, {'$set': update_fields})
        if result.matched_count == 0: return jsonify({'message': '문의사항을 찾을 수 없습니다.'}), 404
        return jsonify({'message': f'문의사항 상태가 "{new_status}"로 변경되었습니다.'}), 200
    except Exception as e:
        current_app.logger.error(f"Error updating inquiry status {inquiry_id}: {e}", exc_info=True)
        return jsonify({'message': '문의사항 상태 변경에 실패했습니다.'}), 500

@admin_bp.route('/inquiries/<string:inquiry_id>', methods=['DELETE'])
@token_required
@roles_required(['관리자', '운영자'])
def delete_inquiry(inquiry_id):
    try:
        db_mongo = get_mongo_db()
        result = db_mongo.inquiries.delete_one({'_id': ObjectId(inquiry_id)})
        if result.deleted_count == 0: return jsonify({'message': '문의사항을 찾을 수 없습니다.'}), 404
        return jsonify({'message': '문의사항이 성공적으로 삭제되었습니다.'}), 200
    except Exception as e:
        current_app.logger.error(f"Error deleting inquiry {inquiry_id}: {e}", exc_info=True)
        return jsonify({'message': '문의사항 삭제에 실패했습니다.'}), 500
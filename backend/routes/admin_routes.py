# backend/routes/admin_routes.py
import os
from flask import Blueprint, request, jsonify, g, current_app
from auth import roles_required, token_required
from maria_models import User, Role, Post, Comment
from mongo_models import MongoPostContent, MenuItem
from extensions import db
from bson.objectid import ObjectId, InvalidId
import json

admin_bp = Blueprint('admin_api', __name__)

UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', 'frontend', 'static', 'uploads', 'community')

def get_mongo_post_content_collection():
    if 'MONGO_DB' not in current_app.config:
        from flask_pymongo import PyMongo
        current_app.config['MONGO_DB'] = PyMongo(current_app).db
    return current_app.config['MONGO_DB'].post_contents

def get_menu_config_collection():
    if 'MONGO_DB' not in current_app.config:
        from flask_pymongo import PyMongo
        current_app.config['MONGO_DB'] = PyMongo(current_app).db
    return current_app.config['MONGO_DB'].menu_configs

def get_role_menu_assignment_collection():
    if 'MONGO_DB' not in current_app.config:
        from flask_pymongo import PyMongo
        current_app.config['MONGO_DB'] = PyMongo(current_app).db
    return current_app.config['MONGO_DB'].role_menu_assignments

# 메뉴 목록 가져오기 (권한 완화)
@admin_bp.route('/menu_configs', methods=['GET'])
# @token_required # 이 데코레이터를 제거하여 로그인 없이도 메뉴 목록을 가져올 수 있도록 함
def get_menu_configs():
    menu_items_cursor = get_menu_config_collection().find({})
    menu_items = [MenuItem.from_mongo(item).to_dict() for item in menu_items_cursor]
    return jsonify({'menu_items': menu_items}), 200

# 특정 메뉴 항목 가져오기
@admin_bp.route('/menu_configs/<menu_id>', methods=['GET'])
@token_required
@roles_required('관리자')
def get_menu_config(menu_id):
    try:
        obj_id = ObjectId(menu_id)
    except InvalidId:
        return jsonify({'message': '유효하지 않은 메뉴 ID입니다.'}), 400
    
    menu_item_data = get_menu_config_collection().find_one({'_id': obj_id})
    if not menu_item_data:
        return jsonify({'message': '메뉴 항목을 찾을 수 없습니다.'}), 404
    
    return jsonify(MenuItem.from_mongo(menu_item_data).to_dict()), 200

# 메뉴 항목 추가
@admin_bp.route('/menu_configs', methods=['POST'])
@token_required
@roles_required('관리자')
def add_menu_config():
    data = request.get_json()
    name = data.get('name')
    path = data.get('path')
    icon_class = data.get('icon_class')
    required_roles = data.get('required_roles', [])
    order = data.get('order')

    if not name or not path or not icon_class:
        return jsonify({'message': '메뉴 이름, 경로, 아이콘 클래스는 필수입니다.'}), 400
    
    # 중복 검사 (path와 name이 동일한 경우)
    if get_menu_config_collection().find_one({'path': path, 'name': name}):
        return jsonify({'message': '이미 동일한 경로와 이름을 가진 메뉴 항목이 존재합니다.'}), 409

    new_menu_item = MenuItem(name, path, icon_class, required_roles, order)
    inserted_id = get_menu_config_collection().insert_one(new_menu_item.to_dict()).inserted_id
    
    # 삽입된 문서의 _id를 포함하여 반환
    new_menu_item_data = get_menu_config_collection().find_one({'_id': inserted_id})
    return jsonify({'message': '메뉴 항목이 성공적으로 추가되었습니다.', 'menu_item': MenuItem.from_mongo(new_menu_item_data).to_dict()}), 201

# 메뉴 항목 업데이트
@admin_bp.route('/menu_configs/<menu_id>', methods=['PUT'])
@token_required
@roles_required('관리자')
def update_menu_config(menu_id):
    try:
        obj_id = ObjectId(menu_id)
    except InvalidId:
        return jsonify({'message': '유효하지 않은 메뉴 ID입니다.'}), 400

    data = request.get_json()
    update_data = {}
    if 'name' in data:
        update_data['name'] = data['name']
    if 'path' in data:
        update_data['path'] = data['path']
    if 'icon_class' in data:
        update_data['icon_class'] = data['icon_class']
    if 'required_roles' in data:
        update_data['required_roles'] = data['required_roles']
    if 'order' in data:
        update_data['order'] = data['order']

    if not update_data:
        return jsonify({'message': '업데이트할 내용이 없습니다.'}), 400

    # 중복 검사 (업데이트 시 path와 name이 다른 기존 항목과 중복되는지 확인)
    if 'path' in update_data and 'name' in update_data:
        existing_menu = get_menu_config_collection().find_one({
            'path': update_data['path'],
            'name': update_data['name'],
            '_id': {'$ne': obj_id} # 현재 업데이트하는 항목 제외
        })
        if existing_menu:
            return jsonify({'message': '이미 동일한 경로와 이름을 가진 다른 메뉴 항목이 존재합니다.'}), 409

    result = get_menu_config_collection().update_one({'_id': obj_id}, {'$set': update_data})

    if result.matched_count == 0:
        return jsonify({'message': '메뉴 항목을 찾을 수 없습니다.'}), 404
    
    updated_menu_item = get_menu_config_collection().find_one({'_id': obj_id})
    return jsonify({'message': '메뉴 항목이 성공적으로 업데이트되었습니다.', 'menu_item': MenuItem.from_mongo(updated_menu_item).to_dict()}), 200

# 메뉴 항목 삭제
@admin_bp.route('/menu_configs/<menu_id>', methods=['DELETE'])
@token_required
@roles_required('관리자')
def delete_menu_config(menu_id):
    try:
        obj_id = ObjectId(menu_id)
    except InvalidId:
        return jsonify({'message': '유효하지 않은 메뉴 ID입니다.'}), 400

    result = get_menu_config_collection().delete_one({'_id': obj_id})

    if result.deleted_count == 0:
        return jsonify({'message': '메뉴 항목을 찾을 수 없습니다.'}), 404
    
    return jsonify({'message': '메뉴 항목이 성공적으로 삭제되었습니다.'}), 200


# 모든 역할 목록 가져오기
@admin_bp.route('/roles', methods=['GET'])
@token_required
@roles_required('관리자')
def get_all_roles():
    roles = Role.query.all()
    return jsonify([{'id': role.id, 'name': role.name} for role in roles]), 200

# 특정 역할에 할당된 메뉴 설정 가져오기
@admin_bp.route('/roles/<int:role_id>/menu_configs', methods=['GET'])
@token_required
@roles_required('관리자')
def get_role_menu_configs(role_id):
    role = db.session.get(Role, role_id)
    if not role:
        return jsonify({'message': '역할을 찾을 수 없습니다.'}), 404
    
    assignment = get_role_menu_assignment_collection().find_one({'role_id': role.id})
    
    assigned_menu_items = []
    if assignment and assignment.get('menu_item_ids'):
        assigned_menu_ids = assignment['menu_item_ids']
        # ObjectId로 변환 가능한 유효한 ID만 필터링
        obj_ids = [ObjectId(mid) for mid in assigned_menu_ids if ObjectId.is_valid(mid)]
        if obj_ids:
            menu_items_cursor = get_menu_config_collection().find({'_id': {'$in': obj_ids}})
            found_items = {str(item['_id']): MenuItem.from_mongo(item).to_dict() for item in menu_items_cursor}
            assigned_menu_items = [found_items[mid] for mid in assigned_menu_ids if mid in found_items]

    return jsonify({'role_id': role_id, 'role_name': role.name, 'menu_items': assigned_menu_items}), 200

@admin_bp.route('/roles/<int:role_id>/menu_configs', methods=['PUT'])
@token_required
@roles_required('관리자')
def update_role_menu_configs(role_id):
    role = db.session.get(Role, role_id)
    if not role:
        return jsonify({'message': '역할을 찾을 수 없습니다.'}), 404

    data = request.get_json()
    menu_item_ids = data.get('menu_item_ids', [])

    if not isinstance(menu_item_ids, list):
        return jsonify({'message': 'menu_item_ids는 리스트 형태여야 합니다.'}), 400
    
    valid_menu_item_ids = [mid for mid in menu_item_ids if ObjectId.is_valid(mid)]

    result = get_role_menu_assignment_collection().update_one(
        {'role_id': role.id},
        {'$set': {'menu_item_ids': valid_menu_item_ids}},
        upsert=True # 문서가 없으면 새로 생성
    )

    if result.matched_count == 0 and result.upserted_id is None:
        return jsonify({'message': '메뉴 할당 업데이트에 실패했습니다.'}), 500

    return jsonify({'message': '메뉴 할당이 성공적으로 저장되었습니다.'}), 200

# 모든 사용자 목록 가져오기
@admin_bp.route('/users', methods=['GET'])
@token_required
@roles_required('관리자')
def get_all_users():
    users = User.query.all()
    users_data = []
    for user in users:
        user_roles = [user_role.role.name for user_role in user.user_roles_association]
        users_data.append({
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'nickname': user.nickname,
            'user_uid': user.user_uid,
            'roles': user_roles
        })
    return jsonify({'users': users_data}), 200

# 사용자 역할 업데이트
@admin_bp.route('/users/<int:user_id>/roles', methods=['PUT'])
@token_required
@roles_required('관리자')
def update_user_roles(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'message': '사용자를 찾을 수 없습니다.'}), 404

    data = request.get_json()
    role_names = data.get('roles', [])

    if not isinstance(role_names, list):
        return jsonify({'message': '역할은 리스트 형태여야 합니다.'}), 400

    # 기존 역할 연결 제거
    user.user_roles_association = []
    db.session.commit()

    # 새 역할 연결
    for role_name in role_names:
        role = Role.query.filter_by(name=role_name).first()
        if role:
            user.roles.append(role) # roles는 관계 속성
    db.session.commit()

    # 업데이트된 사용자 정보 반환
    updated_user_roles = [user_role.role.name for user_role in user.user_roles_association]
    return jsonify({'message': '사용자 역할이 성공적으로 업데이트되었습니다.', 'user_roles': updated_user_roles}), 200

# 게시글 관리 (목록, 삭제)
@admin_bp.route('/posts', methods=['GET'])
@token_required
@roles_required('관리자')
def get_all_posts():
    posts = Post.query.all()
    posts_data = []
    for post in posts:
        # MongoDB에서 content_html 가져오기
        mongo_content = get_mongo_post_content_collection().find_one({'_id': ObjectId(post.mongo_content_id)})
        content_html = mongo_content['content'] if mongo_content else "내용 없음"

        posts_data.append({
            'id': post.id,
            'title': post.title,
            'author_username': post.author.username,
            'created_at': post.created_at.isoformat(),
            'likes': post.likes,
            'views': post.views,
            'content_preview': content_html[:100] + '...' if len(content_html) > 100 else content_html # 미리보기
        })
    return jsonify({'posts': posts_data}), 200

@admin_bp.route('/posts/<int:post_id>', methods=['DELETE'])
@token_required
@roles_required('관리자')
def delete_post_admin(post_id):
    post = db.session.get(Post, post_id)
    if not post:
        return jsonify({'message': '게시글을 찾을 수 없습니다.'}), 404
    
    # MongoDB에서 게시글 내용 삭제
    if post.mongo_content_id:
        try:
            get_mongo_post_content_collection().delete_one({'_id': ObjectId(post.mongo_content_id)})
        except InvalidId:
            print(f"경고: 유효하지 않은 mongo_content_id {post.mongo_content_id}로 인해 MongoDB 문서 삭제 실패.")
        except Exception as e:
            print(f"MongoDB 문서 삭제 중 오류 발생: {e}")

    db.session.delete(post)
    db.session.commit()
    return jsonify({'message': '게시글이 성공적으로 삭제되었습니다.'}), 200

# 댓글 관리 (목록, 삭제)
@admin_bp.route('/comments', methods=['GET'])
@token_required
@roles_required('관리자')
def get_all_comments():
    comments = Comment.query.all()
    comments_data = []
    for comment in comments:
        comments_data.append({
            'id': comment.id,
            'content': comment.content,
            'author_username': comment.author.username,
            'post_title': comment.post.title,
            'created_at': comment.created_at.isoformat()
        })
    return jsonify({'comments': comments_data}), 200

@admin_bp.route('/comments/<int:comment_id>', methods=['DELETE'])
@token_required
@roles_required('관리자')
def delete_comment_admin(comment_id):
    comment = db.session.get(Comment, comment_id)
    if not comment:
        return jsonify({'message': '댓글을 찾을 수 없습니다.'}), 404
    
    db.session.delete(comment)
    db.session.commit()
    return jsonify({'message': '댓글이 성공적으로 삭제되었습니다.'}), 200

